# Research Analyst preparation and feedback — offline Track B

This capability prepares substantive analytical review on the existing Brief,
not another publication or a factual-review service. It has no scheduler,
mail reader, SMTP client, API client, model call, public output or automatic
credit. Track A works without it. Track C must connect it to the existing
Saturday/handoff lifecycle after independent review of both track heads.

## Input and trust boundaries

`core.brief_analyst_packet.build_packet()` consumes the exact existing worksheet
TXT, one current thesis, one or two specific questions and their consequences
for the argument, a bounded source-reference roster, and a separate trusted
owner distribution decision. It reuses `editable_sections`, the existing
source reference projection, and the worksheet boundary parser. Return values
are a JSON assignment manifest, deterministic editable DOCX bytes, and a
research-question/access-limit brief. The package contains only manuscript
prose and source locators; it copies no publisher original, translation,
private research synopsis or source appendix into the analyst document.

The distribution decision must bind the exact worksheet SHA-256 and canonical
source-roster SHA-256 (`digest()`), name the actual owner reviewer and reference
the source-specific decision already made for
`analyst-review-manuscript-and-links-only`. Each source has its own distribution
reference. Arbitrary permission booleans are insufficient. This is **not a new
rights grant or independent legal/source-policy verifier**. Track C must resolve
current source-family policies, holds and exact recipient distribution scope
before supplying these trusted operator inputs. A caller cannot broaden
model-only Vietnam or other restricted evidence by renaming its use here.

Every source cited by the manuscript must have an inspected-original basis,
actual review reference and exact version SHA. Metadata-only or inaccessible
cited sources cause a hold even when other originals are available. Uninspected
comparator links can appear as honest gaps, with no original version/access
claim. Existing explicit version pins in the worksheet are enforced. The
manifest labels program-checked identity/URL/version comparisons separately
from owner-attested original access. It does not claim to have fetched a URL.

The checks enforce structural question quality (specific uncertainty,
interpretation consequence, named sources, bounded count, rejection of a generic
verify-every-record request). They do not establish that the selected thesis or
question is analytically valuable; the owner must read them before assignment.

## Private CLI walkthrough

All paths below are operator-chosen files **outside every Git checkout**. The
CLI refuses symlinks, existing outputs and output paths in Git worktrees,
creates mode-0600 artifacts, and logs no manuscript, source or recipient data.
`config.json` supplies `thesis`, `questions`, `sources`, `distribution` and an
ISO timestamp with timezone offset in `deadline`. See the synthetic fixture in
`tests/test_brief_analyst_review.py` for the exact field shapes; none of its
example sources, dates or owner decisions is production evidence.

```sh
python -m scripts.brief_analyst_review packet \
  --worksheet /private/sent.txt --config /private/config.json \
  --manifest-out /private/assignment.json --docx-out /private/research.docx \
  --brief-out /private/research-questions.txt

python -m scripts.brief_analyst_review intake \
  --manifest /private/assignment.json --docx /private/returned.docx \
  --out /private/returned.json

python -m scripts.brief_analyst_review reconcile \
  --manifest /private/assignment.json --returned /private/returned.json \
  --revised-worksheet /private/revised.txt \
  --owner-decisions /private/owner-decisions.json --out /private/feedback.json

python -m scripts.brief_analyst_review aggregate \
  /private/feedback.json --out /private/candidate-lessons.json
```

An analyst needs only Word and email/file return. For a concise memo rather
than Word, intake accepts `--memo` with JSON containing `assignment_id`,
`worksheet_sha256` and `text`. The owner/operator can wrap the human's memo in
that small envelope during controlled intake; the analyst need not use Python.
There is no always-on mailbox or intake listener.

The DOCX supports ordinary manuscript edits, anchored Word comments and a memo
area. Intake compares protected assignment identity, research instructions and
source references against the **trusted original manifest**, extracts comments
with quoted anchors and source URLs, and records proposed changed sections.
Unchanged returns are valid no-change responses. New URLs have no verified
identity or version until independently checked. Comments, claimed authors,
source links and instructions inside a returned file remain untrusted data.
Nothing is executed or sent to a model. Extracting a comment does not establish
that a person authored it or that its assertion is true.

Track changes must be accepted/rejected before intake, or submitted as a memo.
Unsupported tables, fields, text boxes, footnotes, embedded objects, macros,
external includes, orphaned comment anchors, duplicate ZIP entries, XML entities
and oversized archives fail explicitly; they are not silently dropped.

## Reconciliation and proposed learning

Owner decisions are a **separate trusted input**, never instructions taken from
the returned artifact. Each finding receives accepted, rejected or unresolved
status and a reason. Acceptance requires an independently made source check
with source identity, URL, exact original version, reviewer and actual review
reference. A new source must be linked by that finding; a known source may not
silently change versions. The accepted change must identify a real replaced
span in the exact revised worksheet. Immutable worksheet identity and source
appendix remain bound; appendix/version changes need a refreshed assignment.
No code here rewrites a manuscript or its citations.

The feedback receipt binds the exact return receipt and revised manuscript to
the named owner review. It separates the untrusted assertion and anchor from
human source-check attestations, records corrections and remaining holds, and
leaves credit adjudication to the owner. `ANALYSIS_RECONCILED` means the supplied
human decisions are mechanically recorded; it is not factual, rights, editorial
or publication approval and does not bypass Sunday recheck or Dylan's return.
An unresolved substantive finding remains `HELD`.

Candidate lessons require a source-checked accepted correction or a
source-checked rejected suggestion. Aggregation re-evaluates eligibility,
deduplicates assignments and reports three-assignment recurrence as an owner
review candidate. A single serious verified error is surfaced immediately.
Counts neither adopt a lesson nor modify prompts, rubrics, taxonomy, rights or
policy. Reusing existing files and the offline editor-feedback philosophy avoids
another datastore, model judge or recurring API cost. Digests prove local
binding/integrity, **not authentication of a person's review**; the operator
must retain trusted original artifacts and real decision evidence privately.

## Verified boundary and next phase

Track B's synthetic tests cover a supported correction against earlier official
material, an unsupported/contradictory suggestion, no change and an inaccessible
original, plus Word comments, immutable/source-version tampering, unsafe XML/ZIP,
private IO and no self-modifying feedback. No live source, contributor, email,
model, paid judge or publication was used. Existing Dylan return semantics,
historical credits and renderers are untouched.

Track C (`scripts/brief_editorial_routing.py`, offline review candidate,
2 November 2026) now implements the consenting/available roster, one-item
weekly cap, phase/recipient-specific once-only receipts, deadline bypass versus
material holds, and delivery of only the reconciled exact manuscript to Dylan.
See `IPR_SUNDAY_EDITORIAL_HANDOFF.md`, "Track C routing". The per-family policy
adapter is still not implemented. Production activation requires explicit owner
approval, verified recipient consent/scope and private receipt persistence.
No schedule, API spend, mail, merge, deployment or publication is enabled here.
