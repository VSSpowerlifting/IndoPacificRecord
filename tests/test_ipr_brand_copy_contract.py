"""Guard current IPR pages against repeated predecessor-brand explanations.

Historical issue titles and citations remain unchanged in their source records.
This contract is limited to the current presentation templates.
"""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "site" / "preview" / "templates"
CURRENT_PAGES = ("about.html", "desk.html", "analysis.html", "pla_watch.html")


def public_template_copy(name: str) -> str:
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    return re.sub(r"\{#-?.*?-?#\}", "", text, flags=re.DOTALL)


class IPRBrandCopyContract(unittest.TestCase):
    def test_current_pages_do_not_explain_old_brand_names(self):
        for name in CURRENT_PAGES:
            with self.subTest(template=name):
                text = public_template_copy(name)
                self.assertNotIn("China Mil Watch", text)
                self.assertNotIn("The PLA Watch", text)
                self.assertNotRegex(text, r"\{\{\s*predecessor_(?:name|series)\s*\}\}")

    def test_compatibility_citation_anchors_survive(self):
        text = public_template_copy("pla_watch.html")
        self.assertIn('id="{{ item.anchor }}"', text)
        self.assertIn("{{ item.citation }}", text)
        self.assertIn("/the-pla-watch/archive.html", text)

    def test_analysis_preserves_source_provenance_for_current_briefs(self):
        text = public_template_copy("analysis.html")
        self.assertIn("row.kind == 'issue'", text)
        self.assertIn("{{ row.provenance }}", text)


if __name__ == "__main__":
    unittest.main()
