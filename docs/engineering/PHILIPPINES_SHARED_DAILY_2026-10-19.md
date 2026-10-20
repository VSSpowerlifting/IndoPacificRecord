# Philippines integration with shared Daily

Engineering candidate. Standing AFP processing/output policy is owner-approved
(20 October); production merge/activation/deployment remain separately held.
Started from public main `5ba03d04ec`; rebased onto `4509361d13` after Korea
#832 merged during implementation. Its profile and Analyzer route are preserved.
Shared architecture #833 was already merged. Other desks' engineering is outside
this change.

## Connected implementation

- `processing/screening.py` declares `PHILIPPINES_PROFILE`. AFP and NSC use
  the same English profile and the existing Analyzer, model routing and token
  ledger. One relevance call, then one summary/topics/model-flag call. No
  translation, China category call, additional SDK or separate analysis service.
  Unknown/missing desk profiles are held outside Daily; direct dispatch fails
  closed. Explicit China and Singapore prompts retain their existing behavior.
- `processing/daily_intake.py` reuses AFP history/capture verification and NSC
  capture replay. It reads exact private Git commits, canonical identity, date,
  publisher/issuer and hashes. It compares originals against the exact snapshot
  behind the admitted link, so unchanged metadata cannot conceal a changed body,
  title or capture. No publisher retrieval is added.
- `pipeline.py --private-daily-source FAMILY,CHECKOUT,COMMIT` runs this shared
  engine in private custody. The private companion's existing collectors remain
  unchanged. `--no-analysis` and `--dry-run` verify intake without calls or state
  writes. Originals are transient inputs; the queue ledger stores hashes,
  attempts, dispositions and machine results, never another original corpus.
- Per-source pinned policy separates private model use, public machine
  explanation and unattended release. All three default false for both sources.
  NSC also retains its independent category anomaly and metadata admission gate.
  Missing rights are checked before constructing an Analyzer. One record per
  run and 16,000 input characters are the initial bounds; policy caps cannot
  exceed ten records. Oversize/empty input holds rather than truncating evidence.
- Every sentence and flag explanation requires an exact private source span.
  Checks cover completeness, attribution, numerical/date tokens, proper-name
  tokens, completed-action/modal language, categories and copied original
  sentences/long excerpts. This is conservative screening, **not a proof that
  arbitrary paraphrases are semantically correct**. No model confidence score
  substitutes for source evidence. Genuine model output still needs the first
  real acceptance exercise before activation.
- The common five-attempt retry/pause policy and usage ledger are reused.
  Source revisions/missing records hold individually. Account failure stops
  paid work for that source. `resume(state, key)` resets an exceptional pause;
  changed versions require actual source review before resetting the binding.
- Private processing produces a family-specific MAC over an allowlisted
  public-safe snapshot, bound to the processor commit, policy, exact original
  and capture hashes, metadata version and collection run. AFP/NSC keys are
  separate. Public policy is never accepted from the envelope.
- Normal `daily_update.yml` fetches only these signed outputs, with a separate
  read credential, when enabled. `pipeline.py` admits eligible outputs before
  the normal shared render. Source-specific intake failures are isolated;
  source originals never enter the public workflow or `articles` table.
- Migration 0015 adds `daily_machine_records` to the **existing** public DB.
  It stores separately licensed IPR output, with no original-title/body columns,
  and requires the already-admitted family/identity/version. SQLite admission
  is transactional and replayable; Daily reconciliation preserves additions
  and refuses conflicting versions. Signed source holds retain the DB record
  while withholding it from rendering; an old successful envelope cannot
  silently reverse that hold.
- The production renderer uses the existing record template, IPR shell and
  machine styling, Philippines page and shared archive search/export. Generated
  machine pages are pruned when held. Machine records remain distinct from
  official-link metadata, preserved originals and human analysis. The existing
  Sunday writer receives bounded, dated machine-labeled leads through its
  supplemental research contract; human source verification, bylines and Brief
  approval remain unchanged.

## Authentic evidence versus synthetic tests

Read-only replay used private AFP `d48bb3873fe3df554f5fbed5adaeafb7cdd6d876`:
32 originals/captures verified; 32 matched the exact preserved source versions
behind the 32 admitted public AFP links. The first candidate is `afp:1418`.
Its source evidence is authentic. On 20 October the owner separately authorized
one private trial at `442081916b3b41850e958ae75298bf12afe565b6`; that pin's
32 originals/captures still match all 32 admitted link versions. `afp:1418`
matches its exact captured body/version. The owner configured the private Actions
key; the genuine two-call trial consumed 1,251 input / 584 output tokens,
estimated $0.010581. Response text, relevance judgment and source-specific review
remain private: **not a quality-passing public candidate**. Prompt v2 clarifies
literal evidence punctuation and per-sentence attribution; the gates remain
strict. No further trial expense is authorized or needed by this receipt.
Private NSC `b564c3089cac408fce4dc52b794c94855efe025d` replays zero records,
a valid quiet-source outcome. No original content is copied into this document.

Offline synthetic tests exercise model routing, sentence evidence, malformed
analysis, signatures, policy/publisher separation, duplicate/revision handling,
retry/pause, item/family failure isolation and public non-disclosure. A synthetic
approved output was admitted to a disposable DB copy and rendered through the
production build into `/tmp/ipr-ph-machine-fixture-20261019/site`, including its
record page, Philippines link and archive entry. That is **not** an actual model
response, official-source publication, production DB write or deployed page.

The owner has now approved standing AFP processing and qualifying nonverbatim
machine explanations, subject to applicable source-use rights. The initial
limits are $0.35 estimated/run, one record, two intended calls, no SDK retries,
and five failed queue attempts before pausing that record. `afp:1418` is expressly
excluded regardless of future model judgments. NSC remains separately held.
No schedule, production
DB/output, Pages change or desk promotion has occurred.
The existing 32-link AFP
release remains the genuinely published product; no machine explanation has
been published by this assignment. Verification results and exact PR state
belong in the PR checks and `PROJECT_STATE.md`.

## Release and rollback

1. Review the public integration and essential private companion; require the
   full PR offline check on the exact final public head, including Chromium,
   validator and DB/output preservation. Merge only under owner authority.
2. The **already completed** private `afp:1418` trial is retained in private #21's
   `scripts/trial_afp_1418.py`, which scopes the exact
   identity/capture/content version without changing standing family flags. It
   reuses Analyzer/profile/quality/usage, disables SDK retries, limits dispatch
   to relevance (500 output tokens) and analysis (2,200 output tokens), checks a
   conservative input-byte cost bound before each call, and prevents automatic
   reruns with an exclusive private attempt marker. The $0.35 allowance is an
   estimate, not a billing-enforced cap; expected successful-call cost is below
   $0.12. Anthropic's [Sonnet 4.6 pricing](https://platform.claude.com/docs/en/models/sonnet-4-6/overview)
   and [Haiku 4.5 pricing](https://platform.claude.com/docs/en/models/haiku-4-5/overview)
   support the estimate. Actual total was $0.010581; do not repeat this trial.
   Normal private processing now also disables hidden SDK retries and applies
   the 16,000-character input ceiling conservatively to UTF-8 bytes.
3. Standing AFP policy is pinned to the owner's 20 October decision. It covers
   first-party factual reporting only, independently worded explanation rather
   than publisher expression, with attribution, citations and capture/version
   proof; no original titles/bodies/images or restricted third-party material.
   The [IP Code §§175–176,185](https://ilaw.ipophil.gov.ph/mod/resource/view.php?id=14)
   distinguishes facts, government works and research/comment use; this is not
   a blanket copyright licence or permission for exploitation of government
   expression for profit. Ambiguous source rights remain held. NSC needs its
   own metadata, anomaly, model and output decisions.
4. With separate owner release authority, configure matching independent
   AFP family key and the private-output read credential, then enable the guarded
   private processing and public Daily variables. The private runner uses only
   public main code; its JSON state/output branch is atomically advanced with
   non-force Git ref updates. It does not write public main or Pages.
   Public Daily can reuse the existing `IPR_PRIVATE_VAULT_READ_TOKEN` for the
   fixed signed-envelope read, or use a dedicated `IPR_DAILY_OUTPUT_READ_TOKEN`.
   The shared `DAILY_PH_AFP_ARTICLES_KEY` must match in both repositories;
   no NSC signing key or policy activation is needed for AFP release.
5. Process one genuine AFP record, inspect actual quality and provenance,
   consume its signed output through shared Daily and render/validate/commit
   through the existing publisher. Read back the exact record, desk and archive
   identities over deployed HTTPS; observe the next ordinary unattended cycle
   and a real failure/retry. Only then assess desk operational status.

Pause by disabling the two integration enable variables. Retain all custody
and processing history. Revoking a family policy suppresses its explanations
on the next ordinary shared render and prunes its generated machine pages;
neutral links keep their independent authorization. Replay signed snapshots
after a fetch/admission/deploy failure; identity/version checks prevent duplicate
pages or replacement of an already-released version. A signed hold persists
until an explicit reviewed recovery; no source change is silently republished.
