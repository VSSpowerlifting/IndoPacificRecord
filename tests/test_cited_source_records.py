"""Eligible works cited by approved Briefs become link-metadata Records."""
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import unittest
from urllib.parse import urlsplit

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core import cited_source_records as cited, vietnam_source_use
from core.archive_research import with_cited
from core.brief_collection import load_collection
from core.desk_registry import load_registry
from core.mindef_permissions import APPROVED_MINDEF_LINKS

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "site" / "preview" / "templates"


def ref(rid, url, **extra):
    value = {"id": rid, "url": url, "publisher": "Publisher", "issuer": "Issuer",
             "date": "2026-10-01", "lang": "en", "original_title": "Title " + rid,
             "independence": "official",
             "verification": {"method": "publisher", "locator": "PRIVATE LOCATOR " + rid}}
    value.update(extra)
    return value


def brief(slug, issue, refs, **extra):
    entry = {"slug": slug, "issue": issue, "date": "2026-10-31", "title": "Brief " + slug,
             "url": "briefs/%s.html" % slug, "series_name": "Indo-Pacific Record Briefs"}
    entry.update(extra)
    return entry, {"publisher_references": refs}


def collection(*items):
    return SimpleNamespace(briefs=tuple(e for e, _ in items),
                           sidecars={e["slug"]: s for e, s in items})


class RightsGateTests(unittest.TestCase):
    def test_official_https_reference_is_admitted(self):
        self.assertIsNone(cited.omission(ref("s1", "https://www.mod.go.jp/a.html")))

    def test_independent_reporting_is_citation_only(self):
        r = ref("s1", "https://www.reuters.com/x", independence="independent")
        self.assertIsNone(cited.omission(r))
        records, links, omitted, _ = cited.resolve(collection(brief("b", 1, [r])))
        self.assertEqual((len(records), len(links["b"]), omitted), (1, 1, []))
        self.assertEqual(records[0]["independence"], "independent")
        self.assertNotIn("verification", records[0])

    def test_unclassified_reporting_stays_external(self):
        self.assertEqual(cited.omission(ref("s1", "https://example.org/x",
                                            independence="unknown")),
                         "unclassified_reference")

    def test_unsafe_urls_are_refused(self):
        for url in ("http://www.mod.go.jp/a", "https://u:p@www.mod.go.jp/a",
                    " https://www.mod.go.jp/a", None):
            self.assertEqual(cited.omission(ref("s1", url)), "unsafe_url", url)

    def test_mindef_is_never_a_cited_record(self):
        # The 2026-10-29 permission is for hyperlinks from a Brief, so even
        # the two approved links stay external rather than gain a page.
        for url in ("https://www.mindef.gov.sg/news/unapproved",) + tuple(APPROVED_MINDEF_LINKS):
            self.assertEqual(cited.omission(ref("s1", url)), "mindef_link_only_permission")

    def test_held_vietnam_families_are_omitted(self):
        for host in ("bocongan.gov.vn", "moit.gov.vn", "vanban.chinhphu.vn",
                     "datafiles.chinhphu.vn"):
            reason = cited.omission(ref("s1", "https://%s/doc" % host))
            self.assertTrue(reason and reason.startswith("held_source_family:"), host)
        self.assertIsNone(cited.omission(ref("s1", "https://baochinhphu.vn/doc")))

    def test_rights_holds_include_real_subdomains_but_not_lookalikes(self):
        for host in ("bocongan.gov.vn", "www.bocongan.gov.vn",
                     "notices.vanban.chinhphu.vn"):
            reason = cited.omission(ref("s1", "https://" + host + "/report"))
            self.assertTrue(reason and reason.startswith("held_source_family:"), host)
        for host in ("mindef.gov.sg", "news.mindef.gov.sg"):
            self.assertEqual(cited.omission(ref("s1", "https://" + host + "/report")),
                             "mindef_link_only_permission")
        self.assertIsNone(cited.omission(ref("s1", "https://false-mindef.gov.sg/report")))

    def test_incomplete_metadata_is_refused(self):
        self.assertEqual(cited.omission(ref("s1", "https://www.mod.go.jp/a", issuer=" ")),
                         "incomplete_metadata")


class ResolveTests(unittest.TestCase):
    def test_one_record_per_url_with_every_citing_brief(self):
        url = "https://www.mod.go.jp/shared.html"
        records, links, omitted, _ = cited.resolve(collection(
            brief("a", 1, [ref("s1", url)]),
            brief("b", 2, [ref("s4", url, original_title="Title s1")])))
        self.assertEqual(len(records), 1)
        self.assertEqual([c["slug"] for c in records[0]["cited_in"]], ["a", "b"])
        self.assertEqual(records[0]["cited_in"][1]["anchor"], "publisher-s4")
        self.assertEqual(links, {"a": {"s1": cited.cited_path(url)},
                                 "b": {"s4": cited.cited_path(url)}})
        self.assertEqual(omitted, [])

    def test_record_never_carries_verification_notes(self):
        records, _, _, _ = cited.resolve(collection(brief("a", 1, [ref("s1", "https://x.gov/a")])))
        self.assertNotIn("verification", records[0])
        self.assertNotIn("PRIVATE LOCATOR", repr(records[0]))

    def test_corpus_record_is_linked_not_duplicated(self):
        url = "https://www.mod.gov.cn/held.html"
        corpus = {"id": 42, "url": url, "in_trails": []}
        records, links, _, moved = cited.resolve(collection(brief("a", 1, [ref("s2", url)])),
                                                 corpus_by_url={url: corpus})
        self.assertEqual(records, [])
        self.assertEqual(links, {"a": {"s2": "record/42.html"}})
        # A route published before the URL was collected now redirects.
        self.assertEqual(moved, {cited.cited_path(url): "record/42.html"})
        self.assertEqual([(t["slug"], t["kind"], t["anchor"]) for t in corpus["in_trails"]],
                         [("a", "brief_reference", "publisher-s2")])

    def test_held_family_with_existing_public_record_converges_safely(self):
        url = "https://www.bocongan.gov.vn/a"
        existing = {"id": 84, "url": url, "in_trails": []}
        records, links, omitted, moved = cited.resolve(
            collection(brief("a", 1, [ref("s1", url)])),
            corpus_by_url={url: existing})
        self.assertEqual((records, omitted), ([], []))
        self.assertEqual(links["a"]["s1"], "record/84.html")
        self.assertEqual(moved[cited.cited_path(url)], "record/84.html")
        self.assertEqual(len(existing["in_trails"]), 1)

    def test_machine_record_is_linked_not_duplicated(self):
        url = "https://www.pna.gov.ph/a"
        records, links, _, _ = cited.resolve(
            collection(brief("a", 1, [ref("s1", url)])),
            machine_by_url={url: {"record_path": "record/m-1.html"}})
        self.assertEqual((records, links), ([], {"a": {"s1": "record/m-1.html"}}))

    def test_identity_ignores_host_case_and_fragment_only(self):
        url = "https://www.mod.go.jp/a/b.html"
        same = "HTTPS://WWW.MOD.GO.JP/a/b.html#section"
        self.assertEqual(cited.cited_id(url), cited.cited_id(same))
        self.assertNotEqual(cited.cited_id(url), cited.cited_id("https://www.mod.go.jp/A/b.html"))
        self.assertNotEqual(cited.cited_id(url), cited.cited_id(url + "?p=2"))
        records, links, _, moved = cited.resolve(
            collection(brief("a", 1, [ref("s1", "https://www.mod.go.jp/a/b.html#section")])),
            corpus_by_url={url: {"id": 7, "url": url, "in_trails": []}})
        self.assertEqual((records, links), ([], {"a": {"s1": "record/7.html"}}))

    def test_conflicting_metadata_stops_the_build(self):
        url = "https://www.mod.go.jp/shared.html"
        with self.assertRaisesRegex(ValueError, "cited_source_metadata_conflict"):
            cited.resolve(collection(brief("a", 1, [ref("s1", url)]),
                                     brief("b", 2, [ref("s1", url, date="2026-10-02")])))
        for field, value in (("publisher", "Other"), ("lang", "ja")):
            with self.assertRaisesRegex(ValueError, "cited_source_metadata_conflict"):
                cited.resolve(collection(brief("a", 1, [ref("s1", url)]),
                                         brief("b", 2, [ref("s1", url, **{field: value})])))

    def test_review_and_synthetic_briefs_are_skipped(self):
        review = brief("r", 1, [ref("s1", "https://x.gov/r")], is_review=True)
        synthetic = (brief("f", 2, [])[0], {"synthetic": True,
                     "publisher_references": [ref("s1", "https://x.gov/f")]})
        self.assertEqual(cited.resolve(collection(review, synthetic)), ([], {}, [], {}))

    def test_released_records_follow_their_published_citing_briefs(self):
        import tempfile
        shared, only_new = "https://x.gov/shared", "https://x.gov/new"
        records, _, _, _ = cited.resolve(collection(
            brief("old", 1, [ref("s1", shared)]),
            brief("new", 2, [ref("s1", shared), ref("s2", only_new)])))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(cited.released(records, root), [])
            (root / "briefs").mkdir()
            (root / "briefs/old.html").write_text("")
            self.assertEqual([r["url"] for r in cited.released(records, root)], [shared])
            (root / "briefs/new.html").write_text("")
            self.assertEqual(sorted(r["url"] for r in cited.released(records, root)),
                             sorted([shared, only_new]))


class ArchiveIndexTests(unittest.TestCase):
    def test_cited_record_replaces_unpaged_register_link_and_keeps_desks(self):
        url = "https://www.mod.go.jp/a.html"
        register = {"id": "o1", "record_type": "official_link", "source_url": url,
                    "ipr_url": "", "desks": ["japan"]}
        paged = {"id": "c9", "record_type": "archive_record", "source_url": url,
                 "ipr_url": "https://x/record/9.html", "desks": ["china"]}
        new = {"id": "cited:1", "record_type": "official_link", "source_url": url,
               "ipr_url": "https://x/record/cited-1.html", "desks": []}
        merged = with_cited([register, paged], [new])
        self.assertEqual([r["id"] for r in merged], ["c9", "cited:1"])
        self.assertEqual(merged[-1]["desks"], ["japan"])
        self.assertEqual(new["desks"], [])

    def test_archive_rows_publish_no_desk_coverage(self):
        records, _, _, _ = cited.resolve(collection(brief("a", 7, [ref("s1", "https://x.gov/a")])))
        row = next(cited.archive_rows(records))
        self.assertEqual((row["id"], row["desks"], row["record_type"], row["source_url"]),
                         ("cited:" + cited.cited_id("https://x.gov/a"), [], "official_link",
                          "https://x.gov/a"))
        self.assertIn("No. 7", row["processing"])

    def test_independent_archive_row_is_never_an_official_source(self):
        independent = ref("s1", "https://www.reuters.com/a", independence="independent")
        records, _, _, _ = cited.resolve(collection(brief("a", 1, [independent])))
        row = next(cited.archive_rows(records))
        self.assertEqual(row["record_type"], "independent_link")
        self.assertEqual(row["desks"], [])
        self.assertIsNone(row["text"])
        self.assertIsNone(row["summary"])
        self.assertIn("Independent-publication", row["processing"])


# The five approved Briefs this rule was first applied to. Their exact
# outcome is pinned so a regression in them is caught, while Briefs approved
# later are held only to the invariants in `check_every_reference_resolves`.
HISTORICAL_BRIEFS = frozenset((
    "japan-philippines-first-destroyer-2026",
    "japan-us-amraam-final-assembly-sm3-production",
    "bersama-lima-2026-five-power-coordination-at-sea",
    "three-days-chinese-flights-six-months-japanese-scrambles",
    "what-is-being-built-in-laos",
))
HISTORICAL_HELD = [("what-is-being-built-in-laos", "s3",
                    "held_source_family:vn_mps_foreign_affairs_vi")]


def approved_collection():
    return load_collection([], load_registry(), briefs_dir=ROOT / "briefs")


def subset(c, slugs):
    briefs = tuple(b for b in c.briefs if b["slug"] in slugs)
    return SimpleNamespace(briefs=briefs, sidecars={b["slug"]: c.sidecars[b["slug"]]
                                                    for b in briefs})


def cited_refs(c):
    return [(b["slug"], r) for b in c.briefs
            if not b.get("is_review") and not c.sidecars[b["slug"]].get("synthetic")
            for r in c.sidecars[b["slug"]].get("publisher_references") or ()]


def policy_hold(ref, reason):
    """True only for an omission the source-use policy itself requires.

    The standing is read again here rather than trusted from the reason, and
    any other omission (an unsafe URL, incomplete or unclassified metadata) is
    a defect in an approved Brief, not a hold.
    """
    host = (urlsplit(ref["url"]).hostname or "").lower()
    if reason == "mindef_link_only_permission":
        return cited._under(host, cited.MINDEF_HOSTS) is not None
    family = cited.HELD_HOSTS.get(cited._under(host, cited.HELD_HOSTS))
    return (family is not None and reason == "held_source_family:" + family
            and not vietnam_source_use.standing(family).allows("public_title_display"))


def check_every_reference_resolves(test, c):
    """Every reference in `c` reaches exactly one Record or a policy hold."""
    records, links, omitted, _ = cited.resolve(c)
    refs = cited_refs(c)
    outcomes = Counter([(slug, rid) for slug, ids in links.items() for rid in ids]
                       + [(slug, rid) for slug, rid, _, _ in omitted])
    test.assertEqual(outcomes, Counter((slug, r["id"]) for slug, r in refs),
                     "each reference must have exactly one outcome")
    held = {(slug, rid): reason for slug, rid, _, reason in omitted}
    by_path = {r["record_path"]: r for r in records}
    test.assertEqual(len(by_path), len(records))
    test.assertEqual(len({r["id"] for r in records}), len(records))
    citing = {}
    for slug, ref in refs:
        if (slug, ref["id"]) in held:
            reason = held[(slug, ref["id"])]
            test.assertTrue(policy_hold(ref, reason),
                            "%s %s omitted without a policy hold: %s" % (slug, ref["id"], reason))
            continue
        path = links[slug][ref["id"]]
        test.assertEqual(path, cited.cited_path(ref["url"]), (slug, ref["id"]))
        record = by_path[path]
        test.assertEqual(cited.url_key(record["url"]), cited.url_key(ref["url"]))
        test.assertEqual(record["independence"], ref["independence"], (slug, ref["id"]))
        citing.setdefault(path, set()).add((slug, "publisher-" + ref["id"]))
    test.assertEqual(set(by_path), set(citing), "every Record is cited and every link has one")
    for path, record in by_path.items():
        test.assertEqual({(x["slug"], x["anchor"]) for x in record["cited_in"]}, citing[path])
        test.assertIsNone(cited.omission(record))
        test.assertIn(record["independence"], ("official", "independent"))
        test.assertNotIn("verification", record)
    for row, record in zip(cited.archive_rows(records), records):
        test.assertEqual(row["record_type"], "official_link" if record["independence"] == "official"
                         else "independent_link")
        test.assertEqual(row["desks"], [])
    return records, links, omitted


class ApprovedBriefsTests(unittest.TestCase):
    """The actual approved Briefs: what is admitted and what is deliberately omitted."""

    @classmethod
    def setUpClass(cls):
        cls.collection = c = approved_collection()
        cls.records, cls.links, cls.omitted, cls.moved = cited.resolve(c)
        cls.locators = {r["url"]: r["verification"]["locator"]
                        for s in c.sidecars.values()
                        for r in s.get("publisher_references") or ()
                        if (r.get("verification") or {}).get("locator")}

    def test_every_reference_is_linked_or_explicitly_held(self):
        check_every_reference_resolves(self, self.collection)

    def test_historical_briefs_outcome_is_unchanged(self):
        c = subset(self.collection, HISTORICAL_BRIEFS)
        self.assertEqual({b["slug"] for b in c.briefs}, HISTORICAL_BRIEFS)
        records, links, omitted, _ = cited.resolve(c)
        self.assertEqual(len(cited_refs(c)), 34)
        self.assertEqual(len(records), 33)
        self.assertEqual(sum(len(v) for v in links.values()), 33)
        self.assertEqual(sum(r["independence"] == "independent" for r in records), 4)
        self.assertEqual([(slug, rid, reason) for slug, rid, _, reason in omitted],
                         HISTORICAL_HELD)

    def test_a_new_approved_brief_extends_rather_than_breaks_the_check(self):
        shared = next(r for _, r in cited_refs(self.collection)
                      if r["independence"] == "official")
        new_refs = [dict(shared, id="s1"),
                    ref("s2", "https://www.mod.go.jp/new.html"),
                    ref("s3", "https://www.reuters.com/new", independence="independent"),
                    ref("s4", "https://www.mindef.gov.sg/news/new"),
                    ref("s5", "https://bocongan.gov.vn/new")]
        entry, sidecar = brief("future-brief", 99, new_refs)
        grown = SimpleNamespace(briefs=self.collection.briefs + (entry,),
                                sidecars=dict(self.collection.sidecars, **{"future-brief": sidecar}))
        records, links, omitted = check_every_reference_resolves(self, grown)
        self.assertEqual(len(records), len(self.records) + 2)
        self.assertEqual(len(omitted), len(self.omitted) + 2)
        shared_record = next(r for r in records if r["url"] == shared["url"])
        self.assertEqual(shared_record["cited_in"][-1]["slug"], "future-brief")
        # Filtering before resolving keeps the pinned history independent of
        # later Briefs, even one citing the same URL.
        self.assertEqual(cited.resolve(subset(grown, HISTORICAL_BRIEFS))[:3],
                         cited.resolve(subset(approved_collection(), HISTORICAL_BRIEFS))[:3])
        # A defect in a future Brief is still a failure, not a hold.
        for bad in (ref("s6", "http://www.mod.go.jp/insecure.html"),
                    ref("s6", "https://www.mod.go.jp/x.html", issuer=" "),
                    ref("s6", "https://example.org/x", independence="unknown")):
            entry, sidecar = brief("future-brief", 99, new_refs + [bad])
            broken = SimpleNamespace(briefs=self.collection.briefs + (entry,),
                                     sidecars=dict(self.collection.sidecars,
                                                   **{"future-brief": sidecar}))
            with self.assertRaisesRegex(AssertionError, "without a policy hold"):
                check_every_reference_resolves(self, broken)

    def test_rendered_page_links_back_and_withholds_locators(self):
        env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                          autoescape=select_autoescape(["html"]))
        env.filters["reader_date"] = lambda v: v
        tmpl = env.get_template("_cited_source.html")
        for record in self.records:
            page = tmpl.render(record=record, cite=cited.citation(record, "https://o"))
            self.assertIn("Independent publication" if record["independence"] == "independent" else "Official source", page)
            self.assertIn('href="%s"' % record["url"].replace("&", "&amp;"), page)
            for c in record["cited_in"]:
                self.assertIn('href="../%s#%s"' % (c["url"], c["anchor"]), page)
            locator = self.locators.get(record["url"])
            if locator:
                self.assertNotIn(locator[:40], page)


if __name__ == "__main__":
    unittest.main()
