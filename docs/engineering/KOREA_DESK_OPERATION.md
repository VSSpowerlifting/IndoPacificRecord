# Korea desk operation

> **Desk architecture/process supersession — 30 October 2026:** the
> [mandatory shared desk standard](../desks/README.md) governs every current and future
> desk. This document's older common architecture, onboarding order and launch
> clocks do not override it. Source-specific decisions, restrictions, real
> evidence and still-used commands remain valid in their actual scope. This
> notice does not claim runtime migration, change permissions or activate a source.


## DAPA original-source qualification — 3 November 2026

**Decision-ready evidence; proposed source use, not an adopted grant.** Public
baseline `895aa3469844866f5f63aa07109a2827dfedbf64`; private code main
`a3f6299bd783b9624d0754707572dbb89abdd860`; private custody
[`archive/korea-dapa-policy-briefing` at `85cefcc42e5a5f53ef1dc32dc8b8d903f08abbab`](https://github.com/VSSpowerlifting/ipr-source-evidence-private/tree/85cefcc42e5a5f53ef1dc32dc8b8d903f08abbab/state).
This section updates the DAPA boundary; the MND repair below remains a separate
phase. The founder's [eight-desk scope](../desks/EIGHT_DESK_OPERATIONAL_COMPLETION_PLAN.md)
requires DAPA independently of MND. No source policy, runtime, workflow, model,
production database, original, published output or private archive was changed.

### Authentic evidence and current reader frontier

The private `state/shadow.db` passes SQLite integrity checking and has SHA-256
`58b97902d6e5b2b33276cbea46ecdc882bb47b12df991f9ea1020d5a8773e5ed`.
Its three records are `156786687`, `156786759` and `156786758`. All three stored
texts re-extract byte for byte from their preserved HWPX; their stored headings
match their captured article headings. All 30 preserved capture/original file
paths were read independently through GitHub at the pinned commit: 29 distinct
payloads, including a repeated robots payload. SHA-256 verification succeeded
for every payload; all 16 retained collector ledgers' request hashes and byte
lengths match the retained captures. This does not certify missing historical
slots or make failed attempts successful.

| Portal newsId | Posted date | HWPX fileId / bytes | Custody and qualification disposition |
| --- | --- | --- | --- |
| `156786687` | 2026-10-27 | `198578348` / 235,784 | First candidate: scheduled `40614736442-1`; stored text matches, normalized article heading occurs in HWPX. |
| `156786759` | 2026-10-28 | `198578611` / 230,189 | Scheduled `40802644509-1`; stored text matches. Normalized article heading does not occur verbatim in extracted HWPX; review the variation before substantive use. |
| `156786758` | 2026-10-28 | `198578609` / 227,771 | Same successful run; stored text and normalized heading match. An MND name occurs in the text; this alone establishes neither joint authorship nor a rights conflict. Review issuer/third-party scope. |
| `156787071` | 2026-10-29 | `198579982` / 238,043 | Preserved HWPX in failed `40988894694-1`, absent from source DB. Another item (`156787009`) failed listing/detail agreement, rolling back the batch. Do not admit this orphan by bypassing the failed-batch contract. Its heading also needs variation review. |
| `156785254` | 2026-10-15 | `198570147` / 230,559 | Separate historical owner-capture/import, not scheduled acquisition. Existing link-only approval does not clear substantive use; retained semantic/rights flags remain false. Useful regression sample. |

The recent successful scheduled runs
[`41372802102`](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/41372802102)
and [`41572372748`](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/41572372748)
are **quiet days**, nominal November 1 and 2 respectively, executed the following
UTC date. Their actual collection/readback jobs passed, robots and complete
filtered listings were captured, `ok_no_publications` was recorded, no originals
arrived and public dispatch was skipped. They establish continued collection
operation, not new original-to-reader delivery. The October 29 failed batch
remains failed and its unadmitted HWPX remains preserved.

Independent HTTPS inspection of [the Korea desk](https://indopacificrecord.org/korea.html)
on November 3 found **four DAPA official-link entries**: `156785254`, `156786687`,
`156786758`, `156786759`, matching the baseline's tracked Korea page. The live
page explicitly limits DAPA to metadata and separate review. This was identity/
scope inspection, not a byte-for-byte site attestation or substantive DAPA Record
delivery. No DAPA English explanation was qualified here.

### Exact original versions

Each canonical article is
`https://www.korea.kr/briefing/pressReleaseView.do?newsId=<newsId>`; each HWPX
download is `https://www.korea.kr/common/download.do?fileId=<fileId>&tblKey=GMN`.
DAPA (`kr_dapa`, portal issuer `B00008`) is the **issuer**; Korea Policy Briefing
(`kr_policy_briefing`) is the **republisher**. Source family stays
`kr_policy_dapa_releases`, identity prefix `korea-dapa-policy:`.

| newsId | Captured article SHA-256 | HWPX SHA-256 | Existing extractor's text SHA-256 |
| --- | --- | --- | --- |
| `156786687` | `464a5f0e0314687d763834c4a5649fef0af7715812a897e4cb1c4b515a235085` | `1b447257bfd7359d5acab8f56051a6371c30cbd3b58688e884505a377c991e31` | `c36017771290580e93fd4fef0fea2b86c27c61f6828377a3979e5f1f6d9bba0c` |
| `156786759` | `b3a0660340b4250c941c0f0937c510e7cd2717e1bd33bd72ddc87d993dc40994` | `3099381ebde8bec90398418282ac8295fd0481c707e51e7b662e20c29907941d` | `6755f8ed9cdfbf9f4f7b73449f453776db3c27416035c2f2b1d62893eb6720dc` |
| `156786758` | `c45188ef880fee6313b480af5c6569b31d1c9e91a9e25bb70d170007212461ab` | `1d019223e5289c7619aa4c9123a2626040caede9f133a9ef17849ceddf06b415` | `4fb52ca49b9009608617b7bb2b8bcd2d310080e876caf00e542e59d103095330` |
| `156787071` | `8bcb8dfad817234c5076c84be2feb7a548fe9537ad1c7df7131409052139589a` | `a49534176388a951c98d59d01f1a749a649674f5daeb9931053e9168388b5d96` | `a15e3347fef72a76bf27902952071d3b158dfdc332129a57d95d8683cee55c20` |
| `156785254` | `18d6f645ac345f8a76958be45c6445672e39792e905b6a1edb9472b4a315b992` | `dc832374f7709dfc14a08baf4fad526bf8b519114f0cebdca9793a49a64dd8a8` | `23c014be6ed75bef835553d6d4a674871c6f10f7abb4aa41bee432650fff3abb` |

Ordinary originals/captures are `state/captures/<sha256>.bin`. The historical
original and its HTML are instead under
`state/historical_owner_imports/dapa-2026-10-15-156785254/`, with the HWPX named
`<sha256>.hwpx` and HTML in `captures/<sha256>.bin`. Original bytes stay private.

All five pass the existing `scripts/audit_dapa_hwpx.py` SHA/size/structure audit
and ZIP CRC checking. Each has one XML section. Extracted character counts are
1,765 / 1,315 / 1,245 / 938 / 1,342 in table order; table counts are 5 / 5 / 5 /
6 / 5, and embedded binary-member counts 5 / 5 / 5 / 6 / 5. The extractor's
sequence matches all section XML text runs after whitespace removal. This
supports text-run coverage, **not** visual reading order, table relationships,
image-text completeness or Korean semantic approval. Embedded previews are
approximately 1,022 characters and cannot replace complete section extraction.

### Source-use finding and exact unresolved boundary

All five captured article pages have one article-local **KOGL Type 0, text-only**
notice and the `open_type_00.png` mark/Type 0 alt text. Each explicitly excludes
non-text photos, images, illustrations and video from automatic permission.
Their body is a document-viewer iframe with an opaque viewer identifier; this
audit did not capture the rendered viewer or prove viewer-to-HWPX byte identity.
The named official HWPX attachment and collection request/capture chain are
verified; an iframe shell is not the original text.

The [KOGL authority's current type guide](https://www.kogl.or.kr/info/license.do)
explicitly recognizes Type 0 and permits commercial/noncommercial use and
adaptations without an attribution condition, while preserving moral rights.
The [portal's general copyright policy](https://www.korea.kr/guide/copyRight.do),
read November 3, still describes Type 1 as its standard text category, requests
specific attribution and a copyright-policy link, excludes third-party media,
and explains that agency releases flow in from their issuing institutions.
Thus Type 0 is not an invalid/missing mark; preserve the actual per-item Type 0
and satisfy the portal's attribution/link requests rather than relabel it Type 1.
These policy readings are current web observations, not hashed archival captures.

**Permitted now by IPR:** existing owner-gated private collection/custody,
read-only local integrity inspection, and verified official-link metadata under
[`config/korea_dapa_official_link_automatic_admission.json`](../../config/korea_dapa_official_link_automatic_admission.json).
Its prohibitions on public titles/text, media, translation/analysis and
model/email transmission remain in force. The shadow manifest's older one-time
wording is not the current schedule authority: the actual private workflow has
a distinct owner-approved recurring-access gate. That gate grants no reuse.

**Favorable publisher evidence, pending an IPR source-use decision:** text-only
reuse/adaptation of DAPA-authored material in the exact linked HWPX. Applying
the article's Type 0 notice to that attachment's DAPA-authored prose is a
documented interpretation, not an independently explicit attachment licence or
a verified viewer equivalence. No separate model-specific prohibition was found
in the observed notices/guide; that absence is not model authorization. A founder
decision may accept this documented scope interpretation, but cannot grant
third-party rights or waive a contrary document restriction.

**Still restricted or uncertain:** complete HWPX/PDF rehosting, embedded media,
unidentified third-party/joint-authored material, contact/personnel blocks,
image-only information, heading variations, semantic/table order, provider
retention/training conditions and new model spending. No publisher contact is
authorized. If attachment-text scope cannot be accepted on this evidence, the
precise missing clarification is whether the article's text-only Type 0 notice
covers DAPA-authored prose in its named HWPX for private third-party machine
inference and independently worded attributed English explanations; contact
would need its own authorization. Do not ask for a blanket whole-file licence.

### Recommendation for founder decision — not executed

Accept the documented Type 0 basis **only for DAPA-authored prose** in authentic
linked HWPX releases, starting with exact version `156786687` above. Authorize
an offline implementation candidate that can select and bind eligible prose,
exclude contact/media/uncertain material, and prepare private potential inputs
for attributed English machine explanations. Preserve the complete original
separately. Use `156785254` as an existing-evidence regression; retain the other
samples' stated review/failed-batch dispositions. Do not grandfather future
releases by issuer alone: inspect each version's notice, attachment identity and
exceptions. Once reviewed rules exist, routine eligible versions should not
need a new owner ritual.

The proposed decision should explicitly allow the **source uses** of private
inference/translation and public independently worded machine explanations,
while keeping public originals/media excluded. It should **not** activate those
uses: model calls require separately authorized provider/task/cost controls;
public delivery requires qualified code and applicable release authority. If
the founder declines the attachment-scope interpretation, preserve all work and
hold substantive processing pending the narrow clarification above. Neither
response changes existing link-only service.

No new adapter was added in this phase: the existing extractor already replays
the three database originals exactly; additional processing code cannot resolve
the unadopted source-use boundary. `core/korea_corpus_bridge.py` deliberately
accepts MND-only, already-public Type 1 originals; DAPA cannot be made eligible
by relabeling its issuer, copying it into MND's release index or publishing an
original as a bridge prerequisite. After the decision, extend the existing
source definition/private custody and shared lifecycle with a DAPA profile and
permitted-component projection, coordinating shared integration with #950.
Retain the current DAPA metadata handoff until a reviewed replacement is real.

**Verification/stop:** existing auditor's four synthetic negative/structure tests
pass; five genuine original audits, three stored-text equalities, 16 request-chain
checks and the metadata-only HTTPS inspection above are verified. No semantic
review or new source-to-reader acceptance is claimed. Full final-head CI belongs
to this review PR. Stop at this qualification; the next phase is the founder's
source-use decision, then one bounded offline implementation. Production merge,
activation, paid inference, deployment and subsequent new-release delivery remain
separate and unperformed.

## Current repair phase — 2 November 2026

**Engineering candidate; no merge, activation, paid call or deployment.** This
receipt supersedes the October 28 status below, not its source-use decisions.
Public base `cee4e74459f357a51137c177c29f28a8de3e2470`; private code main
`a3f6299bd783b9624d0754707572dbb89abdd860`; private MND archive
`f63e5a5bcb4df879f1f0b9933c2da00d33bd99e4`. PR #942 is merged; the dispatcher
migration in open PR #950 is separate. No workflow or private companion change.

### Observed source-to-reader frontier

- Private MND attempt [41351669676-1](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/41351669676/attempts/1)
  preserved 32 originals: eight selected/retrieved/extracted duplicates, complete
  listing, no collection failures. Offline authenticated replay re-extracted all
  32 HWPX originals and verified their article-local Type 1 text marks. All 19
  released Korean texts equal their private originals byte for byte. This is
  preserved-evidence validation, not a fresh terms check or grant.
- The tracked corpus ledger has 14 admitted records: two processed, two screened
  out, seven terminal QA-v3 holds and one QA-v2 hold still eligible for its exact
  #942 recovery attempt, plus two pending admissions. Two additional
  licensed originals are held at heading extraction.
- #942's first eight recovery outcomes are observed in the ledger and Daily
  logs: `156786043` passed; `156785691`, `156785888`, `156786154`, `156786296`,
  `156786587`, `156786906` and `156786935` remain held at their incremented
  attempt counts. `156786942` remains at QA-v2/attempt 1, eligible for its
  already-authorized one-time attempt. `156786938` was processed independently.
  Failed Daily [41334251491](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/41334251491)
  and [41531728940](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/41531728940)
  retained those outcomes; later green time-gated runs skipped the pipeline and
  are not additional processing evidence.
- Exact-source inspection of the retained failures found number findings on
  date/time lines (`156785691`: 5/9; `156786587`: 5; `156786935`: 6), an added
  number on `156786154`: 9, agreement findings on `156785691`: 11,
  `156785888`: 14, `156786906`: 12/13, `156786935`: 13, a glossary finding on
  `156786906`: 11, and a summary agreement finding on `156786296`. The current
  code discards failed translation entries and summaries; the inspected runs
  expose codes/locations but no retained failed output. These cannot honestly
  be classified as model errors or validator false positives. They remain held;
  neither the QA rules nor retry eligibility changes in this phase. The two
  accepted machine translations still pass no-cost QA replay. The reviewed
  benchmark still passes two releases and holds the added weekday annotation
  in `156785286` at lines 3/5.

### Repair and acceptance

`156786943` is a reproducible admission false positive: the authentic distribution
timestamp is `2026.10.29(목) 22:00`, without the final date dot required by
`core/korea_corpus_bridge.py`. The parser now permits that punctuation variant
while retaining the exact distribution label, weekday, time and heading guards.
It copies the existing source heading line and changes no original text or title
policy. `156786306`, a statement without that header, remains unidentifiable;
the chronology/research exclusion `156785161`, frozen baseline and reviewed
English exclusions remain intact. DAPA remains separately governed.

On a disposable copy of the base production DB, the actual bridge admits only
`156786943`, at pending/attempt 0, preserving every preexisting article, every
other ledger row and every other table. A second replay changes nothing. The
candidate order becomes `156786942`, `156786943`, `156786944`, `156787126`;
all existing terminal QA holds remain excluded. The public gate remains the
same four finished records; admission alone publishes no machine output.
Regression tests reproduce the former hold and recovery on authentic released
text, reject missing/ambiguous anchors and preserve an exhausted QA hold.

Current HTTPS bytes were independently compared with tracked output for the
Korea desk, original `156786943`, and both accepted machine record routes
`record/5520.html` and `record/5911.html`; all four match. Existing scheduled
[41456178068](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/41456178068)
also reports exact-byte readback of 19 originals plus the desk. **These verify
existing production content, not deployment or processing of this repair.**
Final-revision check results and commit identity belong to the review PR.

After an authorized merge, the next actual gated Daily pipeline can recover
`156786943` through normal admission and process the four eligible records at
the existing cap. Processing/QA or an account-level block may still hold an
individual result; reader delivery requires the normal final render, validation,
commit and deployment. No terminal QA hold is reset. Next bounded action:
review this repair and its exact-revision checks; after release authorization,
observe that normal cycle and read back any newly accepted record. Diagnosing
the terminal QA cohort still needs preserved failed output; do not purchase a
replacement merely to inspect it.

## Previous verification — 28 October 2026 (historical)

**ENGINEERING READY — RELEASE OR FOLLOW-ON VERIFICATION PENDING.** The repairs
below are a review candidate, not a production release. The October 18–19
checkpoint later in this document is historical. In particular, the private
cutover, Daily activation and watchdog have progressed since that checkpoint.
This procedure grants no source, spending, merge or release permission.

Verified against public main `cc25e3c88da3bc7afb9bca7a03f96e1dbfae7224`,
private main `c1cbff0c0aea493957d156d973c872174d5fd3fd`, their current Actions,
immutable private archive tips, tracked production SQLite, Pages and HTTPS.
Shared `PROJECT_STATE.md` was left untouched while other desk PRs are open.

| Stage | Observed state |
| --- | --- |
| MND collection/custody | Genuine scheduled [40587103070](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/40587103070), nominal October 27: robots read, complete October 21–27 listing, 7 selected/retrieved/extracted, 1 inserted, 6 duplicates, no failures, 25 stored. Private readback passed. Archive `cfe7ed77084290cf73de85e5325d1a5cd8a3d711`; independently verified all 164 capture hashes and the source/HWPX inventory. |
| DAPA collection/custody | Genuine scheduled [40614736442 attempt 1](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/40614736442/attempts/1), nominal October 27, executed October 28 UTC: robots read, complete one-day listing, 1 selected/retrieved/extracted/inserted, no failures. Original `korea-dapa-policy:156786687` is preserved at `f268cc5720469bb0788cea4d359aea2bac4c9d1d`; all 13 capture hashes verified. Collection and independent custody readback succeeded; the subsequent metadata export failed. |
| Public links | Production contains 20 MND + 1 DAPA records. Four additional eligible MND identities remain private: `156786154`, `156786296`, `156786306`, `156786587`. The metadata publisher admits them in runner scratch, then fails its obsolete render-count assertion before committing. The new DAPA identity has not reached public admission. |
| Licensed MND text | Eight original texts are public. The latest scheduled genuine new-text release, [39696987609](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39696987609), released three originals and verified actual HTTPS. Current scheduled [40609331696](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/40609331696) stopped with an undifferentiated `HOLD`; its exact cause is not recoverable from that receipt. Preserved-source replay against disposable index/text copies and the current official policy qualified the four pending originals, without production writes. This does not prove the scheduled runner's next attempt. |
| Shared Daily | `KOREA_DAILY_AUTOMATION_ENABLED=true` (since October 21). The registered Korea profile and source-version bridge are active. Five corpus admissions exist: three QA-held, two screened out; zero completed machine analyses. Processing is configured and prior paid attempts are recorded, but a successful machine-analysis-to-live continuation is unverified. |
| Reviewed English | Three reviewed translation/analysis pairs remain public and source-pinned. They remain excluded from machine admission; the existing supersession rule is unchanged. |
| Monitoring | Scheduled private-ledger watchdog [40690021177](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/40690021177) passed for the mature October 27 MND slot. It truthfully retains earlier missing slots, including October 22. That failure and DAPA's corresponding failure were Python 3.9 setup on Ubuntu 26.04, before collection; current private workflows already pin Ubuntu 24.04. They were infrastructure failures, not publisher denials or quiet days. DAPA Actions exposes the present handoff failure; recipient delivery of operational notifications was not tested. |

The enabled private variables were independently read as true:
`KOREA_MND_PRIVATE_COLLECTION_ENABLED`, `DAPA_DAILY_ORIGINAL_ACCESS_APPROVED`
and `DAPA_METADATA_BRIDGE_ENABLED`; public `DAPA_METADATA_BRIDGE_ENABLED` is
also true. No variable or secret was changed, and no secret value was read.
Recent publisher logs prove authenticated private MND read access works.

### Confirmed defects and review candidate

1. DAPA's exporter required `target_date_source=explicit`, rejecting a genuine
   `schedule-slot` after successful collection. It now also accepts a first
   scheduled attempt whose preserved timezone-aware start independently
   resolves to the declared date at the existing 22:17 UTC slot. Unknown/manual
   inferred dates, ambiguous reruns, missing timezone and mismatched dates
   remain held. Exact attempt commit, receipt, complete batch, originals,
   issuer, HWPX replay, signature and public metadata-only checks stay intact.
2. Both MND publisher render gates expected a bare link for every nonhistorical
   DB identity. The renderer already represents finished Korea corpus records
   at `record/<id>.html` and removes their duplicate bare links. The checks now
   use the existing corpus publication gate, require each record route, and
   still reject missing/duplicate link entries. The two currently screened-out
   corpus records are finished records under that existing gate; this repair
   changes no relevance, analysis or rendering policy.
3. The original-text CLI now reports fixed gate reason codes on a global hold,
   allowing policy/access/source faults to be distinguished. Arbitrary parser,
   filesystem or source-bearing exception text is never logged. No retry or
   rights check was relaxed to explain the historical generic failure.
4. The original-text PR's historical public-source replay still expected every
   subsequently published original in the retired public archive. It now
   verifies all fourteen baseline identities and every overlapping published
   text hash, explicitly reporting later private originals as unverified by
   this historical replay. Production still authenticates the private archive.

The private workflow reads the exporter from public main, so no private
companion change is necessary. No new scheduler, model engine or renderer.
No production DB/output, public source index, reviewed English or retry state
was changed by this phase.

### Acceptance evidence and remaining action

- Focused offline checks: 37 collector/export/publisher contracts and 135
  watchdog/shared-Daily/corpus/QA/render/retry contracts passed. The tests
  execute both actual publisher post-render Python blocks and reject missing
  and duplicate rail entries, not just YAML string shape. Mandatory final-head
  full CI is recorded in the review PR; focused success alone is insufficient.
- Replayed the exact new private DAPA evidence through the repaired exporter,
  signed with a disposable test key and admitted to a disposable SQLite schema:
  1 new record, then 0 new / 1 unchanged on retry. No source title, text, media,
  translation or analysis was exported. This proves engineering recovery,
  not a production signature, public dispatch or deployment.
- Independently verified registered text SHA → renderer → main output → Pages
  → actual HTTPS: 8 originals + desk (9 paths), and 3 reviewed English/analysis
  pairs + desk (7 paths). Existing scheduled production readback
  [40681116462](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/40681116462)
  also passed. The live [Korea desk](https://indopacificrecord.org/korea.html)
  shows the existing 21 metadata records, 8 originals and 3 reviewed pairs.
- Production QA holds under `kr-qa-v2` and the v3 translation prompt, in
  first-seen order: `156785691` (attempt 3,
  `qa_agreement_unsupported,qa_number_added,qa_number_missing`), `156785888`
  (attempt 3, `qa_agreement_unsupported`), `156786043` (1,
  `qa_glossary_term_missing`), `156786154` (1,
  `qa_glossary_term_missing,qa_number_added,qa_number_missing`), `156786296`
  (1, `qa_glossary_term_missing`), `156786587` (1,
  `qa_number_added,qa_number_missing`), `156786906` (1,
  `qa_agreement_unsupported,qa_glossary_term_missing`), `156786935` (1,
  `qa_agreement_unsupported`) and `156786942` (1,
  `qa_number_added,qa_number_missing`).
  `kr-qa-v3` corrects month.day dates such as `10.13.` (previously read as
  decimals) and logs held findings as `code@line`; the ledger keeps codes alone.
- Owner-authorized (November 1, 2026) one-time paid re-run under `kr-qa-v3`:
  `QA_V3_RERUN` in `processing/korea_shared_queue.py` names exactly those nine
  identities and their hold attempt counts. A row is selected only while it is
  still `qa_held` with `qa_version = kr-qa-v2` at that count. Any dispatched
  outcome writes `kr-qa-v3` and increments attempts, so a further hold is
  terminal. For `156785691` and `156785888` this supersedes the earlier
  no-fourth-attempt rule for this one call only. Nothing is reset in the DB;
  the re-run happens only through the gated Daily lane after merge, at the
  processing cap (default 4 per run, so about three Dailies in FIFO order).
  `156785986` and `156785987` were screened out on their first attempts.
  None of those outcomes was reset. The chronology hold `156785161` persists.
- Public Daily [40565258649](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/40565258649)
  failed its full suite on two Japan navigation assumptions before processing;
  this phase does not alter Japan PR #892 or presentation PR #895. Current
  base failures are distinguished from the Korea repair's CI in the PR.

Next: review the final-head PR and authorize its merge/release separately.
After release, the existing private `retry_verified_metadata` operation can
recover DAPA attempt `40614736442-1` without fetching originals again; it still
requires the applicable dispatch authorization. Observe existing MND publisher
schedules and the shared Daily, then verify newly admitted identities on actual
HTTPS. New paid model attempts, production dispatches and deployment were not
authorized or performed here. Existing per-record QA holds and DAPA text/model
restrictions remain individual dependencies. A new licensed-original replay
or a configured trigger is not verified unattended machine-analysis publication.

## October 18–19 checkpoint (historical)

## Normal operation

- MND: the public legacy collector is a no-source tombstone. The private repo
  `ipr-source-evidence-private` is the sole writer and custodian of
  `archive/korea-policy-briefing`. Its `korea_mnd_private_first_collector.yml`
  runs at 17:47 UTC (six-day lookback, cap 40) with
  `KOREA_MND_PRIVATE_COLLECTION_ENABLED=true` (set October 19, 18:40 UTC). MND
  is excluded from the private fast-forward mirror. The first genuine scheduled
  run, [39329889889](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/39329889889)
  (`schedule`, slot attributed to October 19, started 21:44 UTC, about four hours
  after the 17:47 slot), succeeded: robots read, 10 listed and retrieved, 10
  duplicates, no failures, 17 stored, ledger and independent readback preserved
  at `0fe16d7708`. GitHub cron delay on these repositories is routinely hours.
- DAPA: private `korea_dapa_private_first_collector.yml`, 22:17 UTC, one logical
  UTC day, no lookback, at most five complete article/HWPX pairs. Private
  `DAPA_DAILY_ORIGINAL_ACCESS_APPROVED` and both repositories'
  `DAPA_METADATA_BRIDGE_ENABLED` were independently read as `true`.
  Both required private secret names exist; values were not read or changed.
- Retain the existing official-link and standing-original-text publishers.
  Their completion hooks must match the collector's actual workflow name.
  Their existing daily fallback schedules remain; do not add another writer.

## One-writer MND private cutover — completed October 19 (record)

All steps below were executed on October 19, 2026: public PRs #825/#826 and
private PR #18 merged (private merge 17:28 UTC), the public read token was
fixed after a 403 on the first publisher dispatch (18:24 UTC) and both
publishers then passed, and the private gate variable was set at 18:40 UTC.
Retain this order only as the record or for a future re-cutover.

Owner approved private GitHub custody as the primary archive and accepted that
this is not an independent off-provider disaster-recovery backup. Do not claim
otherwise. The historical public branch remains in Git history; no force-push,
erasure or secret rotation is implied.

1. Before merging either PR, confirm that public and private MND branches
   have the same final legacy tip and all legacy/public mirror jobs are idle.
   Record that exact commit and verify the existing immutable source/DB/ledger
   equality. A private mirror is not itself proof of independent backup.
2. Provision a **fine-grained token with Contents: Read on the existing private
   evidence repository only** into the PUBLIC repo Actions secret
   `IPR_KOREA_PRIVATE_READ_TOKEN`. Do not print its value.
3. Merge the PUBLIC companion first. It retires the legacy collector and
   changes both existing publishers to clone the private archive into
   ephemeral runner scratch. Check the scheduled publishers are able to
   read the exact preserved private source; no raw evidence reaches Pages.
4. Merge private companion PR #18 only after the public writer is retired
   and source history is still identical. This removes MND alone from the
   old fast-forward mirror and stages one private daily writer. It must not
   disturb DAPA, Indonesia or the seven other mirror families.
5. Finally, enable `KOREA_MND_PRIVATE_COLLECTION_ENABLED=true` in PRIVATE
   repo Actions variables. Check the next scheduled genuine private MND run
   or deliberately authorized single-day manual run, its Git attempt
   commit/readback and SHA-256 original preservation.
6. Run the existing official-link and licensed-Korean-text publishers (or
   observe their existing daily fallback); verify production SQLite,
   generated Korea HTML, Pages and actual HTTPS. A genuine zero-new day
   proves collection operation, not a new source's admission.
7. If a token, provenance, source, completeness or concurrency check fails,
   hold publication and diagnose the precise issue. Do not silently
   reenable the old public original-bearing writer or the mirror.

The private writer has no authority to widen source access, reproduce
restricted HWPX/media, auto-publish DAPA text or change reviewed English.
Manual source recovery does not rewrite historical scheduled failures.

## Quiet day, failure and recovery

1. Check actual Actions repository, event, attempt and selected desk. For DAPA,
   require a real scheduled first attempt and the private attempt receipt plus
   collector ledger at an immutable commit. A green contract-only job proves
   no collection. The existing MND slot watchdog reports missing mature slots;
   check private Actions/receipts separately for DAPA missing slots/failures.
   The Operations Center declares the private DAPA schedule without attesting
   its execution. Never interpret absent receipts as a quiet publisher day.
2. `ok_no_publications` requires robots and a complete filtered listing.
   `ok_all_duplicates` can also be healthy. Neither should manufacture a signed
   packet or dispatch a publication. Failed/partial retrieval remains failed.
3. The MND repair permits one additional transient request TOTAL across
   listing/article/HWPX per collection, after the existing crawl delay. Its
   separate single robots-timeout retry remains. Denials/challenges, redirects,
   TLS failures and malformed responses gain no retries. Incomplete batches
   still preserve the prior database and must not publish.
4. For MND recovery, compare preserved identities before fetching originals
   again. Use the existing bounded explicit-date manual recovery only within
   approved source-access policy. Do not rerun a historical event and guess its
   date. Manual recovery never repairs a historical scheduled result.
5. After successful private DAPA capture but failed publication, use private
   `retry_verified_metadata` with the exact saved `source_run_attempt` and no
   original-access approval. It rereads existing evidence, without fetching a
   government original. `scripts/korea_dapa_private_recovery_plan.py` separates
   this from failed/missing capture. Failed source attempts cannot publish.
6. After a main commit but failed Pages/readback, inspect the existing release
   guards and retry the established publisher. Independently compare current
   SQLite identities, generated Korea HTML, Pages bytes and HTTPS. A successful
   main commit alone proves no deployment. Preserve concurrent main changes.

## Editorial action

Production metadata is URL/date/issuer evidence, not reviewed research. Existing
MND staging yields version-pinned candidates without source body/title export.
The standing original-text publisher checks identity, HWPX parity, text licence
and exceptions before releasing eligible future MND text. The private English
handoff selects published originals without delivered/reviewed English; human
review controls release. Preserve the three existing reviewed pairs.

DAPA recurring access and link permission do not authorize original text,
translation, analysis, media or paid models. Its private evidence must receive
source-specific rights and Korean-language review before those treatments.
Revisions, missing evidence and disputes require actual review. MND
`korea-policy:156785161` retains its chronology hold.

## Verified evidence and remaining release boundary

- Failed MND scheduled `39159889610` stays failed. Its `156785190` original is
  preserved and admitted (text SHA-256
  `c92b0faebb5eac473a96d9b4037bd91c8b5cd97257c970eff694160d24075d7e`).
- Genuine private MND run
  [39304457445](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/39304457445)
  (`workflow_dispatch`, target date October 19, collector `2a710132f4`): robots
  read, six-day listing proven (10 listed), 9 duplicates, 1 new record
  `korea-policy:156785691` (HWPX retrieved; text SHA-256
  `66931c2d0f4d9d187cbe17d68a124882a3e6ed4a5c059754639dbcd0e1697cf8`), no
  failures, 17 stored. Private archive tip `02090fc258bedc4bcadc0c788e078fa8b56afc05`
  with independent clone readback (fsck, SQLite integrity, capture SHA-256 names).
  It is a manual run and does not attest the schedule.
- Before that run, production had 15 MND + 1 DAPA link records, 3 licensed
  originals and 3 reviewed English/analysis pairs, identical on `gh-pages` and
  HTTPS (`korea.html` SHA-256
  `b9f3e7380838fa204f07f5d197a5480ae4dac741d5de9b561968a909a9e6ba14`). Held
  by decision, not defect: `korea-policy:156785161` (chronology exception,
  link-only on the historical bibliography, absent from the production table).
- `156785691` admission and release. The nominal 20:37 and 21:17 UTC scheduled
  publishers had not run by 23:43 UTC on October 19 (recent nights ran about two
  hours late), so it was absent from `main`, `gh-pages` and HTTPS. With the
  owner's explicit one-time authorization (October 19, 23:51 UTC) the existing
  workflows were dispatched manually on `main`, link publisher first. This
  proves the publication pathway, not unattended operation. The link fallback
  subsequently ran successfully as a genuine `schedule` event at 23:55 UTC,
  [39344495959](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39344495959):
  0 new, 16 unchanged, `156785161` still held. The scheduled text fallback and
  DAPA evening slot remain unobserved at this checkpoint.
  - Links, [39344115247](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39344115247):
    pinned private source `0fe16d7708471a6e019a7e5618fb8c9e9768dd11`; admitted 1,
    unchanged 15, `explicit_exception_held` 1 (`156785161`); validator passed
    with the usual 10 warnings. Main commit `137c8b93c2`, `gh-pages` `3a2decb365`.
    Production table: 17 rows (16 MND, 1 DAPA), `156785691` is
    `official_link_only`, admitted 23:52:16 UTC.
  - Text, [39344401457](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39344401457):
    1 new original, 0 held, 14 historical excluded. Main `7347a530e3`,
    `gh-pages` `edc0e2ce7d`. The released text SHA-256 equals the private original
    (`66931c2d…97cf8`). Workflow HTTPS byte readback passed; independently,
    `korea-originals/156785691.html` returns 200 and `korea.html` shows 4
    licensed originals and 3 reviewed English pairs.
  - English owner handoff, workflow_run [39344660562](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39344660562):
    one private draft delivered to the owner only at 23:59:07 UTC (draft SHA-256
    `5a6834fd1821…`, receipt `4f5dbaa4e3`). No reviewed JSON exists and
    `korea-translations/156785691.html` returns 404: nothing English is public
    until human review and the owner release dispatch.
- Known stale check (not changed here): `korea_shadow_slot_watchdog.yml` reads
  the frozen public `shadow/korea-policy-briefing` branch (tip `cac1f02fb7`, last
  ledger October 16), so it reports "no successful scheduled-run ledger" and has
  failed daily since cutover (e.g. `39256411507`). That is a false alarm about
  public custody, not an MND collection failure; private receipts above are
  authoritative. Retargeting it to the private archive is a separate fix.
- Genuine private DAPA scheduled run
  [39179758230, attempt 1](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/39179758230)
  started October 18 at 8:12 PM EDT (October 19 00:12 UTC), correctly attributed
  the delayed execution to October 18, read robots and a complete zero-result
  listing, preserved `ok_no_publications`, independently read back custody,
  and skipped signing/dispatch. Workflow SHA:
  `cf0a556ea2f8f81e8e07fafe467172a9de485f64`; collector SHA:
  `f3ff927b32ebf857e930270e6641fc7abd8a7047`; private receipt commit:
  `7a03ac11555b0d301c64bf5953c255825e988eb5`.
- Reuse DAPA `156785254` acceptance: private `39147821179`, public
  `39147918490`, production `520d661cae4553f273a53a79215976e12807b799`.
  No reimport was performed. SQLite has 15 MND and one DAPA metadata record,
  three licensed originals and three reviewed English/analysis pairs. Existing
  HTTPS returned 200 and matched Pages SHA-256
  `d06dcf7c10be11b579f6b3a2c12e73659e1a6ca0bd28ba32d340121be60ac405`.
- The MND retry, publisher-hook repair and one-writer cutover are merged.
  Preserve historical exposure and failed receipts. Tests authorize no further
  merge, production DB write, schedule or permission change, or editorial
  publication; English release still requires the human review and owner
  dispatch described in `KOREA_ENGLISH_TRANSLATION_ANALYSIS_RELEASE_2026-10-15.md`.
