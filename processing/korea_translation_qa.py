"""Automated QA gate for Korean MND machine translation and analysis.

A deterministic check of one model result against its source-pinned Korean
original, before anything is written to `articles`. A record that fails is
held in the corpus ledger with machine reason codes; it never blocks another
record and nothing about it is published.

What this gate can establish is structural and lexical: line alignment,
copied numbers/dates/times/telephone numbers/designators, glossary terms,
header semantics (보도시점 vs 배포), absent PLA terminology, no added quotation
or agreement language, no injection or refusal traces, plausible size, and a
well-formed analysis. It does NOT establish semantic accuracy; the public
label says machine translation, not reviewed translation.

Reason codes are static ASCII (`[a-z0-9_]`), never source or model text, so
they are safe in logs and in the ledger's processing_reason column.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from core.korea_corpus_bridge import source_lines

QA_VERSION = "kr-qa-v2"
GUIDE_PATH = Path(__file__).resolve().parent.parent / "config" / "korea_translation_guide.json"

# Dispatch holds (decided before any paid call).
HOLD_SOURCE_LINES = "korea_source_line_breaks_unsupported"
HOLD_SOURCE_SIZE = "korea_source_too_large"


@lru_cache(maxsize=4)
def load_guide(path: str = str(GUIDE_PATH)) -> dict:
    with open(path, encoding="utf-8") as fh:
        guide = json.load(fh)
    if guide.get("schema") != "ipr-korea-translation-guide-v1":
        raise ValueError("korea translation guide schema mismatch")
    return guide


def glossary_version() -> str:
    return load_guide()["glossary_version"]


# ── normalisation ─────────────────────────────────────────────────────────────

_DASHES = re.compile("[‐‑‒–—―−]")


def _norm(text: str) -> str:
    """Dash and apostrophe variants folded; used only for comparisons."""
    return _DASHES.sub("-", text).replace("’", "'").replace("‘", "'")


def _value(raw: str, mult: int = 1):
    try:
        v = Decimal(raw.replace(",", "")) * mult
    except InvalidOperation:
        return None
    return int(v) if v == v.to_integral_value() else v.normalize()


_KO_UNITS = {"천": 10 ** 3, "만": 10 ** 4, "억": 10 ** 8, "조": 10 ** 12}
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_KO_GROUP = r"(?:%s)[천만억조]+" % _NUM
_KO_COMPOUND = re.compile(r"%s(?:\s*%s)*" % (_KO_GROUP, _KO_GROUP))
_KO_GROUP_RE = re.compile(r"(%s)([천만억조]+)" % _NUM)
_KO_DOTTED_DATE = re.compile(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?")
_KO_SHORT_DATE = re.compile(r"(?<![\d.])(\d{1,2})\.\s*(\d{1,2})\.(?=\s*\()")
_PLAIN = re.compile(_NUM)

_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}
_MONTH_ABBR = {"Jan.": 1, "Feb.": 2, "Mar.": 3, "Apr.": 4, "Aug.": 8,
               "Sep.": 9, "Sept.": 9, "Oct.": 10, "Nov.": 11, "Dec.": 12}
_EN_MONTH = re.compile(r"\b(%s)\b|(%s)" % (
    "|".join(_MONTHS), "|".join(re.escape(a) for a in _MONTH_ABBR)))
_EN_SCALE = {"thousand": 10 ** 3, "million": 10 ** 6, "billion": 10 ** 9,
             "trillion": 10 ** 12}
_EN_SCALED = re.compile(r"(%s)\s*(thousand|million|billion|trillion)\b" % _NUM)


def _exempt(text: str, patterns: Iterable[str]) -> str:
    for pat in patterns:
        text = re.sub(pat, " ", text)
    return text


def _number_exemptions(guide: dict):
    ko, en = [], []
    for entry in guide["glossary"]:
        if entry.get("number_exempt"):
            ko.append(entry["ko"])
            en.extend(re.escape(a) for a in entry["accepted"])
    return ko, en


def korean_numbers(line: str, guide: Optional[dict] = None) -> Counter:
    """Multiset of numeric values printed in a Korean line."""
    guide = guide or load_guide()
    text = _exempt(line, _number_exemptions(guide)[0])
    values: List = []

    def take(m):
        values.extend(int(g) for g in m.groups() if g)
        return " "

    text = _KO_DOTTED_DATE.sub(take, text)
    text = _KO_SHORT_DATE.sub(take, text)

    def compound(m):
        total = Decimal(0)
        for num, units in _KO_GROUP_RE.findall(m.group(0)):
            mult = 1
            for u in units:
                mult *= _KO_UNITS[u]
            total += Decimal(num.replace(",", "")) * mult
        values.append(int(total) if total == total.to_integral_value()
                      else total.normalize())
        return " "

    text = _KO_COMPOUND.sub(compound, text)
    values.extend(v for v in (_value(n) for n in _PLAIN.findall(text))
                  if v is not None)
    return Counter(values)


def english_numbers(line: str, guide: Optional[dict] = None) -> Counter:
    """Multiset of numeric values in an English line; month names count."""
    guide = guide or load_guide()
    text = _exempt(line, _number_exemptions(guide)[1])
    values: List = []

    def month(m):
        values.append(_MONTHS[m.group(1)] if m.group(1)
                      else _MONTH_ABBR[m.group(2)])
        return " "

    text = _EN_MONTH.sub(month, text)

    def scaled(m):
        v = _value(m.group(1), _EN_SCALE[m.group(2)])
        if v is not None:
            values.append(v)
        return " "

    text = _EN_SCALED.sub(scaled, text)
    values.extend(v for v in (_value(n) for n in _PLAIN.findall(text))
                  if v is not None)
    return Counter(values)


_WORD_NUMBERS = {w: i for i, w in enumerate(
    ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
     "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
     "sixteen", "seventeen", "eighteen", "nineteen", "twenty"])}
_WORD_NUMBERS.update({w: i for i, w in enumerate(
    ["first", "second", "third", "fourth", "fifth", "sixth", "seventh",
     "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth",
     "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth",
     "nineteenth", "twentieth"], start=1)})
_WORD_NUMBERS.update({"thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
                      "seventy": 70, "eighty": 80, "ninety": 90,
                      "hundred": 100, "dozen": 12})
_EN_WORD = re.compile(r"\b(%s)\b" % "|".join(_WORD_NUMBERS), re.I)


def english_number_words(line: str) -> Counter:
    """Spelled-out numbers ("nine siblings", "eighth degree").

    These may only COVER a Korean value, never count as added: "one of the"
    is not a fabricated figure.
    """
    return Counter(_WORD_NUMBERS[w.lower()] for w in _EN_WORD.findall(line))


_PHONE = re.compile(r"\(?0\d{1,2}\)?[-\s]?\d{3,4}-\d{4}")
_DESIGNATOR = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+|[A-Z]{1,4}\d+[A-Z0-9]*)"
    r"(?![A-Za-z0-9])")


def _quote_spans_ko(line: str) -> int:
    return (min(line.count("“"), line.count("”")) + line.count('"') // 2
            + min(line.count("‘"), line.count("’"))
            + min(line.count("「"), line.count("」"))
            + min(line.count("『"), line.count("』")))


_EN_SINGLE_SPAN = re.compile(
    r"(?:^|(?<=[\s(\[\-—–“\"]))['‘]"
    r"(?=\S)[^'‘’\n]*?\S['’](?=$|[\s.,;:!?)\]\-—–”\"…])")


def _quote_spans_en(line: str) -> int:
    doubles = min(line.count("“"), line.count("”")) + line.count('"') // 2
    return doubles + len(_EN_SINGLE_SPAN.findall(line))


def _compile_forbidden(patterns: Sequence[str]):
    # Acronym patterns (\b...) are case-sensitive so "plan" is not "PLAN".
    return [re.compile(p) if p.startswith("\\b") else re.compile(p, re.I)
            for p in patterns]


# ── findings ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Finding:
    code: str
    line: Optional[int] = None      # 1-based source line, None for document-level


@dataclass
class QAResult:
    findings: List[Finding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.findings

    @property
    def reasons(self) -> List[str]:
        return sorted({f.code for f in self.findings})

    def reason_string(self) -> str:
        return ",".join(self.reasons)


def dispatch_hold(text: str, *, max_output_tokens: int,
                  guide: Optional[dict] = None) -> Optional[str]:
    """A static reason to hold BEFORE any paid call, or None.

    Derived from the translation output ceiling: a document whose line-array
    output cannot fit would truncate on every attempt and spend the whole
    retry budget for nothing.
    """
    guide = guide or load_guide()
    lines = source_lines(text)
    if lines is None:
        return HOLD_SOURCE_LINES
    b = guide["bounds"]
    # Korean → English, JSON line array: ~1.2 output tokens per source
    # character plus ~25 tokens of per-line structure. Deliberately generous.
    expected = int(1.2 * len(text)) + 25 * len(lines)
    if (len(lines) > b["max_source_lines"] or len(text) > b["max_source_chars"]
            or expected > b["max_output_token_fraction"] * max_output_tokens):
        return HOLD_SOURCE_SIZE
    return None


def align(entries, n_lines: int) -> Optional[List[str]]:
    """English lines, or None unless exactly one per line, in source order.

    The tool contract asks for entries in order; an out-of-order list is a
    model that lost track of the lines, not a harmless permutation.
    """
    if not isinstance(entries, list) or len(entries) != n_lines:
        return None
    out: List[str] = []
    for position, e in enumerate(entries, 1):
        if not isinstance(e, dict):
            return None
        idx, text = e.get("index"), e.get("text_en")
        if (not isinstance(idx, int) or isinstance(idx, bool)
                or idx != position or not isinstance(text, str)):
            return None
        out.append(text)
    return out


# A shared view is not a signed agreement. These permissions are strictly
# *lexical*: the relevant Korean cue must be in the very same source line.
# The gate still cannot certify the whole translation's semantic accuracy.
_SHARED_VIEW_KO = ("공감", "동감", "인식을 같이", "견해를 같이",
                   "의견을 같이", "뜻을 같이")
_SHARED_VIEW_EN = re.compile(
    r"agree(?:d|s|ing)?\s+(?:with\b|that\b|on\s+(?:the\s+)?"
    r"(?:need|importance|necessity)\b)", re.I)
_CONTACT_DECISION_EN = re.compile(
    r"agree(?:d|s|ing)?\s+to\s+"
    r"(?:maintain|continue|keep(?:\s+up)?|enhance|strengthen)\s+"
    r"(?:close\s+)?(?:communications?|dialogue|contact)\b", re.I)
_CONCURRENCE_NOUN_PREFIX = re.compile(r"(?:expressed|voiced|indicated)\s+$", re.I)


def unsupported_agreement(ko: str, en: str, guide: dict) -> bool:
    """Check each English agreement claim against Korean line-level language.

    "Agreed with/that" may describe 공감, but it cannot authorize an
    unsupported decision, formal accord, treaty or deployment commitment.
    """
    if any(marker in ko for marker in guide["agreement_markers_ko"]):
        return False
    shared_view = any(marker in ko for marker in _SHARED_VIEW_KO)
    contact_decision = ("기로" in ko and
                        any(term in ko for term in ("소통", "대화", "연락")))
    normal = _norm(en)
    for match in re.finditer(guide["agreement_terms_en"], normal, re.I):
        term = match.group(0).lower()
        tail = normal[match.start():]
        if term in ("agree", "agreed", "agrees", "agreeing"):
            if shared_view and _SHARED_VIEW_EN.match(tail):
                continue
            if contact_decision and _CONTACT_DECISION_EN.match(tail):
                continue
        elif term == "agreement" and shared_view:
            before = normal[max(0, match.start()-32):match.start()]
            if (_CONCURRENCE_NOUN_PREFIX.search(before) and
                    re.match(r"agreement\s+with\b", tail, re.I)):
                continue
        return True
    return False


def check_translation(source_text: str, entries,
                      guide: Optional[dict] = None) -> QAResult:
    """Line-level and document-level checks of one line-aligned translation."""
    guide = guide or load_guide()
    result = QAResult()
    add = result.findings.append
    ko_lines = source_lines(source_text)
    if ko_lines is None:
        add(Finding(HOLD_SOURCE_LINES))
        return result
    en_lines = align(entries, len(ko_lines))
    if en_lines is None:
        add(Finding("qa_alignment"))
        return result

    glossary = [(re.compile(g["ko"]), [_norm(a).lower() for a in g["accepted"]])
                for g in guide["glossary"]]
    hdr_timing = guide["header_fields"]["보도시점"]
    injection = [re.compile(p, re.I) for p in guide["injection_patterns_en"]]
    b = guide["bounds"]

    for i, (ko, en) in enumerate(zip(ko_lines, en_lines), start=1):
        if not ko.strip():
            if en.strip():
                add(Finding("qa_blank_line_filled", i))
            continue
        if not en.strip():
            add(Finding("qa_empty_line", i))
            continue
        en_n = _norm(en)
        en_low = en_n.lower()

        ko_nums, en_nums = korean_numbers(ko, guide), english_numbers(en, guide)
        if ko_nums - en_nums - english_number_words(en):
            add(Finding("qa_number_missing", i))
        if en_nums - ko_nums:
            add(Finding("qa_number_added", i))
        for phone in _PHONE.findall(ko):
            if _norm(phone) not in en_n:
                add(Finding("qa_phone_altered", i))
        for des in _DESIGNATOR.findall(_norm(ko)):
            if des not in en_n:
                add(Finding("qa_designator_missing", i))
        for pattern, accepted in glossary:
            if pattern.search(ko) and not any(a in en_low for a in accepted):
                add(Finding("qa_glossary_term_missing", i))
        if "보도시점" in ko and "배포" not in ko:
            if (not any(r in en_low for r in hdr_timing["required_any"])
                    or any(f in en_low for f in hdr_timing["forbidden_any"])):
                add(Finding("qa_header_release_timing", i))
        if "배포" in ko and "distribut" not in en_low:
            add(Finding("qa_header_distribution", i))
        if _quote_spans_en(en) > _quote_spans_ko(ko):
            add(Finding("qa_quote_added", i))
        if unsupported_agreement(ko, en_n, guide):
            add(Finding("qa_agreement_unsupported", i))
        if any(p.search(en_n) for p in injection):
            add(Finding("qa_injection_trace", i))
        if len(en) > b["line_expansion_factor"] * len(ko) + b["line_expansion_slack"]:
            add(Finding("qa_line_expansion", i))

    if not any(m in source_text for m in guide["china_markers"]):
        joined = "\n".join(en_lines)
        if any(p.search(joined) for p in
               _compile_forbidden(guide["forbidden_without_china_marker"])):
            add(Finding("qa_pla_terminology"))

    ko_chars = sum(len(x.strip()) for x in ko_lines)
    en_chars = sum(len(x.strip()) for x in en_lines)
    if ko_chars and not (b["doc_char_ratio_min"] <= en_chars / ko_chars
                         <= b["doc_char_ratio_max"]):
        add(Finding("qa_size_ratio"))
    return result


def check_record(source_text: str, heading_index: int, result: dict,
                 guide: Optional[dict] = None) -> QAResult:
    """The full gate on one analyze() result for a Korean record.

    `heading_index` is the 0-based line index from document_heading().
    """
    guide = guide or load_guide()
    qa = check_translation(source_text, result.get("translation_entries"), guide)
    add = qa.findings.append
    lines = align(result.get("translation_entries"),
                  len(source_lines(source_text) or []))

    if lines is not None:
        if (not 0 <= heading_index < len(lines)
                or result.get("title_english") != lines[heading_index].strip()):
            add(Finding("qa_title_mismatch"))
        if result.get("text_english") != "\n".join(lines):
            add(Finding("qa_schema"))

    summary = result.get("summary_english")
    score = result.get("relevance_score")
    if (not isinstance(summary, str) or not summary.strip()
            or len(summary) > guide["bounds"]["summary_max_chars"]
            or not isinstance(result.get("is_significant"), bool)
            or result.get("categories") != []
            or isinstance(score, bool) or not isinstance(score, (int, float))
            or not 0.0 <= float(score) <= 1.0):
        add(Finding("qa_schema"))
        return qa

    s_norm = _norm(summary)
    if not any(c.lower() in s_norm.lower() for c in guide["attribution_cues_en"]):
        add(Finding("qa_summary_unattributed"))
    if lines is not None:
        supported = set(english_numbers("\n".join(lines), guide))
        if set(english_numbers(summary, guide)) - supported:
            add(Finding("qa_summary_number_unsupported"))
    if unsupported_agreement(source_text, s_norm, guide):
        add(Finding("qa_summary_agreement_unsupported"))
    if (not any(m in source_text for m in guide["china_markers"])
            and any(p.search(s_norm) for p in
                    _compile_forbidden(guide["forbidden_without_china_marker"]))):
        add(Finding("qa_summary_pla_terminology"))
    if any(re.search(p, s_norm, re.I) for p in guide["injection_patterns_en"]):
        add(Finding("qa_injection_trace"))
    return qa


def category_counts(results: Iterable[Tuple[str, QAResult]]) -> Counter:
    """Error categories across a benchmark (counts of findings per code)."""
    counts: Counter = Counter()
    for _, r in results:
        counts.update(f.code for f in r.findings)
    return counts
