"""
The one owner activation change for the South Korea Desk Daily.

scripts/korea_daily_activation.py is rehearsed on a temporary copy of the
desk configuration: the change it writes must load as a live registry whose
manifest syncs the one manual MND source, pass the bridge gates on a fresh
migrated database, and leave every other desk byte-for-byte alone. The real
repository must be in exactly one of the two states, never between them.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import desk_registry
from core import korea_corpus_bridge as bridge
from core.registry import sync_desk_config
from migrations.runner import apply_all, connect
from tests.test_migrations import build_legacy_db
from scripts import korea_daily_activation as activation

ROOT = Path(__file__).resolve().parent.parent


def desks(registry):
    return {d["slug"]: d for d in json.loads(registry)["desks"]}


class ActivationCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ipr-korea-activation-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        shutil.copytree(ROOT / "desks", self.root / "desks",
                        ignore=shutil.ignore_patterns("korea"))
        real = desks((ROOT / activation.REGISTRY).read_text(encoding="utf-8"))
        for entry in real.values():
            path = entry["manifest"]
            if path and not (self.root / path).exists():
                (self.root / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / path, self.root / path)
        (self.root / activation.STAGED).parent.mkdir(parents=True)
        shutil.copyfile(ROOT / activation.STAGED, self.root / activation.STAGED)
        self.before = (self.root / activation.REGISTRY).read_text(encoding="utf-8")

    def load(self):
        with mock.patch.object(desk_registry, "REPO_ROOT", self.root), \
                mock.patch.object(desk_registry, "DESKS_DIR", self.root / "desks"):
            return desk_registry.load_registry(self.root / activation.REGISTRY)


@unittest.skipUnless((ROOT / activation.STAGED).is_file(),
                     "repository already activated")
class TestActivationRehearsal(ActivationCase):
    def test_plan_writes_nothing(self):
        files = sorted(p for p in self.root.rglob("*") if p.is_file())
        snapshot = {p: p.read_bytes() for p in files}
        activation.plan(self.root)
        self.assertEqual({p: p.read_bytes() for p in files}, snapshot)
        self.assertFalse((self.root / activation.ACTIVE).exists())

    def test_apply_yields_a_live_registry_with_one_manual_source(self):
        activation.apply(self.root)
        self.assertFalse((self.root / activation.STAGED).exists())
        korea = self.load().get("korea")
        self.assertEqual(korea.status, "live")
        self.assertEqual(korea.manifest_path, "desks/korea/manifest.json")
        self.assertTrue(korea.has_production_records)
        self.assertEqual([(s.slug, s.access_method, s.enabled, s.contract_validated)
                          for s in korea.sources],
                         [(bridge.SOURCE_SLUG, "manual", True, True)])

    def test_apply_changes_only_the_korea_entry(self):
        activation.apply(self.root)
        after = (self.root / activation.REGISTRY).read_text(encoding="utf-8")
        start, end = activation._korea_block(self.before)
        a_start, a_end = activation._korea_block(after)
        self.assertEqual(self.before[:start], after[:a_start])
        self.assertEqual(self.before[end:], after[a_end:])
        old, new = desks(self.before), desks(after)
        self.assertEqual({k: v for k, v in old.items() if k != "korea"},
                         {k: v for k, v in new.items() if k != "korea"})
        changed = {k for k in old["korea"] if old["korea"][k] != new["korea"][k]}
        self.assertEqual(changed, set(activation.REGISTRY_FIELDS))
        self.assertIn("no human has reviewed", new["korea"]["status_explanation"])

    def test_applied_state_passes_the_bridge_gates(self):
        activation.apply(self.root)
        registry = self.load()
        build_legacy_db(self.root / "fresh.db")
        conn = connect(self.root / "fresh.db")
        self.addCleanup(conn.close)
        apply_all(conn)
        sync_desk_config(conn, self.root / "desks")
        source_id = bridge.check_gates(conn, registry=registry)
        self.assertEqual(conn.execute(
            "SELECT slug, desk_id, access_method, enabled FROM sources WHERE id=?",
            (source_id,)).fetchone(), (bridge.SOURCE_SLUG, "korea", "manual", 1))

    def test_shadow_state_fails_the_bridge_gates(self):
        build_legacy_db(self.root / "fresh.db")
        conn = connect(self.root / "fresh.db")
        self.addCleanup(conn.close)
        apply_all(conn)
        sync_desk_config(conn, self.root / "desks")
        with self.assertRaisesRegex(bridge.BridgeHold, "korea_source_not_registered"):
            bridge.check_gates(conn, registry=self.load())

    def test_apply_refuses_to_run_twice_or_from_half_state(self):
        activation.apply(self.root)
        with self.assertRaisesRegex(activation.ActivationError, "already activated"):
            activation.plan(self.root)
        (self.root / activation.ACTIVE).unlink()
        with self.assertRaisesRegex(activation.ActivationError, "staged manifest"):
            activation.plan(self.root)

    def test_cli_plan_is_dry(self):
        with mock.patch.object(activation, "REPO_ROOT", self.root), \
                mock.patch("sys.stdout"):
            self.assertEqual(activation.main(["plan"]), 0)
        self.assertTrue((self.root / activation.STAGED).is_file())
        self.assertEqual((self.root / activation.REGISTRY).read_text(encoding="utf-8"),
                         self.before)


class TestRepositoryState(unittest.TestCase):
    def test_repository_is_wholly_staged_or_wholly_activated(self):
        korea = desk_registry.load_registry().get("korea")
        staged = (ROOT / activation.STAGED).is_file()
        active = (ROOT / activation.ACTIVE).is_file()
        if staged:
            self.assertFalse(active)
            self.assertEqual((korea.status, korea.manifest_path,
                              korea.has_production_records), ("shadow", None, False))
        else:
            self.assertTrue(active)
            self.assertEqual((korea.status, korea.manifest_path,
                              korea.has_production_records),
                             ("live", "desks/korea/manifest.json", True))

    @unittest.skipIf((ROOT / activation.STAGED).is_file(), "not activated")
    def test_the_manual_source_is_healthy_and_judged_after_admission(self):
        from core.collection import status as st
        from core.registry import get_registry
        from scripts import check_source_liveness as liveness

        self.assertEqual(get_registry().healthcheck(bridge.SOURCE_SLUG).status, st.OK)
        self.assertEqual({r.source_slug: r.status for r in get_registry().healthcheck_all()}
                         [bridge.SOURCE_SLUG], st.OK)
        expected = liveness.expectations()[bridge.SOURCE_SLUG]
        self.assertEqual((expected.manual, expected.inert, expected.broken),
                         (True, False, False))


if __name__ == "__main__":
    unittest.main()
