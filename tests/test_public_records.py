"""One admitted source publication is one public record, on every surface.

The unit cases pin the grouping rules in ``core.public_records``: exact
identities only, a URL mismatch or a duplicate component type is reported and
left apart, and Briefs and dossiers never count. The build case renders the
tracked database once and reconciles each desk's count across the Archive
index, the Desks directory, the desk page, home and the Archive filter.
"""
from __future__ import annotations

import json
import re
import unittest

from bs4 import BeautifulSoup

from core.public_records import group, project
from tests.test_desk_rollout_contract import DeskCase


def rec(rid, kind, url, desks=("x",), date=None, date_kind=None, source="S"):
    return {"id": rid, "record_type": kind, "source_url": url, "desks": list(desks),
            "date": date, "date_kind": date_kind, "source": source,
            "ipr_url": None if kind == "official_link" else rid.replace(":", "/") + ".html"}


class Grouping(unittest.TestCase):
    def test_link_and_explanation_of_one_publication_count_once(self):
        records = [rec("official:afp:1", "official_link", "https://a/1"),
                   rec("machine:afp:1", "machine_explanation", "https://a/1")]
        out = project(records, ["x"])
        self.assertEqual(out["desks"]["x"]["records"], 1)
        self.assertEqual(out["lead"], {"machine:afp:1": "official:afp:1"})
        self.assertEqual(out["parts"]["official:afp:1"][0][0], "Machine explanation")
        self.assertEqual(out["unresolved"], [])

    def test_url_mismatch_is_reported_and_never_merged(self):
        records = [rec("official:afp:1", "official_link", "https://a/1"),
                   rec("machine:afp:1", "machine_explanation", "https://a/other")]
        groups, unresolved = group(records)
        self.assertEqual(len(groups), 2)
        self.assertEqual(unresolved[0]["reason"], "official URL mismatch")

    def test_two_components_of_one_type_stay_apart(self):
        records = [rec("official:afp:1", "official_link", "https://a/1"),
                   rec("official:afp:1", "official_link", "https://a/1")]
        groups, unresolved = group(records)
        self.assertEqual(len(groups), 2)
        self.assertEqual(unresolved[0]["reason"], "two components of one type")

    def test_corpus_record_joins_only_through_a_verified_binding(self):
        link = rec("official:vn:7", "official_link", "https://v/7")
        corpus = rec("record:42", "archive_record", None)
        self.assertEqual(len(group([link, corpus])[0]), 2)
        groups, unresolved = group([link, corpus], bindings={42: "vn:7"},
                                   corpus_urls={42: "https://v/7"})
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0][0]["id"], "record:42")      # the IPR record leads
        groups, unresolved = group([link, corpus], bindings={42: "vn:7"},
                                   corpus_urls={42: "https://v/elsewhere"})
        self.assertEqual(len(groups), 2)
        self.assertEqual(unresolved[0]["reason"], "official URL mismatch")

    def test_same_url_under_two_identities_is_reported_not_merged(self):
        records = [rec("official:afp:1", "official_link", "https://a/1"),
                   rec("official:nsc:9", "official_link", "https://a/1")]
        out = project(records, ["x"])
        self.assertEqual(out["desks"]["x"]["records"], 2)
        self.assertEqual(out["shared_url"], [["official:afp:1", "official:nsc:9"]])

    def test_briefs_and_dossiers_are_not_source_records(self):
        records = [rec("brief:1", "human_analysis", None),
                   rec("dossier:1", "living_dossier", None),
                   rec("official:afp:1", "official_link", "https://a/1")]
        out = project(records, ["x"])
        self.assertEqual(out["total"], 1)
        self.assertEqual(sorted(out["analysis"]), ["brief:1", "dossier:1"])

    def test_sources_and_latest_date_keep_their_labels(self):
        records = [rec("official:a:1", "official_link", "https://a/1", source="MOD RSS",
                       date="2026-10-02",
                       date_kind="RSS pubDate (not independently verified document issue date)"),
                   rec("official:b:1", "official_link", "https://b/1", source="Other",
                       date="2026-10-01", date_kind="publisher-posted date")]
        desk = project(records, ["x"])["desks"]["x"]
        self.assertEqual(desk["sources"], {"MOD RSS": 1, "Other": 1})
        self.assertEqual(desk["latest"], "2026-10-02")
        self.assertEqual(desk["latest_label"], "RSS listing date, not verified issue date")


class SurfacesAgree(DeskCase):
    """Every public surface shows the projection's count for every desk."""

    def projection(self):
        return json.loads(self.page("archive-research-index.json"))["public_records"]

    def test_counts_reconcile_across_surfaces(self):
        pr = self.projection()
        directory = self.page("desks.html")
        home = BeautifulSoup(self.page("index.html"), "html.parser")
        archive = BeautifulSoup(self.page("archive.html"), "html.parser")
        # Recount independently: a lead is any source record not folded into
        # another record's components. Each lead counts once per desk it names.
        index = json.loads(self.page("archive-research-index.json"))
        leads = [r for r in index["records"]
                 if r["id"] not in pr["lead"] and r["id"] not in pr["analysis"]]
        self.assertEqual(pr["total"], len(leads))
        for slug, desk in pr["desks"].items():
            self.assertEqual(desk["records"], sum(slug in r["desks"] for r in leads))
        for slug, desk in pr["desks"].items():
            n = format(desk["records"], ",")
            with self.subTest(desk=slug):
                plate = re.search(r'<section class="desk[^"]*"[^>]*data-desk="%s".*?</section>' % slug,
                                  directory, re.S).group(0)
                self.assertIn("<dt>Records</dt><dd>%s</dd>" % n, plate)
                self.assertIn("Records</dt><dd>%s</dd>" % n, self.page(slug + ".html"))
                option = archive.select_one('#f-desk option[value="%s"]' % slug)
                if desk["records"]:
                    self.assertIn("(%s records)" % n, option.get_text())
                    link = home.select_one('.home-desk-list a[href="%s.html"]' % slug)
                    self.assertIn("%s public records" % n, link.get_text(" "))

    def test_nothing_unresolved_and_no_url_shared_by_two_records(self):
        pr = self.projection()
        self.assertEqual(pr["unresolved"], [])
        self.assertEqual(pr["shared_url"], [])

    def test_held_korea_records_stay_out(self):
        index = json.loads(self.page("archive-research-index.json"))
        ids = {r["id"] for r in index["records"]}
        for held in (5457, 5458, 5520):
            self.assertNotIn("record:%d" % held, ids)
            self.assertNotIn("record/%d.html" % held, self.page("korea.html"))

    def test_japan_dates_say_what_they_are(self):
        pr = self.projection()
        self.assertEqual(pr["desks"]["japan"]["latest_label"],
                         "RSS listing date, not verified issue date")
        self.assertIn("RSS listing date, not verified issue date", self.page("japan.html"))

    def test_link_components_carry_no_source_text(self):
        # Grouping adds no field: a link component keeps the adapter's
        # metadata-only shape even when it now heads a public record.
        index = json.loads(self.page("archive-research-index.json"))
        for r in index["records"]:
            if r["record_type"] == "official_link":
                with self.subTest(record=r["id"]):
                    self.assertIsNone(r["summary"])
                    self.assertIsNone(r["text"])


if __name__ == "__main__":
    unittest.main()
