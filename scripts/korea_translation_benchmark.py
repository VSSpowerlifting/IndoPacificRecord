#!/usr/bin/env python3
"""Run the Korean translation QA gate over the human-reviewed English releases.

Prints error categories (finding code, release, line number) and versions
only: no Korean or English text. This is a benchmark of the gate against the
reviewed standard, not a measure of model accuracy, and makes no model call.

    .venv/bin/python scripts/korea_translation_benchmark.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from processing import korea_translation_qa as qa  # noqa: E402

TEXTS = ROOT / "research" / "korea_published_original_texts"
REVIEWED = ROOT / "research" / "korea_english_reviewed"


def main() -> int:
    results = []
    for path in sorted(REVIEWED.glob("*.json")):
        reviewed = json.loads(path.read_text(encoding="utf-8"))
        text = (TEXTS / (path.stem + ".txt")).read_text(encoding="utf-8")
        entries = [{"index": t["index"], "text_en": t["text_en"]}
                   for t in reviewed["translations"]]
        results.append((path.stem, qa.check_translation(text, entries)))
    print("qa_version=%s glossary_version=%s releases=%d" % (
        qa.QA_VERSION, qa.glossary_version(), len(results)))
    for release, result in results:
        lines = ", ".join("%s@%s" % (f.code, f.line) for f in result.findings)
        print("%s %s %s" % (release, "pass" if result.passed else "held",
                            lines or "-"))
    for code, n in sorted(qa.category_counts(results).items()):
        print("category %s %d" % (code, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
