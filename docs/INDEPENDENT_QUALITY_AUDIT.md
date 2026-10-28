# Independent quality audit packet

This offline preparation tool produces an **unsigned** starting packet for a
second human reviewer. Dylan is the intended reviewer, but preparation does not
assign him, establish his language expertise or record any completed review.
No model, crawler, publisher request, mail, production write or release is used.

## Generate and verify

From the repository, using Python 3.9 or later (standard library only):

```sh
python3 scripts/build_independent_audit_packet.py \
  --revision HEAD --seed ipr-independent-audit-2026-10-27-v1 \
  --out "$HOME/ipr-private-audits/quality-audit-2026-10-27"
python3 scripts/build_independent_audit_packet.py \
  --verify "$HOME/ipr-private-audits/quality-audit-2026-10-27"
```

Use the full delivered head SHA instead of HEAD to recreate the initial packet.
The revision must contain this methodology. The output directory must be new
and outside the repository; generation refuses to overwrite an existing packet
or reviewer work. Git objects are read locally, with no network access. No
working database, output or sidecar is opened or written. The database is read
through the existing scratch-copy `reconcile_db.read_only` helper.

`manifest.json` pins the repository revision, database Git blob and byte SHA-256,
full eligible roster with row-version hashes, exclusions, seed, stratum counts,
selected identities, publisher/IPR URLs, dates with meanings, processing fields,
stored provenance receipts and evidence-file hashes. `snapshot/` holds the
committed DB and public research index. `sample/` and `supplement/` contain local
JSON evidence and frozen committed HTML, not new publications. Open the HTML
as text for offline checking; loading it in a browser can request remote assets.
`worksheet.md` gives check instructions and per-item pending tables.
`methodology.md` is this document from the selected revision.
`known-problems.json` identifies existing assistant-prepared correction candidates.
`reviews.json` is the working verdict ledger; all checks start pending and
unsigned. Keep prose notes in a copy of the worksheet, preserving frozen files.

Verification reconstructs selection and manifest from the Git revision and
compares all frozen evidence hashes. It validates the verdict ledger separately;
it does **not** authenticate a person, prove review independence or certify their
judgments. Any non-pending outcome requires a reviewer, actual ISO review date
(no future dates) and specific evidence note. Pending verdicts have null identity,
date and note. Allowed outcomes are `pending`, `pass`, `issue`, `not-assessable`.
The generator never upgrades a pending verdict or declares human completion.

## Sampling frame and deterministic rule

The unit is a committed `articles` row with nonblank preserved original body,
a valid source-stated publication date, publisher URL and an existing committed
`output/record/<id>.html`. This frame audits the public corpus as preserved in
the pinned database; it excludes retired/removed rows, missing bodies, unpublished
rows, private collectors and separate research-only originals. Missing dates,
bodies and committed pages are explicitly enumerated. The frame is **not** all
publisher output, all captures or all official publications across the region.
A stored extracted body counts as preserved text, not as preserved raw HTML/PDF.

Strata are stored source family × calendar quarter of stored publication date.
Take one record per nonempty stratum. Allocate remaining slots to the stratum
with the largest exact rational `population / (allocated + 1)`, respecting its
capacity; ties go to the lexically first stratum. Stop at 20. If fewer than 20
eligible records or more than 20 strata exist, stop with an error rather than
silently dropping strata. Within a stratum order by
`SHA256(UTF8(seed + NUL + identity + NUL + version_sha256))`, then identity.
Identity is `article:<database id>` bound to publisher URL and source in the
version hash. Version is SHA-256 of the complete joined article/source identity
row serialized as sorted-key, indented UTF-8 JSON with a final newline.
Original-body SHA-256 separately hashes exact UTF-8 stored body text. Stored
`content_hash` is retained as a deduplication signal, not substituted for a
body or raw-capture hash. Available source/capture/policy/QA receipts retain
their original field names and meanings; absent receipts are not fabricated.

The explicit default seed is `ipr-independent-audit-2026-10-27-v1`. There is no
clock-based selection or replacement of difficult, contaminated or untranslated
records. The manifest reports the actual eligible population and sample per
stratum. This coverage-oriented design oversamples small families/periods;
**do not publish a pooled accuracy rate as a population estimate**. Report
outcomes per check/stratum and assessability. Any population inference requires
appropriate stratified weighting and uncertainty analysis beyond this packet.

Prior problem candidates come from the committed China original-source notes;
only contamination and absent-body cases are listed, as unadjudicated assistant
observations. They do not influence selection or its denominator. A candidate
selected naturally remains in the sample; `also_selected` discloses overlap.
Additional known-case examinations count only in a separately described section.

## Other-desk supplement and limits

From the committed public Archive research index, take at most one item from
each desk outside the selected sample's desks, ordered by desk code, up to four.
Within a desk prefer machine explanations, then use the same seeded hash rank
and identity tie-break. Otherwise take metadata-only official links. Counts are
descriptive, outside the preserved-body sample denominator. No missing private
original is replaced with a metadata link in the main sample.

An official link may have no individual IPR permalink. The packet preserves that
fact and identifies the committed desk's canonical surface, publisher link and
index identity. It does not invent a record URL. Stored database receipts are
attached where present; index-only metadata without a database receipt remains
visible as such. A machine explanation's public wording, labels, source identity
and canonical link can be checked. Its substantive support cannot be passed
without access to the authorized cited original. Metadata-only entries permit
attribution/date/citation checks, not extraction or translation accuracy checks.
Use `not-assessable` with reasons when a check does not apply or evidence is absent.

For the main sample, compare exact extracted bodies, translations/summaries,
labels, source citation and committed HTML. Completeness, contamination and
ordering against publisher originals need raw HTML/PDF or another authorized
preserved original. Those upstream captures are **not included** by this tool;
without them, mark the affected check not-assessable or narrowly document what
was assessed. No new retrieval or private-repository access is implied.
Publisher URL, posting date and source institution are stored claims requiring
review: a host may republish another issuer. Publication, document issue, event,
collection and processing dates are different facts. Clock zones are not inferred
when absent. English originals need no translation; missing or held translations
must be disclosed, not treated as correct. Language competence must be recorded.
Official statements establish an institution's account, not independent truth.
The committed page is evidence of repository output, not proof of current live
CDN content or historical delivery.

## Custody, findings and eventual publication

The directory is private/local by default (0700; evidence files 0600). Preserve
existing source-use restrictions: this tool grants no rights to distribute stored
originals, translations, screenshots or private evidence. Do not commit the real
packet. Only code, methodology and synthetic test fixtures belong in this PR.
Do not edit public records or use this ledger as a correction/release approval.
Record concrete correction candidates in reviewer notes for separate editorial
review, with identity, version, observed discrepancy and cited evidence.

An eventual publishable report should state the reviewer and independence from
the original author, actual dates, language expertise, frame/snapshot/seed,
selection rule, completed and not-assessable counts for each check and stratum,
findings with evidence references and limitations. Report the supplement and
known-case work separately. Redact restricted evidence and obtain the existing
editorial/source-use approval before publication. No report or signed result is
created by engineering preparation.
