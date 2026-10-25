# Sunday discovery and provisional story selection

This extends PR #805 within the existing Sunday handoff. The October 24
editorial assessment is held outside this public repository for private owner review.
The separate owner-signed thematic preview retains its existing contract.

## Before composition

The normal full-week handoff still scaffolds the successful Sunday's stored
Sunday–Saturday corpus and validates its governed research packet. Its existing
writer now inventories every row from the scaffold's production desks instead
of ranking ten bodies by model flag and recency. Full-text drafting requires
an exact source-trail match, completed screening/analysis, a positive relevance
disposition, no processing hold, a substantial original and an available
English representation where needed. Derived explanations with no original,
short bodies, unscreened records and separate official-link rows stay visible
with hold reasons. This is stricter than historical source-trail inclusion.
Production admission and research permissions remain upstream requirements;
the selector grants none. Current-week private research retains typed IDs and
its existing roster, source-version and distribution restrictions.

Every eligible source contributes a fuller labeled machine synopsis and exact
source-sentence excerpts selected for changes, outcomes, plans and limitations. Whole originals are read locally for integrity
and deterministic clustering, not copied wholesale into an expanded prompt.
Character-shingle similarity groups near-duplicate originals across issuing
surfaces; the model must recognize further related developments and can split
or combine these suggestions. A cluster is not independent corroboration or
a certified semantic event. All source digests remain available. Desk
interleaving changes presentation order, not eligibility or shortlist quotas.
The recent six approved Brief titles provide continuity context.

The one existing invocation emits a `story_selection` decision before article
fields. With at least three source clusters, commitment requires three to five
distinct proposals. Each has a thesis, why this week, novelty versus baseline,
counterevidence, limitations, scores/reasoning, readiness and exact content
anchors for its sources. Renaming the same evidence set cannot fill the slate.
Important undeveloped alternatives and coverage gaps require an omission
rationale. A single-country focus is allowed for private drafting; existing
single-desk publication-exception approval is unchanged.

## Reproducible decision mechanics

The baseline remains `regional_editorial_slate.WEIGHTS`: significance 30,
evidence 25, novelty 20, connection 15, timeliness 10. Scores are 0–5 editor/model
judgments, not facts. When connection is inapplicable its score is zero and the
other weights normalize over 85; a forced multinational comparison gains no
automatic advantage. Applicable connections need distinct issuing institutions
and a source-grounded explanation. No source-count or model-flag bonus exists.

`ready` candidates must score at least 3 on significance, evidence, novelty and
timeliness. Aggregate scores cannot rescue weak evidence or routine activity.
The highest qualifying score wins; a tie permits either tied lead. Both the
development and opening must cite the selected evidence and may add only its
declared counterevidence. Exact excerpt matching prevents invented evidence
anchors; ordinary section citation and reserved-boundary checks still run.

If none qualifies, `selected_slug=null` saves a mode-0600 private
`.selection.json` beside the requested output, with no manuscript and no SMTP.
An empty eligible corpus abstains before any model call. Malformed responses
fail closed. Candidate fields precede prose in the schema and prompt, but no
single-call implementation can prove the model's internal reasoning order or
factually validate its scores. The editor must assess meaning and source
support; these offline tests do not claim live model quality assurance.

## Inspectable evidence and bounds

The immutable TXT appendix includes the provisional comparison and a
program-owned discovery receipt: all observed eligibility outcomes, registry
coverage, cluster membership, source-body hashes, input hash/size and which
clusters have no developed proposal. Candidate assessments are model output;
source fingerprints, inclusion and exclusion accounting are program output.
The readable DOCX/mail body remains prose-only. The returned DOCX/TXT source
appendix integrity and Ben's approval/numbering/publication gates remain intact.

Full-week automatic selection uses at most one model request, with the existing
PR #805 output ceiling of 5,400 tokens and no malformed-response paid retry.
This is fewer possible calls than main's two-attempt ordinary writer. Input
can be substantially larger than the former ten excerpts: at most 256 source
digests and 280,000 serialized discovery characters, plus the existing bounded
instructions/schema. These are character bounds, **not a dollar/token quota**;
actual model usage still needs normal operational spend observation. Overflow
refuses before spending rather than silently sampling the week. No paid call
or editor send was made to develop this change.

Read-only replay, with no API key, model or SMTP:

```sh
.venv/bin/python -m scripts.audit_sunday_story_discovery \
  --week-ending 2026-10-24 --out /tmp/ipr-oct24-discovery.json
```

This production-only audit adds no private packet. The runtime alone uses its
existing separately governed research expansion. The frozen October 24 replay
in `docs/evidence/briefs-selection-2026-10-24/discovery.json` records the exact
checkout's source availability, not a paid editorial decision, live collector
attestation or rights review. Missing research/access remains a coverage gap,
never institutional silence. Its input hash is a snapshot commitment and can
change when registry, prior approved titles or the admitted corpus change.

Focused checks include `tests.test_sunday_story_discovery`,
`tests.test_sunday_automatic_story_selection` and the existing Sunday/source-use,
thematic-preview, owner, delivery and editorial-return tests. The repository's
full `PR offline checks` remains required at the final review revision.
PR #807's trigger work, #819 citation fixes, #876 Saturday Vietnam fix,
Daily collection, schedules, editor addresses and production output are outside
this change. No merge, activation, paid rehearsal or replacement communication
is authorized by this document.
