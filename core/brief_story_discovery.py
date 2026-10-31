"""Bounded weekly discovery for the existing private Sunday writer.

No I/O, model call, source permission, publication decision or desk promotion.
Scores remain editorial judgments; exact content anchors only prove that a
model used offered text, not that its interpretation is factually correct.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict

from core.regional_editorial_slate import WEIGHTS, heuristic_score

MAX_DISCOVERY_CHARS = 280000
MAX_DISCOVERY_RECORDS = 256
MAX_CANDIDATES = 5


class NoQualifyingStory(ValueError):
    """Explicit editorial abstention; callers must not write/send a manuscript."""

    def __init__(self, receipt):
        self.receipt = receipt
        super().__init__("No qualifying story: " + receipt["selection_rationale"])


def compact(text):
    return " ".join((text or "").split())


def eligibility(row, reference):
    """Production admission alone is insufficient for full-text drafting."""
    if reference is None:
        return "not_in_current_source_trail"
    if reference.get("screening") != "analyzed" or not row["analyzed_at"]:
        return "awaiting_screening_or_analysis"
    if row["passed_relevance"] != 1:
        return "not_selected"
    if row["processing_state"] in ("paused", "terminal"):
        return "processing_hold"
    if not compact(row["title_original"]) or len(compact(row["text_original"])) < 250:
        return "no_original_full_text_metadata_or_derived_record"
    if not str(row["source_language_tag"]).startswith("en") and not compact(row["text_english"]):
        return "translation_unavailable"
    return None


def content_digest(body, summary=""):
    """Preserve substantive synopsis and source sentences, not headline space.

    A synopsis is machine analysis and labeled accordingly. Excerpts are exact
    substrings of normalized stored text; the full body hash remains separate.
    """
    body, summary = compact(body), compact(summary)
    synopsis_omitted = max(0, len(summary) - 1600)
    # Retain the tail's caveats when an unusually long synopsis exceeds its
    # per-source allowance. Ordinary stored summaries fit in full.
    if len(summary) > 1600:
        summary = summary[:1000] + " [synopsis truncated] " + summary[-600:]
    sentences = re.split(r"(?<=[.!?])\s+", body)
    cues = (
        r"\b(first|inaugural|introduced|began|trial(?:s|led|ed)?|proof of concept)\b",
        r"\b(however|not|limited|shortfalls|previously|since last year|must|premise|uncertain|will|scheduled)\b",
        r"\b(was trialled|was conducted|proof of concept|completed|shortfalls|however|since last year)\b",
    )
    selected = []
    for pattern in cues:
        matches = [(len(re.findall(pattern, sentence, re.I)), pos, sentence)
                   for pos, sentence in enumerate(sentences) if sentence not in selected]
        count, _, best = max(matches, default=(0, 0, ""), key=lambda x: (x[0], -x[1]))
        if count:
            selected.append(best)
    # Quiet/routine records still get actual source content, with no invented
    # novelty score. Matching is an editorial cue, never proof of a new event.
    substantive = [s for s in sentences if len(s) >= 50]
    for sentence in ((substantive[0], substantive[-1]) if substantive else (body,)) :
        if len(selected) < 3 and sentence not in selected:
            selected.append(sentence)
    excerpts = []
    for sentence in selected:
        # A cue-centered prefix alone can turn a qualified trial into a
        # completed capability by dropping the sentence's closing limitation.
        # Keep ordinary sentences whole; long ones retain the cue's context
        # and closing text as exact anchors, never as a spliced quotation.
        if len(sentence) <= 360:
            excerpts.append(sentence)
        else:
            match = re.search("|".join(cues), sentence, re.I)
            start = max(0, match.start() - 60) if match else 0
            tail = len(sentence) - 180
            if start + 180 >= tail:
                excerpts.append(sentence[min(start, tail):])
            else:
                excerpts.extend((sentence[start:start + 180], sentence[tail:]))
    return {"machine_synopsis": summary, "excerpts": excerpts,
            "omitted_body_chars": len(body) - sum(len(s) for s in excerpts),
            **({"omitted_synopsis_chars": synopsis_omitted} if synopsis_omitted else {})}


def prompt_packet(packet):
    """Compress repetitive metadata, never the roster of eligible content."""
    grouped = defaultdict(list)
    for row in packet["inventory"]:
        grouped[(row["desk"], row["reason"])].append(row["id"])
    return {**{k: v for k, v in packet.items()
               if k not in ("inventory", "sources", "input_sha256", "input_chars")},
            "inventory": [{"desk": desk, "reason": reason, "ids": ids}
                          for (desk, reason), ids in sorted(grouped.items())],
            "sources": [{k: v for k, v in source.items() if k != "body_sha256"}
                        for source in packet["sources"]]}


def _grams(text):
    text = re.sub(r"\W+", "", text.casefold())
    return {text[i:i + 7] for i in range(max(0, len(text) - 6))}


def discovery_packet(chosen, supplemental, *, inventory=(), coverage=(), continuity=()):
    """Every eligible source gets content; overflow refuses before spending.

    Deterministic clusters are suggestions, never semantic truth. The model
    may join related clusters for a candidate, retaining exact IDs. Duplicate
    groups cannot multiply shortlist slots.
    No desk quota or significance/recency order decides the shortlist.
    """
    sources = []
    for row, body in chosen:
        sources.append({
            "id": row["id"], "desk": row["desk_id"], "lane": "production_record",
            "issuer": row["source_name"], "date": row["published_date"],
            "url": row["url"], "title": (row["title_english"] or row["title_original"])[:200],
            "language": row["source_language_tag"],
            "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "basis": "stored English rendering; verify original" if not str(
                row["source_language_tag"]).startswith("en") else "English original",
            **content_digest(body, dict(row).get("summary_english")),
        })
    for item in supplemental:
        sources.append({
            "id": item["id"], "desk": item["desk"], "lane": "private_research",
            "issuer": item["source_name"], "date": item["published_date"],
            "url": item["source_url"], "title": item["title_original"][:200],
            "basis": "approved private drafting summary; NOT a production body",
            "body_sha256": item["source_content_sha256"],
            "machine_synopsis": "", "excerpts": [compact(item["summary"])],
            "limitations": item["caveats"],
        })
    if len(sources) > MAX_DISCOVERY_RECORDS:
        raise ValueError("weekly discovery record budget exceeded; no silent sampling")
    # Source order is stable and interleaved by desk. This gives a low-volume
    # source early visibility without assigning it a country shortlist quota.
    by_desk = defaultdict(list)
    for source in sorted(sources, key=lambda s: str(s["id"])):
        by_desk[source["desk"]].append(source)
    sources = [group[i] for i in range(max(map(len, by_desk.values()), default=0))
               for _, group in sorted(by_desk.items()) if i < len(group)]
    clusters, signatures = [], []
    originals = {row["id"]: compact(row["text_original"]) for row, _ in chosen}
    for source in sources:
        signature = _grams(originals.get(source["id"]) or " ".join(source["excerpts"]))
        target = None
        for pos, earlier in enumerate(signatures):
            union = signature | earlier
            if union and len(signature & earlier) / len(union) >= .55:
                target = pos
                break
        if target is None:
            target = len(clusters)
            clusters.append({"id": "cluster-{}".format(target + 1), "source_ids": []})
            signatures.append(signature)
        clusters[target]["source_ids"].append(source["id"])
        source["cluster"] = clusters[target]["id"]
    packet = {"schema": "ipr-sunday-discovery/1", "inventory": list(inventory),
              "coverage": list(coverage), "continuity": list(continuity),
              "sources": sources, "clusters": clusters,
              "digest_limits": "Lossy source excerpts and machine synopses, not complete bodies. "
              "A synopsis over 1600 characters omits its middle; long selected sentences "
              "offer cue-context/tail anchors. Unoffered context can change the judgment. "
              "Unknown baseline or unresolved chronology/limitations requires review."}
    encoded = json.dumps(prompt_packet(packet), ensure_ascii=False, sort_keys=True)
    if len(encoded) > MAX_DISCOVERY_CHARS:
        raise ValueError("weekly discovery character budget exceeded; no silent sampling")
    packet["input_sha256"] = hashlib.sha256(encoded.encode()).hexdigest()
    packet["input_chars"] = len(encoded)
    return packet


def decision_score(candidate):
    """A single-country story receives no penalty for an irrelevant comparison."""
    scores = candidate["scores"]
    heuristic_score(scores)  # shared 0..5 strict integer validator
    keys = [k for k in WEIGHTS if candidate["connection_applicable"] or k != "cross_desk_connection"]
    return sum(scores[k] * WEIGHTS[k] for k in keys) / sum(WEIGHTS[k] for k in keys)


def qualifies(candidate):
    scores = candidate["scores"]
    return candidate["readiness"] == "ready" and all(scores[k] >= 3 for k in (
        "strategic_significance", "evidence_strength", "analytical_novelty", "timeliness"))


def selection_schema(production_ids, research_ids):
    """Strict-tool subset; validate_selection enforces bounds and uniqueness.

    Anthropic does not support numerical constraints, maxItems or uniqueItems
    in strict schemas. Keep those rules in descriptions and Python validation.
    """
    string = {"type": "string"}
    scores = {"type": "object", "additionalProperties": False,
              "properties": {k: {"type": "integer", "description": "Score from 0 to 5 inclusive."} for k in WEIGHTS},
              "required": list(WEIGHTS)}
    identity = {"anyOf": ([{"type": "integer", "enum": list(production_ids)}] if production_ids else []) +
                ([{"type": "string", "enum": list(research_ids)}] if research_ids else [])}
    note = {"type": "object", "additionalProperties": False,
            "properties": {"id": identity, "excerpt": string}, "required": ["id", "excerpt"]}
    properties = {k: string for k in ("slug", "thesis", "why_now", "novelty_basis",
        "counterevidence", "limitation", "connection_basis", "score_reasoning")}
    properties.update({"production_ids": {"type": "array", "items": {"type": "integer", "enum": list(production_ids)}, "description": "Unique production record IDs."},
        "research_ids": {"type": "array", "items": ({"type": "string", "enum": list(research_ids)} if research_ids else string), "description": "Unique typed research IDs."},
        "evidence_notes": {"type": "array", "items": note, "minItems": 1, "description": "One to ten exact source-content anchors."},
        "counterevidence_ids": {"type": "array", "items": identity, "description": "Unique source IDs with exact counterevidence anchors."},
        "connection_applicable": {"type": "boolean"}, "scores": scores,
        "readiness": {"type": "string", "enum": ["ready", "review", "reject"]}})
    candidate = {"type": "object", "properties": properties,
                 "required": list(properties), "additionalProperties": False}
    fields = {"candidates": {"type": "array", "items": candidate,
                             "description": "At most {} distinct story candidates.".format(MAX_CANDIDATES)},
              "selected_slug": {"type": ["string", "null"]},
              "selection_rationale": string, "omission_rationale": string}
    return {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}


def validate_selection(selection, packet):
    """Fail closed on invented anchors, unsupported winners or false abstention."""
    if not isinstance(selection, dict) or set(selection) != {
            "candidates", "selected_slug", "selection_rationale", "omission_rationale"}:
        raise ValueError("missing automatic story-selection assessment")
    options = selection["candidates"]
    if not isinstance(options, list) or len(options) > MAX_CANDIDATES:
        raise ValueError("must consider up to five story candidates")
    sources = {s["id"]: s for s in packet["sources"]}
    seen, attributed = set(), []
    expected = set(selection_schema([1], ["EXAMPLE"])["properties"]["candidates"]["items"]["properties"])
    for option in options:
        if not isinstance(option, dict) or set(option) != expected:
            raise ValueError("malformed story candidate")
        slug = option["slug"]
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,79}", slug) or slug in seen:
            raise ValueError("duplicate or malformed story slug")
        seen.add(slug)
        for field in expected - {"slug", "production_ids", "research_ids", "evidence_notes", "counterevidence_ids",
                                  "connection_applicable", "scores", "readiness"}:
            _line(option[field], field, 20, 650)
        ids = option["production_ids"] + option["research_ids"] if (
            isinstance(option["production_ids"], list) and isinstance(option["research_ids"], list)) else []
        if (any(type(i) not in (int, str) for i in ids) or
                not 1 <= len(ids) <= 10 or len(set(ids)) != len(ids) or
                any(type(i) is not int or i not in sources or sources[i]["lane"] != "production_record" for i in option["production_ids"]) or
                any(type(i) is not str or i not in sources or sources[i]["lane"] != "private_research" for i in option["research_ids"])):
            raise ValueError("story candidate used unavailable source IDs")
        clusters = {sources[i]["cluster"] for i in ids}
        if any(len(clusters & prior) / len(clusters | prior) > .5 for prior in attributed):
            raise ValueError("duplicate stories cannot occupy the shortlist")
        attributed.append(clusters)
        notes = option["evidence_notes"]
        if not isinstance(notes, list) or not 1 <= len(notes) <= 10:
            raise ValueError("candidate lacks content evidence notes")
        anchored = set()
        for note in notes:
            if not isinstance(note, dict) or set(note) != {"id", "excerpt"}:
                raise ValueError("malformed evidence note")
            ident = note["id"]
            if type(ident) not in (str, int) or ident not in sources:
                raise ValueError("unavailable content anchor")
            _line(note["excerpt"], "content anchor", 20, 600)
            source = sources[ident]
            if not any(note["excerpt"] in text for text in source["excerpts"] + [source["machine_synopsis"]]):
                raise ValueError("content anchor not present in offered source content")
            anchored.add(ident)
        counters = option["counterevidence_ids"]
        if not isinstance(counters, list) or any(type(i) not in (str, int) for i in counters) or len(set(counters)) != len(counters) or not set(counters) <= anchored:
            raise ValueError("counterevidence needs exact offered content anchors")
        if not set(ids) <= anchored or not anchored <= set(ids) | set(counters):
            raise ValueError("every supporting source needs a content anchor")
        if type(option["connection_applicable"]) is not bool:
            raise ValueError("connection applicability must be explicit")
        if option["connection_applicable"] and len({sources[i]["issuer"] for i in ids}) < 2:
            raise ValueError("connection needs distinct issuing institutions")
        if option["connection_applicable"] and len({sources[i]["cluster"] for i in ids}) < 2:
            raise ValueError("duplicate release surfaces cannot earn a connection bonus")
        heuristic_score(option["scores"])
        if not option["connection_applicable"] and option["scores"].get("cross_desk_connection") != 0:
            raise ValueError("inapplicable connection must score zero")
        decision_score(option)
        if option["readiness"] not in ("ready", "review", "reject"):
            raise ValueError("invalid candidate readiness")
    for field in ("selection_rationale", "omission_rationale"):
        _line(selection[field], field, 30, 1200)
    ready = [o for o in options if qualifies(o)]
    lead = selection["selected_slug"]
    if ready and len(packet["clusters"]) >= 3 and len(options) < 3:
        raise ValueError("a broad weekly corpus requires at least three distinct proposals before commitment")
    if not ready:
        if lead is not None:
            raise ValueError("no qualifying story; must explicitly abstain")
    elif lead not in {o["slug"] for o in ready}:
        raise ValueError("selected story must meet evidence and novelty floors")
    elif decision_score(next(o for o in ready if o["slug"] == lead)) < max(map(decision_score, ready)):
        raise ValueError("chosen story is not highest-scoring qualifying candidate")
    return selection


def _line(value, label, minimum, maximum):
    if (not isinstance(value, str) or not minimum <= len(value) <= maximum or value != value.strip()
            or any(ord(c) < 32 for c in value) or re.search(r"===|SOURCE RECORD IDS:|END OF", value)):
        raise ValueError("malformed story " + label)


def receipt(packet, selection=None):
    """Private metadata only; no source excerpt or synopsis in the receipt."""
    developed = {i for option in (selection or {}).get("candidates", [])
                 for i in option["production_ids"] + option["research_ids"]}
    return {k: v for k, v in packet.items() if k != "sources"} | {
        "source_pins": [{k: s[k] for k in ("id", "desk", "lane", "body_sha256", "cluster",
                                         "omitted_body_chars", "omitted_synopsis_chars") if k in s}
                        for s in packet["sources"]],
        "unscored_cluster_ids": [c["id"] for c in packet["clusters"]
                                 if not developed.intersection(c["source_ids"])],
        "source_accuracy_verified": False, "publication_authorized": False}
