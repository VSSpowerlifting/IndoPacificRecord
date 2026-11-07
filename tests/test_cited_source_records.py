"""Official originals cited by approved Briefs become link-metadata Records."""
from pathlib import Path
from types import SimpleNamespace
import unittest

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core import cited_source_records as cited
from core.archive_research import with_cited
from core.brief_collection import load_collection
from core.desk_registry import load_registry

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

    def test_independent_reporting_stays_external(self):
        self.assertEqual(cited.omission(ref("s1", "https://www.reuters.com/x",
                                            independence="independent")),
                         "independent_reference")

    def test_unsafe_urls_are_refused(self):
        for url in ("http://www.mod.go.jp/a", "https://u:p@www.mod.go.jp/a",
                    " https://www.mod.go.jp/a", None):
            self.assertEqual(cited.omission(ref("s1", url)), "unsafe_url", url)

    def test_mindef_is_never_a_cited_record(self):
        # MINDEF permission covers hyperlinks only, so even official-host
        # links stay external rather than gain a Record page.
        for url in ("https://www.mindef.gov.sg/news/unapproved",
                    "https://www.mindef.gov.sg/news-and-events/latest-releases/23oct26-nr2/",
                    "https://www.mindef.gov.sg/news-and-events/latest-releases/4nov26-nr/"):
            self.assertEqual(cited.omission(ref("s1", url)), "mindef_link_only_permission")

    def test_held_vietnam_families_are_omitted(self):
        for host in ("bocongan.gov.vn", "moit.gov.vn", "vanban.chinhphu.vn",
                     "datafiles.chinhphu.vn"):
            reason = cited.omission(ref("s1", "https://%s/doc" % host))
            self.assertTrue(reason and reason.startswith("held_source_family:"), host)
        self.assertIsNone(cited.omission(ref("s1", "https://baochinhphu.vn/doc")))

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


class ApprovedBriefsTests(unittest.TestCase):
    """The actual approved Briefs: what is admitted and what is deliberately omitted."""

    @classmethod
    def setUpClass(cls):
        c = load_collection([], load_registry(), briefs_dir=ROOT / "briefs")
        cls.records, cls.links, cls.omitted, cls.moved = cited.resolve(c)
        cls.locators = {r["url"]: r["verification"]["locator"]
                        for s in c.sidecars.values()
                        for r in s.get("publisher_references") or ()
                        if (r.get("verification") or {}).get("locator")}

    def test_admission_counts(self):
        self.assertEqual(len(self.records), 29)
        self.assertEqual(sum(len(v) for v in self.links.values()), 29)
        self.assertEqual(len({r["id"] for r in self.records}), 29)

    def test_deliberate_omissions(self):
        reasons = sorted(o[3] for o in self.omitted)
        self.assertEqual(reasons, ["held_source_family:vn_mps_foreign_affairs_vi"]
                         + ["independent_reference"] * 4)

    def test_rendered_page_links_back_and_withholds_locators(self):
        env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                          autoescape=select_autoescape(["html"]))
        env.filters["reader_date"] = lambda v: v
        tmpl = env.get_template("_cited_source.html")
        for record in self.records:
            page = tmpl.render(record=record, cite=cited.citation(record, "https://o"))
            self.assertIn('href="%s"' % record["url"].replace("&", "&amp;"), page)
            for c in record["cited_in"]:
                self.assertIn('href="../%s#%s"' % (c["url"], c["anchor"]), page)
            locator = self.locators.get(record["url"])
            if locator:
                self.assertNotIn(locator[:40], page)


if __name__ == "__main__":
    unittest.main()
