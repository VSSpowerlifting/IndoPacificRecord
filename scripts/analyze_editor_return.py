"""Offline comparison of a Sunday worksheet with its editor's returned version.

Reads the TXT worksheet Ben sent and Dylan's returned TXT (or Word file, which
is reconstructed through the existing importer) and writes a private report of
editing patterns for OWNER REVIEW: which paragraphs were kept, tightened,
rewritten, moved or cut; which source-bearing blocks changed enough to need a
fresh check against their records; figures that appeared or vanished; and which
heuristic flags the edit resolved or introduced.

This tool never reads mail, calls a model, edits the prompt or the prose
standard, or imports anything into briefs/. One return is an observation, not
a rule: patterns recorded here stay candidates until the owner decides to adopt
one in ``docs/IPR_BRIEFS_WRITING_STANDARD.md`` and the writer prompt.

The report quotes short fragments of the private manuscript, so it refuses to
write inside the repository.

Usage:
    python -m scripts.analyze_editor_return --original sent.txt \
        --edited returned.txt --out /private/analysis.md [--json-out a.json]
    python -m scripts.analyze_editor_return --aggregate a.json b.json c.json
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
from pathlib import Path

from core.brief_prose_standard import (
    HEDGE_PATTERNS, STOCK_PATTERNS, check_article, fingerprint, sentences, words)
from scripts.sunday_editor_readable import (
    ARTICLE_KEY, BLOCK_LINE, HEADINGS, split_article)
from scripts.validate_editorial_return import (
    ReturnValidationError, _load, _sections, _split, validate_return)

SCHEMA = "ipr-editor-return-analysis/1"
REPO_ROOT = Path(__file__).resolve().parents[1]
LIGHT, MATCH = 0.80, 0.45
RECURRING_AFTER = 3
CITATION_PREFIXES = ("SOURCE RECORD IDS:", "EXTERNAL SOURCE IDS:")
NUMBER = re.compile(r"\b\d[\d,.]*\d\b|\b\d\b")
QUOTED = re.compile(r"[\"“]([^\"”]{12,}?)[\"”]")
RECONCILIATION_STATEMENT = (
    "A passing validate_return and an unchanged source appendix prove structure only. They are NOT "
    "factual, citation or editorial approval of the returned text. The appendix describes the ORIGINAL "
    "paragraphs; a rewritten, added, merged or moved paragraph is unverified until Ben has checked each "
    "claim, figure, name, date and quotation in it against the original records and assigned its citations again.")
PROSE_SECTIONS = tuple(h for h in HEADINGS if h not in ("WORKING TITLE", "DEK"))


def _units(sections):
    """Ordered ``(kind, text, section)`` units from the editable sections."""
    body = dict(sections)
    units = []
    if ARTICLE_KEY in body:
        for kind, text in split_article(body[ARTICLE_KEY]):
            units.append((kind, text, ARTICLE_KEY))
        return "article-first", units
    for key in PROSE_SECTIONS:
        if key not in body:
            continue
        kept = [line for line in body[key].splitlines() if not line.startswith(CITATION_PREFIXES)]
        for chunk in re.split(r"\n\s*\n", "\n".join(kept)):
            if chunk.strip():
                units.append(("para", chunk.strip(), key))
    return "fixed-outline", units


def _parse(text):
    header, manuscript, appendix = _split(text)
    sections = _sections(manuscript)
    layout, units = _units(sections)
    return {"header": header, "appendix": appendix, "sections": dict(sections),
            "layout": layout, "units": units}


def _blocks(units):
    """Group units into article-shaped blocks (a block per subhead or per section)."""
    blocks, heading, paras, current = [], "", [], None
    for kind, text, section in units:
        starts_block = kind == "subhead" or (section != ARTICLE_KEY and section != current)
        if starts_block and paras:
            blocks.append({"heading": heading, "text": "\n\n".join(paras), "citations": []})
            paras = []
        if kind == "subhead":
            heading = text
            continue
        if starts_block:
            heading = "" if section == ARTICLE_KEY else section.title()
        current = section
        paras.append(text)
    if paras:
        blocks.append({"heading": heading, "text": "\n\n".join(paras), "citations": []})
    return blocks


def _paragraphs(units):
    return [text for kind, text, _ in units if kind == "para"]


def _ratio(a, b):
    a, b = a.casefold(), b.casefold()
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if matcher.real_quick_ratio() < MATCH or matcher.quick_ratio() < MATCH:
        return 0.0
    return matcher.ratio()


def match_paragraphs(old, new):
    """Greedy global best-match. Returns (pairs[(i, j, ratio)], deleted, added)."""
    scored = sorted(((_ratio(a, b), i, j) for i, a in enumerate(old) for j, b in enumerate(new)),
                    reverse=True)
    used_old, used_new, pairs = set(), set(), []
    for ratio, i, j in scored:
        if ratio < MATCH or i in used_old or j in used_new:
            continue
        used_old.add(i)
        used_new.add(j)
        pairs.append((i, j, ratio))
    pairs.sort()
    deleted = [i for i in range(len(old)) if i not in used_old]
    added = [j for j in range(len(new)) if j not in used_new]
    return pairs, deleted, added


def _moved(pairs):
    """Original indices of pairs outside one longest order-preserving run."""
    sequence = [j for _, j, _ in pairs]
    n = len(sequence)
    if not n:
        return set()
    length, prev = [1] * n, [-1] * n
    for i in range(n):
        for j in range(i):
            if sequence[j] < sequence[i] and length[j] + 1 > length[i]:
                length[i], prev[i] = length[j] + 1, j
    k = max(range(n), key=length.__getitem__)
    keep = set()
    while k != -1:
        keep.add(k)
        k = prev[k]
    return {pairs[k][0] for k in range(n) if k not in keep}


def _spans(old_units, accounting):
    """Map accounting blocks to original paragraph index spans by fingerprint."""
    paras = _paragraphs(old_units)
    spans, cursor = [], 0
    for number, fp, records, external in accounting:
        found = None
        for size in range(1, 5):
            chunk = paras[cursor:cursor + size]
            if len(chunk) == size and fingerprint("\n\n".join(chunk)) == fp:
                found = (cursor, cursor + size)
                break
        if found:
            cursor = found[1]
        spans.append({"block": number, "span": found, "records": records, "external": external})
    return spans


def _accounting(appendix):
    out = []
    for m in BLOCK_LINE.finditer(appendix):
        out.append((int(m.group(1)), m.group(2),
                    [] if m.group(3) == "none" else m.group(3).split(", "),
                    [] if m.group(4) == "none" else m.group(4).split(", ")))
    return out


def _pattern_counts(text):
    hedges = sum(len(rx.findall(text)) for _, rx in HEDGE_PATTERNS)
    stock = sum(len(rx.findall(text)) for _, rx in STOCK_PATTERNS)
    sents = sentences(text)
    mean = (sum(len(words(s)) for s in sents) / len(sents)) if sents else 0.0
    return {"hedges": hedges, "stock": stock, "dashes": text.count("—"),
            "mean_sentence": round(mean, 1), "words": len(words(text))}


def _snippet(text, n=12):
    tokens = text.split()
    return " ".join(tokens[:n]) + (" …" if len(tokens) > n else "")


def analyze(original, edited):
    """Compare two validated worksheet texts; returns a JSON-serializable report."""
    receipt = validate_return(original, edited)
    old, new = _parse(original), _parse(edited)
    old_paras, new_paras = _paragraphs(old["units"]), _paragraphs(new["units"])
    pairs, deleted, added = match_paragraphs(old_paras, new_paras)
    moved = _moved(pairs)
    status = {}
    for i, j, ratio in pairs:
        # Similarity finds corresponding paragraphs, never factual equivalence:
        # even a one-word actor/negation change must be reconciled to its source.
        status[i] = ("unchanged" if old_paras[i] == new_paras[j] else "tightened-or-lightly-edited"
                     if ratio >= LIGHT else "rewritten")
        if i in moved:
            status[i] += "+moved"
    for i in deleted:
        status[i] = "cut-or-merged"

    old_text, new_text = "\n\n".join(old_paras), "\n\n".join(new_paras)
    before, after = _pattern_counts(old_text), _pattern_counts(new_text)

    report_old = check_article({"article": _blocks(old["units"])})
    report_new = check_article({"article": _blocks(new["units"])})
    old_flags = {f["code"] for f in report_old["flags"]}
    new_flags = {f["code"] for f in report_new["flags"]}

    old_nums, new_nums = set(NUMBER.findall(old_text)), set(NUMBER.findall(new_text))

    cited = []
    if old["layout"] == "article-first":
        for entry in _spans(old["units"], _accounting(old["appendix"])):
            span = entry["span"]
            parts = [status[i] for i in range(*span)] if span else []
            if not span:
                verdict = "unmapped (check manually)"
            elif all(p == "unchanged" for p in parts):
                verdict = "intact"
            elif any(p.startswith("cut") for p in parts):
                verdict = "partly or wholly cut or merged"
            elif any(p.startswith("rewritten") for p in parts):
                verdict = "rewritten: re-check claims against the cited records"
            elif any("moved" in p for p in parts):
                verdict = "moved or lightly edited"
            else:
                verdict = "lightly edited"
            cited.append({"block": entry["block"], "records": entry["records"],
                          "external": entry["external"], "verdict": verdict})

    old_quotes, new_quotes = set(QUOTED.findall(old_text)), set(QUOTED.findall(new_text))
    items = []
    for entry in cited:
        if entry["verdict"] != "intact":
            items.append({"kind": "cited_block", "where": "block {}".format(entry["block"]),
                          "records": entry["records"], "external": entry["external"],
                          "reason": entry["verdict"]})
    if old["layout"] != "article-first":
        touched = [i + 1 for i, v in sorted(status.items()) if v != "unchanged"]
        if touched:
            items.append({"kind": "edited_paragraphs", "where": "paragraphs " + ", ".join(map(str, touched)),
                          "reason": "edited, moved or cut in a fixed-outline worksheet; re-check against its SOURCE RECORD IDS"})
    for j in added:
        items.append({"kind": "added_paragraph", "where": "returned paragraph {}".format(j + 1),
                      "reason": "new text with no citation mapping"})
    if old["sections"].get("WORKING TITLE") != new["sections"].get("WORKING TITLE"):
        items.append({"kind": "title", "where": "title", "reason": "changed; confirm it claims no more than the records"})
    if old["sections"].get("DEK") != new["sections"].get("DEK"):
        items.append({"kind": "dek", "where": "dek", "reason": "changed; confirm it claims no more than the records"})
    if new_nums - old_nums:
        items.append({"kind": "new_figures", "where": "article",
                      "reason": "figures absent from the sent text: " + ", ".join(sorted(new_nums - old_nums))})
    if new_quotes - old_quotes:
        items.append({"kind": "new_quotations", "where": "article",
                      "reason": "{} quotation(s) absent from the sent text; verify wording against the original".format(
                          len(new_quotes - old_quotes))})
    reconciliation = {"required": True, "items": items, "factual_approval": False,
                      "validate_return_is_factual_approval": False, "statement": RECONCILIATION_STATEMENT}

    old_subs = [t for k, t, _ in old["units"] if k == "subhead"]
    new_subs = [t for k, t, _ in new["units"] if k == "subhead"]
    cut_pct = round(100.0 * (after["words"] - before["words"]) / before["words"], 1) if before["words"] else 0.0
    candidates = []

    def candidate(code, observation, count=1):
        candidates.append({"code": code, "observation": observation, "count": count})

    if before["mean_sentence"] and after["mean_sentence"] <= 0.85 * before["mean_sentence"]:
        candidate("shortened_sentences", "mean sentence length fell {} -> {} words".format(
            before["mean_sentence"], after["mean_sentence"]))
    if after["hedges"] < before["hedges"]:
        candidate("removed_caveat_formulas", "{} -> {} stock caveat formulas".format(
            before["hedges"], after["hedges"]), before["hedges"] - after["hedges"])
    if after["hedges"] > before["hedges"]:
        candidate("added_caveat_formulas", "{} -> {} caveat formulas (editor added qualification)".format(
            before["hedges"], after["hedges"]), after["hedges"] - before["hedges"])
    if after["stock"] < before["stock"]:
        candidate("removed_stock_phrasing", "{} -> {} stock significance/contrast phrases".format(
            before["stock"], after["stock"]), before["stock"] - after["stock"])
    if after["dashes"] < before["dashes"]:
        candidate("removed_em_dashes", "{} -> {} em dashes".format(before["dashes"], after["dashes"]),
                  before["dashes"] - after["dashes"])
    if cut_pct <= -10:
        candidate("cut_length", "article {}% in words".format(cut_pct))
    if cut_pct >= 10:
        candidate("added_length", "article +{}% in words".format(cut_pct))
    rewritten = sum(1 for v in status.values() if v.startswith("rewritten"))
    if rewritten:
        candidate("rewritten_paragraphs", "{} of {} original paragraphs substantially rewritten".format(
            rewritten, len(old_paras)), rewritten)
    if deleted:
        candidate("cut_paragraphs", "{} paragraph(s) cut or merged".format(len(deleted)), len(deleted))
    if moved:
        candidate("reordered_paragraphs", "{} paragraph(s) moved".format(len(moved)), len(moved))
    if old_paras and pairs and pairs[0][0] == 0 and _ratio(old_paras[0], new_paras[pairs[0][1]]) < LIGHT:
        candidate("lead_rewritten", "the opening paragraph was substantially rewritten")
    elif old_paras and 0 in deleted:
        candidate("lead_rewritten", "the opening paragraph was cut or merged")
    if set(old_subs) != set(new_subs):
        candidate("subheads_changed", "subheads {} -> {}".format(len(old_subs), len(new_subs)),
                  abs(len(new_subs) - len(old_subs)) or 1)
    for code in sorted(old_flags - new_flags):
        candidate("resolved_flag:" + code, "heuristic flag {} no longer fires after the edit".format(code))
    for code in sorted(new_flags - old_flags):
        candidate("introduced_flag:" + code, "heuristic flag {} fires only after the edit".format(code))

    return {
        "schema": SCHEMA,
        "packet": receipt["packet"], "layout": old["layout"],
        "validation": {"changed_sections": receipt["changed_sections"],
                       "appendix_sha256": receipt["appendix_sha256"]},
        "counts": {"original_paragraphs": len(old_paras), "returned_paragraphs": len(new_paras),
                   "unchanged": sum(1 for v in status.values() if v == "unchanged"),
                   "lightly_edited": sum(1 for v in status.values() if v.startswith("tightened")),
                   "rewritten": rewritten, "cut_or_merged": len(deleted),
                   "added": len(added), "moved": len(moved)},
        "words": {"before": before["words"], "after": after["words"], "change_pct": cut_pct},
        "style_counts": {"before": before, "after": after},
        "title_changed": old["sections"].get("WORKING TITLE") != new["sections"].get("WORKING TITLE"),
        "dek_changed": old["sections"].get("DEK") != new["sections"].get("DEK"),
        "figures": {"new_in_returned": sorted(new_nums - old_nums),
                    "missing_from_returned": sorted(old_nums - new_nums)},
        "added_paragraphs": [{"index": j + 1, "starts": _snippet(new_paras[j])} for j in added],
        "cut_paragraphs": [{"index": i + 1, "starts": _snippet(old_paras[i])} for i in deleted],
        "cited_blocks": cited,
        "reconciliation": reconciliation,
        "heuristic_flags": {"original": sorted(old_flags), "returned": sorted(new_flags)},
        "candidate_patterns": candidates,
        "governance": {
            "auto_ingested_correspondence": False, "model_called": False,
            "prompt_or_standard_changed": False,
            "promotion_rule": ("Observations only. A pattern becomes a writing rule only after the "
                               "owner records it in docs/IPR_BRIEFS_WRITING_STANDARD.md; one return "
                               "never changes the prompt."),
        },
    }


def render_markdown(report):
    c = report["counts"]
    lines = [
        "# Editor-return analysis — private, owner review only",
        "",
        "{} · layout {} · words {} -> {} ({:+}%)".format(
            report["packet"], report["layout"], report["words"]["before"],
            report["words"]["after"], report["words"]["change_pct"]),
        "",
        "Paragraphs: {original_paragraphs} sent, {returned_paragraphs} returned; {unchanged} unchanged, "
        "{lightly_edited} lightly edited, {rewritten} rewritten, {cut_or_merged} cut or merged, "
        "{added} added, {moved} moved.".format(**c),
        "Title changed: {}. Dek changed: {}.".format(report["title_changed"], report["dek_changed"]),
        "",
    ]
    rec = report["reconciliation"]
    lines += ["## Reconciliation required before any Brief", rec["statement"], ""]
    lines += ["- {} ({}): {}".format(i["where"], i["kind"], i["reason"]) for i in rec["items"]] or [
        "- No paragraph, title, figure or quotation changed; the sent text still needs Ben's own review."]
    lines.append("")
    if report["cited_blocks"]:
        lines.append("## Source-bearing blocks (re-check before any Brief)")
        for b in report["cited_blocks"]:
            lines.append("- Block {} (records {}; external {}): {}".format(
                b["block"], ", ".join(b["records"]) or "none",
                ", ".join(b["external"]) or "none", b["verdict"]))
        lines.append("")
    f = report["figures"]
    lines.append("## Figures")
    lines.append("- New in the returned text (verify against records): " + (", ".join(f["new_in_returned"]) or "none"))
    lines.append("- Present in the sent text but not returned: " + (", ".join(f["missing_from_returned"]) or "none"))
    if report["added_paragraphs"]:
        lines += ["", "## Paragraphs the editor added (no citation mapping; Ben verifies any new claim)"]
        lines += ["- #{}: {}".format(a["index"], a["starts"]) for a in report["added_paragraphs"]]
    if report["cut_paragraphs"]:
        lines += ["", "## Paragraphs cut or merged"]
        lines += ["- #{}: {}".format(a["index"], a["starts"]) for a in report["cut_paragraphs"]]
    lines += ["", "## Candidate patterns (observations, not rules)"]
    lines += ["- {}: {}".format(p["code"], p["observation"]) for p in report["candidate_patterns"]] or ["- none"]
    lines += ["", "## Governance", report["governance"]["promotion_rule"],
              "No correspondence was read, no model was called, and no prompt or standard was changed.", ""]
    return "\n".join(lines)


def aggregate(reports):
    """Count candidate patterns across returns; recurrence is evidence, not approval."""
    seen = {}
    for report in reports:
        if report.get("schema") != SCHEMA:
            raise ValueError("not an editor-return analysis report")
        for code in {p["code"] for p in report["candidate_patterns"]}:
            seen[code] = seen.get(code, 0) + 1
    return [{"code": code, "returns_observed": count,
             "status": ("recurring: eligible for owner consideration"
                        if count >= RECURRING_AFTER else "isolated observation"),
             "promoted": False}
            for code, count in sorted(seen.items(), key=lambda item: (-item[1], item[0]))]


def _private_output(path):
    resolved = path.resolve()
    if REPO_ROOT == resolved or REPO_ROOT in resolved.parents:
        raise ValueError("refusing to write a private manuscript analysis inside the repository")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return os.fdopen(fd, "w", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--original", type=Path, help="the unchanged worksheet TXT sent to the editor")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--edited", type=Path, help="the editor's returned TXT")
    group.add_argument("--edited-word", type=Path, help="the editor's returned DOCX")
    parser.add_argument("--out", type=Path, help="new private Markdown report (outside the repository)")
    parser.add_argument("--json-out", type=Path, help="new private JSON report")
    parser.add_argument("--aggregate", nargs="+", type=Path, help="JSON reports to count patterns across")
    args = parser.parse_args(argv)
    try:
        if args.aggregate:
            rows = aggregate([json.loads(p.read_text(encoding="utf-8")) for p in args.aggregate])
            for row in rows:
                print("{returns_observed:>2}  {code}  [{status}]".format(**row))
            print("No pattern was promoted; adopting a rule needs explicit owner approval.")
            return 0
        if not (args.original and (args.edited or args.edited_word) and (args.out or args.json_out)):
            parser.error("--original, an edited file and --out/--json-out are required")
        original = _load(args.original)
        if args.edited_word:
            from scripts.import_sunday_editor_docx import reconstruct_return
            if args.edited_word.is_symlink() or not args.edited_word.is_file():
                raise ReturnValidationError("Word return must be a regular file")
            edited, _ = reconstruct_return(original, args.edited_word.read_bytes())
        else:
            edited = _load(args.edited)
        report = analyze(original, edited)
        for path, payload in ((args.out, None), (args.json_out, True)):
            if path is None:
                continue
            with _private_output(path) as handle:
                handle.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n"
                             if payload else render_markdown(report))
    except (ReturnValidationError, OSError, ValueError) as exc:
        parser.exit(2, "REFUSED: " + str(exc) + "\n")
    print("Analysis written for owner review. Nothing was imported, sent, approved or published.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
