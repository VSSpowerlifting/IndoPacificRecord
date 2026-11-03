"""Exact editorial selection of captured VPCP versions; grants no new source use."""
import copy
import hashlib
import hmac
import io
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from core.collection.vietnam_government_documents import FAMILY, digest, identity
from core.regional_official_link_render import read_live_links
from processing import government_document_intake as intake
from scripts import admit_official_document as cli
from tests.test_vietnam_government_documents import NOW, SHA, database, metadata

ROOT = Path(__file__).resolve().parents[1]
LATER = "2026-10-24T16:00:00Z"


def routine(ident="220078", subject="Synthetic routine personnel appointment"):
    """A real fixture whose subject is outside the bounded topic index."""
    m = metadata(ident)
    m["subject"] = subject
    return m


class EditorialSelection(unittest.TestCase):
    def setUp(self):
        self.conn = database()
        self.addCleanup(self.conn.close)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def selection(self, *entries, **override):
        value = {"source_family": FAMILY,
                 "decision_reference": "docs/engineering/VIETNAM_GOVERNMENT_DOCUMENTS_2026-10-23.md",
                 "policy": "config/vietnam_vpcp_metadata_policy.json",
                 "scope": "public_bibliographic_metadata_only",
                 "selections": [{"source_identity": identity(m), "metadata_sha256": digest(m),
                                 "selected_by": "test editor", "reason": "fixture"} for m in entries]}
        value.update(override)
        path = self.tmp / "selection.json"
        path.write_text(json.dumps(value, ensure_ascii=False))
        return path

    def admit(self, records, path=None, *, observed=NOW, run="offline-fixture", capture="b" * 64):
        return intake.admit(self.conn, [(m, capture) for m in records], source_sha=SHA, run_id=run,
                            observed_utc=observed, selection_path=path)

    def links(self):
        return self.conn.execute("SELECT source_identity,metadata_version_sha256,release_proof_sha256,"
            "released_at_utc,first_seen_run FROM regional_official_source_links ORDER BY 1").fetchall()

    def versions(self):
        return self.conn.execute("SELECT count(*) FROM official_document_versions").fetchone()[0]

    def test_committed_selection_is_valid_and_empty(self):
        self.assertEqual(intake.selection()["selections"], [])

    def test_unselected_topic_false_negative_stays_unpublished(self):
        self.assertEqual(self.admit([routine()])["filtered"], 1)
        self.assertEqual(read_live_links(self.conn, "vietnam"), [])

    def test_selected_version_publishes_once_and_replay_is_a_noop(self):
        m = routine()
        self.admit([m])
        before = intake.processing_metadata(self.conn, identity(m))
        path = self.selection(m)
        report = self.admit([], path)
        self.assertEqual(report["selection"], {identity(m): "selection_admitted"})
        self.assertEqual(report["model_calls"], 0)
        first = self.links()
        self.assertEqual(first[0][:2], (identity(m), digest(m)))
        self.assertEqual(first[0][4], "offline-fixture")  # the capturing run, not the replay
        public = read_live_links(self.conn, "vietnam")
        self.assertEqual((public[0]["source_identity"], public[0]["topics"]), (identity(m), []))
        self.assertNotIn("body", public[0]["document"])
        for replay in ([], [m]):
            again = self.admit(replay, path, observed=LATER, run="later-run")
            self.assertEqual(again["selection"], {identity(m): "selection_unchanged"})
            self.assertEqual(self.links(), first)
        self.assertEqual(self.versions(), 1)
        # Text-processing routing is not widened by an editorial pin.
        self.assertEqual(intake.processing_metadata(self.conn, identity(m)), before)

    def test_revision_after_selection_holds_and_preserves_history(self):
        m = routine()
        self.admit([m])
        path = self.selection(m)
        self.admit([], path)
        revised = copy.deepcopy(m); revised["signatory"] += " (synthetic revision)"
        report = self.admit([revised], path, observed=LATER, run="later-run")
        self.assertEqual(report["selection"], {identity(m): "selection_revision_held"})
        self.assertEqual(read_live_links(self.conn, "vietnam"), [])
        self.assertEqual(self.versions(), 2)
        self.assertIsNone(intake.processing_metadata(self.conn, identity(m)))
        # The held pin stays held on replay; it is never followed automatically.
        self.assertEqual(self.admit([], path, observed=LATER)["selection"][identity(m)], "selection_revision_held")

    def test_pin_to_newest_of_several_versions_leaves_processing_held(self):
        m = routine()
        self.admit([m])
        revised = copy.deepcopy(m); revised["signatory"] += " (synthetic revision)"
        self.admit([revised], observed=LATER, run="later-run")
        self.assertIsNone(intake.processing_metadata(self.conn, identity(m)))
        report = self.admit([], self.selection(revised), observed=LATER)
        self.assertEqual(report["selection"][identity(m)], "selection_admitted")
        self.assertEqual(self.links()[0][1], digest(revised))
        self.assertIsNone(intake.processing_metadata(self.conn, identity(m)))

    def test_topical_revision_supersedes_the_pin_through_normal_routing(self):
        m = routine()
        self.admit([m])
        path = self.selection(m)
        self.admit([], path)
        topical = metadata("220078")
        report = self.admit([topical], path, observed=LATER, run="later-run")
        self.assertEqual(report["selection"][identity(m)], "selection_superseded")
        self.assertEqual(self.links()[0][1], digest(topical))
        self.assertEqual(self.versions(), 2)

    def test_out_of_scope_revision_follows_the_topical_rule_then_its_exact_pin(self):
        topical = metadata("220078")
        self.admit([topical])
        changed = routine()
        path = self.selection(changed)
        report = self.admit([changed], path, observed=LATER, run="later-run")
        # The unselected rule withdraws the old topical projection (main's rule,
        # unchanged); the editor's exact pin of the newest version then admits it.
        self.assertEqual(report["selection"][identity(changed)], "selection_admitted")
        self.assertEqual(self.links()[0][1], digest(changed))
        self.assertEqual(self.versions(), 2)

    def independent(self, m, proof="e" * 64):
        """A link admitted by another path: its proof is not a selection proof."""
        intake.store_verified_links(self.conn, [{"source_family": FAMILY, "source_identity": identity(m),
            "desk": "vietnam", "canonical_official_url": m["official_url"], "publisher_posted_date": m["issue_date"],
            "official_issuer": "vn_vpcp", "official_publisher": "vn_government_portal",
            "official_republisher": None, "source_git_commit": SHA, "metadata_version_sha256": digest(m),
            "first_seen_run": "independent-run"}], proof, NOW, stable_versions=True)

    def test_conflicting_pin_leaves_an_independent_admission_untouched(self):
        m = routine()
        revised = copy.deepcopy(m); revised["signatory"] += " (synthetic revision)"
        self.admit([m])
        self.admit([revised], observed=LATER, run="later-run")
        self.independent(m)
        before = self.links()
        report = self.admit([], self.selection(revised), observed=LATER, run="pin-run")
        self.assertEqual(report["selection"], {identity(m): "selection_conflict"})
        self.assertEqual(self.links(), before)
        # Removing the conflicting entry does not touch it either.
        self.assertEqual(self.admit([], self.selection(), observed=LATER)["selection"], {})
        self.assertEqual(self.links(), before)

    def test_independent_link_at_the_pinned_version_survives_entry_removal(self):
        m = routine()
        self.admit([m])
        self.independent(m)
        before = self.links()
        self.assertEqual(self.admit([], self.selection(m))["selection"], {identity(m): "selection_independent"})
        self.assertEqual(self.links(), before)
        self.assertEqual(self.admit([], self.selection(), observed=LATER)["selection"], {})
        self.assertEqual(self.links(), before)
        # An invalid file and a held revision do not withdraw it either.
        (self.tmp / "broken.json").write_text("{")
        self.admit([], self.tmp / "broken.json", observed=LATER)
        self.assertEqual(self.links(), before)

    def test_held_revision_withdraws_only_a_selection_owned_link(self):
        m, other = routine(), routine("220077")
        self.admit([m, other])
        self.independent(other)
        path = self.selection(m, other)
        self.assertEqual(self.admit([], path)["selection"],
                         {identity(m): "selection_admitted", identity(other): "selection_independent"})
        later = []
        for x in (m, other):
            r = copy.deepcopy(x); r["signatory"] += " (synthetic revision)"; later.append(r)
        # A recapture is applied directly so the topical rule cannot be the cause.
        for r in later:
            self.conn.execute("INSERT INTO official_document_versions VALUES (?,?,?,?,?,?,?,?)",
                (FAMILY, identity(r), digest(r), json.dumps(r, ensure_ascii=False, sort_keys=True),
                 "c" * 64, LATER, "later-run", SHA))
        report = self.admit([], path, observed=LATER)
        self.assertEqual(report["selection"], {identity(m): "selection_revision_held",
                                               identity(other): "selection_revision_held"})
        self.assertEqual([r[0] for r in self.links()], [identity(other)])

    def test_repin_replaces_only_its_own_link(self):
        m = routine()
        revised = copy.deepcopy(m); revised["signatory"] += " (synthetic revision)"
        self.admit([m])
        self.admit([], self.selection(m))
        self.assertEqual(self.links()[0][1], digest(m))
        self.admit([revised], self.selection(m), observed=LATER, run="later-run")
        self.assertEqual(self.links(), [])  # held: the pin is no longer the newest
        report = self.admit([], self.selection(revised), observed=LATER)
        self.assertEqual(report["selection"], {identity(m): "selection_admitted"})
        self.assertEqual(self.links()[0][1], digest(revised))
        self.assertEqual(self.versions(), 2)

    def test_editing_other_entries_never_changes_ownership(self):
        m, other = routine(), routine("220077")
        self.admit([m, other])
        self.admit([], self.selection(m))
        first = self.links()
        path = self.selection(m, other)
        data = json.loads(path.read_text())
        data["selections"][0]["reason"] = "edited reason"; data["selections"][0]["selected_by"] = "another editor"
        path.write_text(json.dumps(data, ensure_ascii=False))
        report = self.admit([], path, observed=LATER, run="later-run")
        self.assertEqual(report["selection"], {identity(m): "selection_unchanged",
                                               identity(other): "selection_admitted"})
        self.assertEqual([r for r in self.links() if r[0] == identity(m)], first)
        report = self.admit([], self.selection(other), observed=LATER)
        self.assertEqual(report["selection"], {identity(other): "selection_unchanged",
                                               identity(m): "selection_withdrawn"})
        self.assertEqual([r[0] for r in self.links()], [identity(other)])
        self.assertEqual(self.versions(), 2)

    def test_proof_routes_are_distinct(self):
        m = routine()
        self.admit([m])
        self.admit([], self.selection(m))
        proof = self.links()[0][2]
        self.assertEqual(proof, intake.selection_proof(intake.policy(), identity(m), digest(m), "b" * 64,
                                                       "offline-fixture", SHA))
        topical = metadata()
        self.admit([topical])
        topical_proof = [r for r in self.links() if r[0] == identity(topical)][0][2]
        self.assertNotEqual(topical_proof, intake.selection_proof(intake.policy(), identity(topical),
            digest(topical), "b" * 64, "offline-fixture", SHA))

    def test_pinned_topical_version_needs_no_selection_route(self):
        topical = metadata()
        self.admit([topical])
        self.assertEqual(self.admit([], self.selection(topical))["selection"][identity(topical)],
                         "selection_topical")

    def test_uncaptured_or_tampered_pin_holds_without_blocking_other_work(self):
        m, other = routine(), metadata()
        missing = routine("220077")
        self.admit([m])
        path = self.selection(m, missing)
        self.conn.execute("UPDATE official_document_versions SET metadata_json=? WHERE source_identity=?",
                          (json.dumps(dict(m, signatory="tampered"), ensure_ascii=False), identity(m)))
        report = self.admit([other], path)
        self.assertEqual(report["selection"], {identity(m): "selection_digest_mismatch",
                                               identity(missing): "selection_version_missing"})
        self.assertEqual(report["new"], 1)
        self.assertEqual([r["source_identity"] for r in read_live_links(self.conn, "vietnam")],
                         [identity(other)])

    def test_malformed_or_widened_selection_files_are_refused(self):
        m = routine()
        entry = {"source_identity": identity(m), "metadata_sha256": digest(m), "selected_by": "x", "reason": "y"}
        bad = [{"policy": "config/other.json"}, {"scope": "public_document_body"},
               {"source_family": "vn_mps_news_vi"}, {"selections": [dict(entry, public_translation=True)]},
               {"selections": [entry, entry]}, {"selections": [dict(entry, metadata_sha256="z" * 64)]},
               {"selections": [dict(entry, source_identity="vpcp-vi:0")]},
               {"selections": [dict(entry, selected_by=" ")]}, {"extra": True}]
        for override in bad:
            with self.subTest(override=override), self.assertRaisesRegex(ValueError, "vpcp_selection_invalid"):
                intake.selection(self.selection(**override))
        # Other shapes and a missing file raise the same code, never another error type.
        for text in ("[]", '{"selections": null}', '{"selections": ["x"]}', "", None):
            path = self.tmp / "shape.json"
            path.unlink(missing_ok=True)
            if text is not None:
                path.write_text(text)
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "vpcp_selection_invalid"):
                intake.selection(path)
        # In a run, the invalid file holds the selections only: topical
        # captures still admit and the unselected version stays unpublished.
        (self.tmp / "broken.json").write_text("{")
        topical = metadata()
        report = self.admit([m, topical], self.tmp / "broken.json")
        self.assertEqual(report["selection"], "vpcp_selection_invalid")
        self.assertEqual(report["new"], 1)
        self.assertEqual(self.versions(), 2)
        self.assertEqual([r["source_identity"] for r in read_live_links(self.conn, "vietnam")],
                         [identity(topical)])

    def test_invalid_file_freezes_selection_links_and_removal_withdraws(self):
        m = routine()
        self.admit([m], self.selection(m))
        broken = self.tmp / "broken.json"
        broken.write_text("{")
        # Recapture under an invalid file neither withdraws nor republishes.
        report = self.admit([m], broken, observed=LATER, run="later-run")
        self.assertEqual(report["selection"], "vpcp_selection_invalid")
        self.assertEqual([r[0] for r in self.links()], [identity(m)])
        report = self.admit([], self.selection(), observed=LATER, run="removal-run")
        self.assertEqual(report["selection"], {identity(m): "selection_withdrawn"})
        self.assertEqual(self.links(), [])
        self.assertEqual(self.versions(), 1)

    def test_downstream_failure_rolls_back_without_losing_prior_evidence(self):
        m = routine()
        self.admit([m])
        self.conn.commit()
        path = self.selection(m)
        with patch.object(intake, "store_verified_links", side_effect=RuntimeError("render host down")):
            with self.assertRaises(RuntimeError):
                with self.conn:
                    self.admit([metadata()], path)
        self.assertEqual((self.versions(), self.links()), (1, []))
        self.assertEqual(self.admit([], path)["selection"][identity(m)], "selection_admitted")

    def test_store_refusal_is_a_named_hold(self):
        m = routine()
        self.admit([m])
        with patch.object(intake, "store_verified_links", side_effect=ValueError("legacy_article_url_collision")):
            report = self.admit([], self.selection(m))
        self.assertEqual(report["selection"][identity(m)], "selection_held:legacy_article_url_collision")


class Invocation(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.m = routine()
        db = self.tmp / "candidate.db"
        with database() as mem, sqlite3.connect(db) as out:
            intake.admit(mem, [(self.m, "b" * 64)], source_sha=SHA, run_id="offline-fixture", observed_utc=NOW)
            mem.commit()
            mem.backup(out)
        self.db = db
        self.path = self.tmp / "selection.json"
        self.path.write_text(json.dumps({"source_family": FAMILY,
            "decision_reference": "docs/engineering/VIETNAM_GOVERNMENT_DOCUMENTS_2026-10-23.md",
            "policy": "config/vietnam_vpcp_metadata_policy.json", "scope": "public_bibliographic_metadata_only",
            "selections": [{"source_identity": identity(self.m), "metadata_sha256": digest(self.m),
                            "selected_by": "test editor", "reason": "fixture"}]}))

    def run_cli(self, *extra, family=FAMILY):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(["--family", family, "--identity", identity(self.m), "--database", str(self.db),
                             "--selection", str(self.path), *extra])
        return code, json.loads(out.getvalue())

    def link_count(self):
        with sqlite3.connect(self.db) as conn:
            return conn.execute("SELECT count(*) FROM regional_official_source_links").fetchone()[0]

    def test_dry_run_reports_without_writing_then_write_and_replay(self):
        code, report = self.run_cli()
        self.assertEqual((code, report["disposition"], report["written"], report["model_calls"]),
                         (0, "selection_admitted", False, 0))
        self.assertEqual(report["other_dispositions"], {})
        self.assertEqual(self.link_count(), 0)
        self.assertEqual(self.run_cli("--write")[1]["disposition"], "selection_admitted")
        self.assertEqual(self.run_cli("--write")[1]["disposition"], "selection_unchanged")
        self.assertEqual(self.link_count(), 1)

    def test_unknown_family_and_unselected_identity_hold(self):
        code, report = self.run_cli(family="vn_mps_news_vi")
        self.assertEqual((code, report["reason"]), (3, "unsupported_family"))
        self.path.write_text(self.path.read_text().replace(identity(self.m), "vpcp-vi:1"))
        code, report = self.run_cli()
        self.assertEqual((code, report["reason"]), (2, "identity_not_selected"))

    def test_repository_or_production_database_is_refused_for_writes(self):
        for target in (ROOT / "pla_watch.db", Path.home() / "pla-watch/pla_watch.db"):
            with self.subTest(target=target), patch.object(Path, "is_file", return_value=True):
                out = io.StringIO()
                with redirect_stdout(out):
                    code = cli.main(["--family", FAMILY, "--identity", identity(self.m), "--database",
                                     str(target), "--selection", str(self.path), "--write"])
                self.assertEqual((code, json.loads(out.getvalue())["reason"]), (2, "candidate_db_not_isolated"))

    def sealed(self, capture=None, key=b"k" * 32):
        cap = capture or {"schema": "ipr-vpcp-private-capture/1", "metadata": self.m,
            "pdf_sha256": "c" * 64, "content_sha256": "d" * 64, "metadata_sha256": digest(self.m),
            "collector_commit": SHA, "source_run": "1-1", "workflow_sha": SHA, "observed_utc": NOW}
        payload = json.dumps(cap, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        raw = json.dumps({"capture": cap, "mac": hmac.new(key, b"IPR-VPCP-CAPTURE-v1\n" + payload,
            hashlib.sha256).hexdigest()}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        path = self.tmp / (hashlib.sha256(raw).hexdigest() + ".json")
        path.write_bytes(raw)
        return path

    def test_private_record_hash_only_readback_and_refusals(self):
        record = self.sealed()
        with patch.dict(os.environ, {"VIETNAM_PRIVATE_BRIDGE_KEY": ""}):
            code, report = self.run_cli("--private-record", str(record))
        back = report["private_readback"]
        self.assertEqual((code, back["mac"], back["metadata_sha256"]), (0, "unverified_key_absent", digest(self.m)))
        self.assertEqual(back["custody"], "blocked:bridge_key_absent,original_not_supplied")
        self.assertNotIn("metadata", back)
        self.assertNotIn(self.m["subject"], json.dumps(report, ensure_ascii=False))
        with patch.dict(os.environ, {"VIETNAM_PRIVATE_BRIDGE_KEY": "k" * 32}):
            back = self.run_cli("--private-record", str(record))[1]["private_readback"]
            self.assertEqual((back["mac"], back["custody"]), ("verified", "blocked:original_not_supplied"))
        with patch.dict(os.environ, {"VIETNAM_PRIVATE_BRIDGE_KEY": "x" * 32}):
            self.assertEqual(self.run_cli("--private-record", str(record))[1]["reason"], "private_record_mac_invalid")
        renamed = record.with_name("e" * 64 + ".json"); record.rename(renamed)
        self.assertEqual(self.run_cli("--private-record", str(renamed))[1]["reason"], "private_record_hash_mismatch")
        other = routine(subject="Synthetic different subject")
        mismatched = self.sealed(dict(json.loads(renamed.read_text())["capture"], metadata=other,
                                      metadata_sha256=digest(other)))
        self.assertEqual(self.run_cli("--private-record", str(mismatched))[1]["reason"], "private_record_pin_mismatch")
        self.assertEqual(self.run_cli("--private-original", str(renamed))[1]["reason"], "private_original_without_record")
        self.assertEqual(self.link_count(), 0)

    def test_dry_run_reads_a_clean_wal_copy_without_sidecars(self):
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("PRAGMA journal_mode=WAL").fetchone(), ("wal",))
        self.assertFalse(Path(str(self.db) + "-wal").exists())
        before = self.db.read_bytes()
        code, report = self.run_cli()
        self.assertEqual((code, report["disposition"], report["written"]), (0, "selection_admitted", False))
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(self.link_count(), 0)

    def test_custody_is_authenticated_only_with_key_and_replayed_original(self):
        original = self.tmp / "original.bin"
        original.write_bytes(b"%PDF- synthetic original")
        content = "d" * 64
        record = self.sealed(dict(json.loads(self.sealed().read_text())["capture"],
                                  pdf_sha256=hashlib.sha256(original.read_bytes()).hexdigest()))
        args = ("--private-record", str(record), "--private-original", str(original))
        with patch.object(cli, "inspect_pdf", lambda data, m, expected_sha256: {"content_sha256": content}):
            with patch.dict(os.environ, {"VIETNAM_PRIVATE_BRIDGE_KEY": ""}):
                back = self.run_cli(*args)[1]["private_readback"]
                self.assertEqual((back["original_replay"], back["custody"]), ("replayed", "blocked:bridge_key_absent"))
            with patch.dict(os.environ, {"VIETNAM_PRIVATE_BRIDGE_KEY": "k" * 32}):
                code, report = self.run_cli(*args)
                self.assertEqual((code, report["private_readback"]["custody"]), (0, "authenticated"))
                original.write_bytes(b"%PDF- altered")
                self.assertEqual(self.run_cli(*args)[1]["reason"], "private_original_hash_mismatch")
        original.write_bytes(b"%PDF- synthetic original")
        with patch.object(cli, "inspect_pdf", lambda data, m, expected_sha256: {"content_sha256": "0" * 64}):
            self.assertEqual(self.run_cli(*args)[1]["reason"], "private_content_hash_mismatch")
        self.assertEqual(self.link_count(), 0)


if __name__ == "__main__":
    unittest.main()
