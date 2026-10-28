"""Synthetic fixtures for the Briefs narrative-writing reform.

SYNTHETIC DEMONSTRATION TEXT. The Tavaran Navy, the patrol ship Marisol, Rear
Admiral Voss and every figure below are invented for tests and for the
before/after demonstration. They describe no real institution or event, and no
private October 24 manuscript or unapproved source text appears here.

``legacy_manuscript`` is written the way the retired fixed-outline template
tended to read; ``article_manuscript`` tells the same invented story as an
article. Both cite the two production records in ``evidence()``.
"""
from __future__ import annotations

import copy

from tests.test_briefs_editorial_evidence import SAT, scaffold  # noqa: F401
from tests.test_weekly_briefs_auto_writer import evidence, valid_manuscript  # noqa: F401

TITLE = "A navy says its new towed sonar heard a submarine 11 kilometres away"
DEK = ("The Tavaran Navy reports that a domestically built sonar array tripled its detection "
       "range in shallow water; the claim rests on the navy's own account.")

ARTICLE_BLOCKS = (
    ("", (
        "The Tavaran Navy has spent three weeks towing a new sonar array behind the patrol "
        "ship Marisol in the shallow Kesh Strait, and on 14 October it said what the array "
        "found. Rear Admiral Ilan Voss, the navy's chief, told reporters that the system "
        "picked up a diesel-electric submarine from 11 kilometres away in water about 60 "
        "metres deep.\n\n"
        "A towed array is a long cable of underwater microphones pulled behind a ship, far "
        "enough back to escape the ship's own engine noise. The navy did not name the "
        "submarine, say who operated it, or release any recordings.")),
    ("Why shallow water is hard", (
        "Sonar works best in deep, cold ocean, where sound travels in long, predictable "
        "curves. Over a seabed only 60 metres down, the same pulse bounces between the "
        "surface and the bottom, and a quiet submarine blends into the echoes. Navies that "
        "operate near coasts have long treated this as the hardest version of the detection "
        "problem.\n\n"
        "That is why the claimed range matters more than the ship or the array. Voss said "
        "the sonar previously fitted to the Marisol class managed about four kilometres in "
        "the same strait, so the navy is reporting a gain of nearly threefold. Both figures "
        "come from the navy, and it gave no test conditions for either.\n\n"
        "The design follows from the physics. A sonar fixed to the hull has to listen "
        "through the ship's own noise, so trailing the array behind the stern removes most "
        "of it. The price is manoeuvrability: a ship dragging a cable that long turns "
        "slowly and cannot easily back up.")),
    ("A domestic design", (
        "The array was built by the Tavara Naval Research Institute, which Voss said began "
        "work in 2023 after a request for imported systems drew no bid the navy could "
        "afford. Production will start next year at the Port Sellis yard, with the first "
        "sets going to the four ships of the Marisol class.\n\n"
        "But the announcement contains no budget and no delivery schedule beyond next year. "
        "Voss said the cost per ship was \"within existing allocations\", which leaves open "
        "whether the navy is buying four arrays or committing to a longer production run.\n\n"
        "For a navy of this size the practical question is how many ships get the system, "
        "not whether one trial worked. Voss said the array fits the winches already "
        "installed on all four ships, so each refit should need only a few days in port.")),
    ("What would settle it", (
        "The next evidence will be practical rather than rhetorical. If the navy publishes "
        "the test conditions, or invites an outside observer to the autumn exercise it has "
        "scheduled in the strait, the 11-kilometre figure can be judged against the seabed "
        "and sea state that produced it.\n\n"
        "Until then the claim is a navy statement about its own equipment, and a plausible "
        "one: the gain it describes is large, but not larger than a new array tuned to one "
        "strait could deliver.")),
)

AUDIT = {
    "development": "The Tavaran Navy announced that a new towed sonar array detected a submarine at 11 km in 60 m of water.",
    "baseline_and_routine": "Routine this week: ordinary ship movements. Baseline: the navy's own prior figure of about 4 km, unverified.",
    "cross_desk_assessment": "Single-country story. No other desk's record concerns towed sonar, so no comparison is made and none is forced.",
    "limitations": "Test conditions, submarine identity and operator are not given; all figures are the navy's own and cannot be corroborated from the supplied records.",
    "terms_to_verify": "Check the original wording for 'towed array', the 11 km and 4 km figures, and the phrase 'within existing allocations'.",
}


def article_manuscript(*, extra=False):
    """A valid article-first manuscript over the two production records in ``evidence()``."""
    blocks = []
    for heading, text in ARTICLE_BLOCKS:
        block = {"heading": heading, "text": text, "citations": [2]}
        if extra:
            block["supplemental_citations"] = []
        blocks.append(block)
    audit = dict(AUDIT, citations=[2])
    if extra:
        audit["supplemental_citations"] = []
    result = {
        "title": TITLE, "dek": DEK, "article": blocks, "audit": audit,
        "editorial_questions": (
            "Please check the 11 km and 4 km figures and the 'within existing allocations' "
            "quotation against the original wording before anything is public."),
    }
    if extra:
        result["editorial_focus"] = "The Tavaran Navy's claim of tripled shallow-water sonar detection range"
    return result


LEGACY_TEXT = {
    "title": "Tavaran Navy sonar release: what the record shows",
    "dek": "A review of a navy press release on towed sonar trials and what the available record does or does not establish.",
    "development": (
        "On 16 October 2026 the Tavaran Navy published a press release on its website "
        "describing trials of a towed sonar array on the patrol ship Marisol."),
    "opening_note": (
        "The available record suggests that the Tavaran Navy released a statement about a "
        "new sonar system. This note examines what the release says and what the available "
        "record does not establish. The release was published on 16 October and the stored "
        "record covers the week ending 24 October."),
    "what_stood_out": (
        "What stood out in the record was the claim of detection at 11 kilometres. The "
        "record does not establish the conditions of the test. It could not be determined "
        "whether the submarine was cooperating. The available record suggests the claim is "
        "notable, but this cannot be confirmed."),
    "why_it_matters": (
        "This matters because anti-submarine capability is important for regional security. "
        "The development underscores the importance of shallow-water detection in an "
        "increasingly complex maritime landscape. It is important to note that the claim "
        "is the navy's own."),
    "what_was_routine": (
        "What was routine this week was that the navy published a release in its ordinary "
        "format. The record does not show anything unusual in the format of the release."),
    "what_im_watching_next": (
        "I am watching whether the navy publishes further information. I could not "
        "determine when this might occur."),
    "cross_desk_comparison": (
        "Across the region, no other desk in the record reported a comparable development, "
        "so a comparison is not possible. The record does not establish whether others are "
        "pursuing similar systems."),
    "editorial_questions": "Please check the 11 km figure and the date against the original release.",
}


def legacy_manuscript():
    """Fixed-outline manuscript in the retired shape (validates under the legacy path)."""
    m = copy.deepcopy(valid_manuscript())
    for key, value in LEGACY_TEXT.items():
        m[key] = value
    m["citations"] = {name: [2] for name in m["citations"]}
    return m
