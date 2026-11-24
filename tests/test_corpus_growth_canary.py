"""Corpus-growth canary: tests that read the tracked database must survive growth.

Several test classes copy the tracked ``pla_watch.db`` and read it under a
synthetic policy. The first genuine released ``daily_machine_records`` row of a
desk family is bound to the *real* policy, so such a test can start raising
``IntakeHold('daily_output_schema_or_policy_invalid')`` the day the corpus
grows, long after the PR that introduced it. This canary finds that fragility at
PR time:

1. copy the tracked database to a temp dir (the tracked file is never opened for
   writing; its sha256 is asserted unchanged);
2. insert one validate_output-valid released row per family that
   ``core.daily_machine_records.load`` would show under the real policy (its
   own eligibility and release holds), and confirm load() shows each. A visible
   family that cannot be grown is a gap, reported but never a failure; code
   defects that cause gaps fail independently of data in
   ``code_gaps()`` (see FAILING_GAP_CODES);
3. run the test modules that copy the tracked database in a subprocess where
   ``shutil.copy/copy2/copyfile`` of the tracked path is redirected to the grown
   copy. No production code and no other test is changed.

Target selection is deterministic: every ``tests/test_*.py`` (except this file)
containing a ``shutil.copy*(`` call whose source expression names the tracked
database (``TRACKED``, ``TRACKED_DB``, ``tracked`` or ``pla_watch.db``).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACKED = ROOT / "pla_watch.db"
SELF = Path(__file__).name
# grow()'s own unit tests live apart so this module is one slow unit that
# scripts.parallel_unittest schedules first (MEASURED_SECONDS).
HELPER_TESTS = "test_corpus_growth_canary_helpers.py"
_COPY_RE = re.compile(
    r"shutil\.copy(?:2|file)?\(\s*([^,\n]*(?:TRACKED|tracked|pla_watch\.db)[^,\n]*),")

# Where a family's parent identities live when source.parent is set (the
# parent *row* is always resolved through source.parent_link, as load() does).
# A parent-bearing family missing here is a gap and fails the canary.
PARENT_TABLES = {
    "jp_jcg_press_en": ("japan_jcg_source_records", "1=1"),
    "us_uscc_press_en": ("uscc_press_source_records", "1=1"),
    "sg_mindef_releases": ("singapore_mindef_source_records", "1=1"),
    "kr_policy_dapa_releases": (
        "korea_official_source_records",
        "official_issuer='kr_dapa' AND public_scope='official_link_only'"),
}
# A visible family the canary cannot grow is a *gap*. Gaps are reported, never
# a failure of the canary run itself: which families are growable depends on the
# tracked data and the committed policy, and the Daily commits data unattended,
# so a gap-based failure would let a data-only change (or a policy-only pause,
# hold or activation) turn main red, the very failure class this canary exists
# to prevent. In every gap load() shows either no row of the family yet or only
# genuine released rows that already exercise every reader.
#
# Code defects that would *cause* gaps are caught independently of data and
# policy, at code-PR time, by tests/test_corpus_growth_canary_helpers.py
# (CannedRowsCoverEveryFamily): every policy family must have a source
# definition, enumerable parent support whose table is created by a migration,
# and a canned row its output check accepts under a forced-eligible policy.
# The canary run fails only when a reader breaks on the grown copy, or when an
# inserted row is not visible through load() (canary/load() disagreement).
FAILING_GAP_CODES = frozenset({"not_visible_after_insert"})
# Resolvable parents tried per family before reporting no_buildable_row.
MAX_BUILD_ATTEMPTS = 5
SUMMARY = (
    "The publisher announced a routine cooperation activity with a regional "
    "partner this week, according to its release."
)
# Family-specific wording where a family's output check (attribution, topic
# gates) rejects the generic sentence above.
FAMILY_SUMMARY = {
    "id_kemhan_news": "Kemhan announced a defence cooperation meeting with a regional partner "
                      "to strengthen bilateral military ties.",
    "ph_afp_articles": "The Armed Forces of the Philippines announced a joint maritime "
                       "cooperative activity with partners in the West Philippine Sea this week.",
    "ph_nsc_official_statements": "The National Security Council of the Philippines issued a "
                                  "statement on maritime incidents in the West Philippine Sea "
                                  "this week.",
    "sg_mindef_releases": "MINDEF announced that the Republic of Singapore Navy conducted a "
                          "bilateral exercise with a partner navy in the South China Sea this week.",
    "us_uscc_press_en": "The USCC announced the release of its annual report to Congress on "
                        "China and security.",
    "kr_policy_dapa_releases": "DAPA announced a defence acquisition programme meeting with "
                               "a partner to strengthen cooperation this week.",
    "jp_jcg_press_en": "The JCG announced that it conducted a joint training exercise with a "
                       "partner coast guard agency to strengthen maritime law enforcement "
                       "cooperation.",
}
# Runtime bound (~4 min alone, 18 modules otherwise finish in ~80 s with 4
# workers). It copies the tracked database for generic site rendering, passed
# on a grown copy when this canary was built, and is not a daily-record reader
# under a synthetic policy. Re-include it if its runtime drops.
SLOW_EXCLUDED = {"test_preview_prototype"}
NEVER_PARENT = {"15aug26-speech", "16sep26-speech"}


def target_modules():
    mods = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        if path.name in (SELF, HELPER_TESTS) or path.stem in SLOW_EXCLUDED:
            continue
        if _COPY_RE.search(path.read_text(encoding="utf-8", errors="replace")):
            mods.append(f"tests.{path.stem}")
    return mods


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _parent_identities(conn, family, src):
    """Candidate parent identities, newest first, or None if not enumerable."""
    spec = PARENT_TABLES.get(family)
    if spec is not None:
        table, where = spec
        sql = (f"SELECT source_identity FROM {table} WHERE {where} "
               "ORDER BY publisher_posted_date DESC")
    elif not src.parent:
        sql = ("SELECT source_identity FROM regional_official_source_links "
               "WHERE source_family=? ORDER BY publisher_posted_date DESC")
        return [r[0] for r in conn.execute(sql, (family,))]
    else:
        return None
    return [r[0] for r in conn.execute(sql)]


def _parent_row(conn, family, src, identity):
    """The parent exactly as load() resolves it (source.parent_link), plus raw
    provenance columns the normalized dict may omit."""
    if src.parent:
        return src.parent_link(conn, identity)
    row = conn.execute(
        "SELECT * FROM regional_official_source_links WHERE source_family=? AND source_identity=?",
        (family, identity)).fetchone()
    return dict(row) if row else None


def build_record(family, identity, par, src, display):
    """A validate_output-valid released row bound to ``display`` (the policy
    load() compares against), or raise the last validation error."""
    from processing import daily_intake as di
    last = None
    for version in (list(src.released_prompt_versions) + list(reversed(src.prompt_versions))):
        rec = {
            "source_family": family, "source_identity": identity,
            "metadata_version_sha256": par["metadata_version_sha256"],
            "content_sha256": par.get("content_sha256")
            or hashlib.sha256(b"c" + family.encode()).hexdigest(),
            "capture_sha256": par.get("capture_sha256")
            or hashlib.sha256(b"k" + family.encode()).hexdigest(),
            "source_git_commit": par.get("source_git_commit") or "0" * 40,
            "source_run": "99999999999-1",
            "summary": FAMILY_SUMMARY.get(family, SUMMARY),
            "categories": list(di.profile_for_source(family).categories)[:2],
            "model_flagged": False, "flag_reason": None,
            "model_id": "claude-sonnet-4-6", "prompt_version": version,
            "quality_sha256": hashlib.sha256(b"q" + family.encode()).hexdigest(),
            "policy_sha256": di.policy_binding(display),
        }
        try:
            di.validate_output(rec, family, display)
            return rec
        except Exception as exc:  # try the next accepted prompt version
            last = exc
    raise last if last else ValueError("no prompt versions")


def code_gaps():
    """Data- and policy-independent coverage defects, family -> reason.

    For every family in the committed policy (whatever its switches), the canary
    must be able to grow it the day data and policy allow: a source definition,
    enumerable parent support whose table a migration creates, and a canned row
    the family's output check accepts under a forced-eligible policy. Checked on
    every code PR so a defect fails there, never on a later data-only commit."""
    from core.daily_sources import source_for
    from processing import daily_intake as di
    migrations = "\n".join(
        p.read_text(encoding="utf-8") for p in sorted((ROOT / "migrations").rglob("*.py")))
    out = {}
    for family, pol in sorted(di.load_policy()["sources"].items()):
        src = source_for(family)
        if src is None:
            out[family] = "no source definition"
            continue
        if src.parent:
            spec = PARENT_TABLES.get(family)
            if spec is None:
                out[family] = "source.parent is set but PARENT_TABLES has no entry"
                continue
            if not re.search(rf"\b{re.escape(spec[0])}\b", migrations):
                out[family] = f"PARENT_TABLES table {spec[0]!r} is created by no migration"
                continue
        forced = {**pol, "public_machine_explanation": True,
                  "private_model_processing": True, "unattended_release": True}
        try:
            build_record(family, "canary-static-1",
                         {"metadata_version_sha256": hashlib.sha256(family.encode()).hexdigest()},
                         src, forced)
        except Exception as exc:
            out[family] = f"canned row rejected by the output check: {exc!r}"
    return out


def grow(db):
    """Insert one valid released row per family that load() would show.

    Returns (inserted, skipped, gaps). ``skipped`` maps family -> reason for
    families legitimately not visible (not eligible, paused, held). ``gaps``
    maps family -> (code, reason) for families that ARE visible under the real
    policy but could not be grown (reported; only FAILING_GAP_CODES fail).
    """
    from core import daily_machine_records as dmr
    from core.daily_sources import source_for
    from processing import daily_intake as di

    policy = di.load_policy()
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    inserted, skipped, gaps = {}, {}, {}
    before = {(r["source_family"], r["source_identity"]) for r in dmr.load(str(db))}
    try:
        for family, pol in sorted(policy["sources"].items()):
            # Eligibility is load()'s own, not a re-implementation.
            display = dmr._released_visibility_policy(family, pol)
            if display is None:
                skipped[family] = "not visible: public explanation off or switches not permitted"
                continue
            src = source_for(family)
            if src is None:
                gaps[family] = ("no_source_definition", "policy family has no source definition")
                continue
            hold = src.release_hold()
            if hold:
                skipped[family] = f"release hold: {hold}"
                continue
            try:
                identities = _parent_identities(conn, family, src)
            except sqlite3.OperationalError as exc:
                if "no such table" not in str(exc):
                    raise
                gaps[family] = ("parent_table_missing", str(exc))
                continue
            if identities is None:
                gaps[family] = ("parent_not_enumerable",
                                "source.parent is set but PARENT_TABLES has no entry")
                continue
            if not identities:
                gaps[family] = ("no_parent_rows", "no parent rows exist in the tracked database")
                continue
            existing = {r[0] for r in conn.execute(
                "SELECT source_identity FROM daily_machine_records WHERE source_family=?",
                (family,))}
            spare = [i for i in identities if i not in existing
                     and i not in pol["excluded_source_identities"] and i not in NEVER_PARENT]
            if not spare:
                gaps[family] = ("all_parents_released",
                                "every parent row already has a released Record or is excluded")
                continue
            rec_ok, last_err, chosen, tried = None, None, None, 0
            for identity in spare:
                if tried >= MAX_BUILD_ATTEMPTS:
                    break
                par = _parent_row(conn, family, src, identity)
                if not par:
                    # Held or otherwise unresolvable: load() would not show a
                    # Record on it either. It does not count as an attempt.
                    continue
                tried += 1
                try:
                    rec_ok, chosen = build_record(family, identity, par, src, display), identity
                except Exception as exc:
                    last_err = repr(exc)
                if rec_ok:
                    break
            if rec_ok is None and not tried:
                gaps[family] = ("no_resolvable_parent",
                                "no spare parent resolves through source.parent_link")
                continue
            if rec_ok is None:
                gaps[family] = ("no_buildable_row", f"no valid canary row buildable: {last_err}")
                continue
            vals = dict(rec_ok)
            vals["categories_json"] = json.dumps(vals.pop("categories"))
            vals["model_flagged"] = 0
            with conn:
                conn.execute(
                    f"INSERT INTO daily_machine_records ({','.join(vals)},publication_state) "
                    f"VALUES ({','.join('?' * len(vals))},'released')", list(vals.values()))
            inserted[family] = chosen
    finally:
        conn.close()
    after = {(r["source_family"], r["source_identity"]) for r in dmr.load(str(db))}
    for family, identity in inserted.items():
        if (family, identity) not in after or (family, identity) in before:
            gaps[family] = ("not_visible_after_insert",
                            "inserted row not visible through load() under the real policy")
    return inserted, skipped, gaps


def unexpected_gaps(gaps):
    return {f: v for f, v in gaps.items() if v[0] in FAILING_GAP_CODES}


_BOOTSTRAP = r"""
import shutil, sys, unittest
from pathlib import Path
tracked = Path(sys.argv[1]).resolve()
grown = sys.argv[2]
def _wrap(orig):
    def inner(src, dst, *a, **k):
        try:
            if Path(src).resolve() == tracked:
                src = grown
        except (OSError, TypeError):
            pass
        return orig(src, dst, *a, **k)
    return inner
for name in ("copy", "copy2", "copyfile"):
    setattr(shutil, name, _wrap(getattr(shutil, name)))
suite = unittest.defaultTestLoader.loadTestsFromNames(sys.argv[3:])
res = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(0 if res.wasSuccessful() else 1)
"""


class CorpusGrowthCanary(unittest.TestCase):
    def test_tracked_db_readers_survive_first_released_records(self):
        if not TRACKED.exists():
            self.skipTest("tracked database absent")
        before = _sha(TRACKED)
        mods = target_modules()
        self.assertTrue(mods, "no tracked-database test modules found; selection regex is stale")
        with tempfile.TemporaryDirectory(prefix="ipr-growth-canary-") as tmp:
            grown = Path(tmp) / "grown.db"
            shutil.copyfile(TRACKED, grown)
            inserted, skipped, gaps = grow(grown)
            bad = unexpected_gaps(gaps)
            self.assertFalse(
                bad, "inserted canary rows are not visible through load(): "
                + "; ".join(f"{f}: {c} - {r}" for f, (c, r) in bad.items()))
            if not inserted:
                # Nothing growable in this data/policy state. Code defects that
                # would cause this fail in CannedRowsCoverEveryFamily instead.
                self.skipTest(f"no family grown (skipped: {skipped}; gaps: {gaps})")
            print(f"\ncanary grew {sorted(inserted)}; skipped {skipped}; allowed gaps {gaps}; targets {len(mods)}",
                  file=sys.stderr)
            def run(mod):
                return mod, subprocess.run(
                    [sys.executable, "-c", _BOOTSTRAP, str(TRACKED), str(grown), mod],
                    cwd=str(ROOT), env=dict(os.environ), capture_output=True, text=True,
                    timeout=900)

            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(run, mods))
        self.assertEqual(_sha(TRACKED), before, "tracked database changed")
        failed = [(m, p) for m, p in results if p.returncode != 0]
        if failed:
            lines = []
            for mod, proc in failed:
                names = sorted(set(re.findall(
                    r"^(?:FAIL|ERROR): (\S+ \([^)]*\))", proc.stderr, re.M)))
                lines.append(f"{mod}: {', '.join(names) or 'no test id parsed'}")
            self.fail(
                "tests that read the tracked database break once genuine released Records exist "
                f"for {sorted(inserted)}. Isolate the family's rows on the scratch copy "
                "(see tests/test_japan_jcg_daily.py). Failing:\n  " + "\n  ".join(lines)
                + "\n--- tail of first failure ---\n" + failed[0][1].stderr[-2500:])


if __name__ == "__main__":
    unittest.main()
