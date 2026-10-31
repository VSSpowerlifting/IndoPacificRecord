# Kemhan Berita shared Daily — authorized release, 27 October 2026

> **Desk architecture/process supersession — 30 October 2026:** the
> [mandatory shared desk standard](../desks/README.md) governs every current and future
> desk. This document's older common architecture, onboarding order and launch
> clocks do not override it. Source-specific decisions, restrictions, real
> evidence and still-used commands remain valid in their actual scope. This
> notice does not claim runtime migration, change permissions or activate a source.


The owner approved the narrow standing source-use, spending and controlled
release decision on 27 October 2026; see `DECISION_LOG.md`. Public #891 merged
as `455a1c73f58cf4d8bd0f41474b94a0dd14ee5114`; private #26 merged as
`c1cbff0c0aea493957d156d973c872174d5fd3fd`. The three public policy switches
are true, but `KEMHAN_DAILY_ENABLED` remains absent/disabled. First live
processing exposed the quality blocker below; no explanation was signed or
published. The repair phase permits offline work and one checked PR only:
no paid calls, merge, activation or publication.

## Scope and implementation

Only `id_kemhan_news`, from the existing private `archive/indonesia-kemhan`.
The shared `pipeline.py --private-daily-source` route verifies immutable Git
custody, history, capture hashes and metadata candidates, then binds originals
to unchanged, already-admitted public metadata. Kemhan uses its explicit
Indonesian profile, outside the public-original article queue. Relevance is
Indonesian defense/security content; routine ministry ceremony need not pass.

The existing two-call Analyzer path screens relevance, then translates only
the two cited passages privately while composing two independently worded
English factual sentences. The model returns passage IDs; code resolves them
to the exact original. Private translations and evidence spans never enter the
public database, queue ledger or signed envelope. No full-article translation,
China prompt, new model engine, renderer or article corpus is introduced.

The per-sentence QA checks attribution, exact quantities/unit identifiers,
semantically equivalent calendar dates, names,
source-supported geography, Indonesian negation/plans and completed-action
language. Initial output has no model significance flag. These conservative
checks **do not certify arbitrary bilingual meaning**; real model quality must
be checked at first authorized release. Genuine discrepancies are held by
record/version. Yonif TP 880 remains excluded in policy and code, even if an
excluded-list entry is mistakenly removed. Changed/missing originals,
third-party credit lines, mismatched institutional metadata and existing
terminal/paused holds cannot become automatically eligible.

The existing shared machine-record table, HMAC domain, Archive/search,
`record/source-*.html`, Daily intake and main/Pages publication writer are reused.
Indonesia shows the latest five released explanations alongside its admitted
links, with all explanations searchable in Archive. Records disclose private
Indonesian translation, source version and model/prompt. Existing English
Philippines records retain their language disclosure and desk assignment.

## Observed source-use basis and approved decision

Read-only checks on 27 October:

- The [Kemhan Berita listing](https://www.kemhan.go.id/category/berita) identifies
  the ministry and carries a ministry copyright footer. No affirmative general
  reuse/external-model licence was found on that page. Public access, and the
  collector's successfully enforced access/robots checks, do not themselves
  establish reproduction or external-processing rights. No new crawl or access
  workaround was used for this integration.
- The [Copyright Act published by Kemhan](https://www.kemhan.go.id/ppid/wp-content/uploads/sites/2/2016/11/UU-28-Tahun-2014.pdf)
  includes attribution-conditioned current-news use in Article 43(c). That
  supports considering a narrow factual-reporting product; it is not evidence
  of an explicit licence for sending whole articles to an external model or
  publicly distributing translations. The proposal below is an editorial
  source-use judgment for approval, not a claim that government text is public
  domain or that a statutory exception automatically settles every use.
- Anthropic's commercial API states that inputs/outputs are
  [not used for training by default](https://privacy.claude.com/en/articles/7996868-is-my-data-used-for-model-training)
  and describes [30-day standard retention with exceptions](https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data).
  This proposal accepts that external processing/retention boundary; it does
  not assert that IPR has zero-retention terms. No feedback/training opt-in,
  Files API retention, consumer service or new credentials are proposed.

**Owner-approved source-use scope (27 October 2026):** Approve standing private commercial
API processing of verified first-party Kemhan Berita Indonesian text, including
translation of cited evidence when needed, solely to produce short factual
English explanations. Approve unattended release of QA-passing, independently
worded, precisely Kemhan-attributed machine explanations of at most 90 words,
with canonical source link, publication date, evidence/version binding and
machine disclosure. Accept the API handling described above. Retain private
original custody; exclude public original titles/bodies, full translations,
quotations, media, PDFs, third-party republications, disputed/revised versions,
Yonif TP 880 and human Briefs/editorial analysis. Retain the existing metadata
approval as a separate grant. Recheck/hold affected uses if access or publisher
restrictions change. Correspondence is required only if an actual restriction
or rights uncertainty cannot be resolved within this narrow decision.

**Owner-approved spend limit:** $0.35 estimated per invocation, at most one record and
two calls (Haiku relevance: 500 output tokens; Sonnet reading: 2,200). The
shared guard reserves conservative UTF-8-byte input plus 2,048 framing tokens
at repository-pinned prices before each call; SDK retries are disabled.
Maximum original input is 16,000 UTF-8 bytes. Existing retry budget is five
observed failures, then paused; this bounds a version's failed processing to
$1.75 estimated before an explicit resume. Normal Indonesia-triggered
processing runs only after its collector succeeds; unrelated AFP/NSC events
cannot add Indonesia calls, and Indonesia events cannot add AFP/NSC calls.
Manual dispatch is separately authorized operation, not an extra standing
schedule. This is an estimated reservation, not an invoice or a claimed daily
billing limit. No historical archive-wide backfill is requested.

## Activation after one explicit owner release decision

The owner has explicitly authorized these steps after final-head checks, as
recorded in the decision log. Preserve all exclusions and limits below.

1. Record the actual owner decision; set only Kemhan's three existing policy
   booleans (`private_model_processing`, `public_machine_explanation`,
   `unattended_release`) true in `config/philippines_daily_policy.json` and
   replace its proposed `owner_decision` with the real authorization. Review
   and merge through the existing required PR checks. No source-specific
   licence framework or routine per-item approval is needed.
2. Merge the private companion into private main. It reuses the public main
   processor, the existing state branch and `KEMHAN_BRIDGE_KEY`. The shared
   Daily HMAC domain differs from the metadata-envelope domain. Public Daily
   maps `DAILY_ID_KEMHAN_NEWS_KEY` to that existing secret. No new credentials.
3. Enable the private family's gate, then run the existing workflow:

   ```sh
   gh variable set KEMHAN_DAILY_ENABLED --body true -R VSSpowerlifting/ipr-source-evidence-private
   gh workflow run shared_daily_processing.yml --ref main -R VSSpowerlifting/ipr-source-evidence-private
   ```

   Both repositories' `IPR_PRIVATE_DAILY_ENABLED` and the metadata bridge
   variables were already true when checked. Do not toggle or replace them.
4. Inspect that private run's ledger, source binding, quality result and actual
   English output. A private `--private-daily-no-release` inspection with the
   existing local API credential may precede signing; preserve its queue without
   resetting attempts or reprocessing the inspected record. Then allow the
   ordinary public Daily or, if explicitly
   authorized, dispatch the existing public `daily_update.yml`. It fetches the
   signed public-safe output, admits it, renders, validates, reconciles and
   publishes through its existing writer. Confirm exact DB/desk/record/Archive/
   search agreement on deployed HTTPS and verify the next collector-triggered
   eligible record (or legitimate no-op) follows automatically. First-result
   inspection is a release check, not a standing per-article approval ritual.

Disable `KEMHAN_DAILY_ENABLED` to stop future processing. Policy revocation
also prevents processing, signing, public admission and public rendering. Use
existing explicit queue recovery for real exceptions; do not reset terminal
holds or replay the entire archive.

## Verification receipt

Real immutable private pin `d9ad1ce4421ea274cff3c2d7dda797dac6d7a6e8`:
50 captured records validate; 49 bind to the actual public link versions;
Yonif remains absent. On a disposable database copy, the actual Analyzer with
**mocked relevance and reading responses** produced one signed explanation;
shared admission added one row, replay added zero, other desks and production
DB bytes stayed unchanged. The production renderer reconciles its Indonesia
desk, individual machine record and shared Archive/search index. The mock
translation is explicitly a plumbing stub; this proves no live translation or
model quality, and nothing was published. Focused regressions cover the
Indonesian profile, rights holds, attribution, original evidence bindings,
numbers/names, negation/action status, geography, retained anomalies,
relevance rejection, cache/version holds, bounded retries, signing and other
desks. Focused public run: 67 tests passed, plus the Kemhan validator regressions;
private workflow contracts: five tests passed. Chromium at 1280/375 found no
horizontal overflow on desk/record and found the record through Archive search.
Indonesia HTML+CSS is 104,481 bytes (120,000 cap); the record is 57,091 bytes.
All 2,369 routes pass delivery budgets. The isolated production publication
render passes the validator with seven warnings; unchanged committed output
passes with its ten governed warnings. Exact-revision CI is recorded in the
PR description. No generated output or content-data changes are committed.

The first PR CI run exposed two stale Japan navigation assertions. Both fail
on the unchanged base `11df894846` in a disposable worktree: they treat the
historical seven-PDF directory as the entire admitted Japan index and claim
all Japan production is held. The bounded CI repair scopes the historical
parser to its existing section and checks original-text/model holds against
the actual admitted metadata state. All seven navigation tests pass locally;
no Japan data, policy or renderer changes are included. Required full CI runs
again on the final revision because this observed failure justified it.

## Live failure diagnosis and bounded repair (28 October UTC)

Private immutable source pin `97668de31f0c01e8d000ad71518c16caac18f670` and
all three retained rejected readings were located and hash-checked. These are
actual parsed Analyzer/QA inputs, including exact resolved source evidence and
private translations; the original HTTP/SDK response envelopes were not retained.
No rejected response was reconstructed. The private custody history, capture
hashes and public-admitted metadata bindings validate. The remote queue still
matches private state commit `63f79b71439b7b7deca2e416f1f8b8f99bcf2018`.
Source bodies and rejected readings are absent from public code, logs and CI
artifacts. Private reproduction and detailed receipts remain under the owner's
private `kemhan-release-20261027` evidence directory.

Both medical-evacuation readings fail only the redundant summary equality
contract under v1: independently generated summary text differs from the two
fact sentences, which total 65 words. The industry reading has 93 fact words
hidden behind a shorter 58-word summary; merely joining those facts must still
fail. Replaying every applicable check also finds claims/names outside the
cited passage and an unsupported completed action. Its private translations
complete cut-off source fragments with bracketed additions. The named-month
event date is semantically equivalent to the numeric source date; v1's literal
numeric/name comparison incorrectly calls that formatting a date defect.
Changed dates and use of the later publication date remain prohibited.

The `id-relevance-v1+id-analysis-v2` repair asks for exactly two attributed fact
sentences and their private translations, with no independently generated
summary. Code joins all fact sentences; the existing quality gate validates
each fact and the complete 90-word budget before any output persists. Unexpected
summary fields fail instead of silently discarding potential extra claims.
Evidence IDs resolve only to exact complete paragraphs/sentences of at most
500 characters; longer single sentences are unavailable, never sliced or
completed. Other desks retain their existing passage builder and contract.
Date comparison accepts equivalent Indonesian/English month and numeric formats
while retaining exact quantities and unit/model suffixes. Both private and
public fields must retain supported action status and negation. Private
translations cannot insert source names from another passage or bracketed
completions. Observed industry concepts require local source support. These
bounded checks do not certify arbitrary bilingual semantics; a future real
v2 reading still requires the authorized first-release inspection.

Private offline replay distinguishes unchanged rejected inputs from a diagnostic
projection that only joins their fact sentences and selects the v2 rubric.
That projection passes both medical readings; the industry reading still fails
word count, evidence locality, private-translation and action-status gates.
It is not a new model result, a queue recovery, or release authority. Public
regressions use explicitly synthetic text and fake calls, alongside this separate
actual-artifact replay. No paid call or queue write occurs in the repair.

### Controlled-release checkpoint

The source-version key still hashes only metadata/content/capture versions,
not the prompt. No retry accounting or queue recovery code changes. Failed
attempts, relevance rejection and terminal/paused/held states are preserved.
The public admission allowlist accepts v2 only; no v1 Kemhan output was released.

| Affected source version (queue digest) | Failures retained | Attempts remaining before five-failure pause |
|---|---:|---:|
| Medical evacuation: `4269fad7a8154336314b59d88e9bf5498227bcb05cc85b89c4b46c16fafa5ec1` | 2 | 3 |
| Defense industry: `8788720e8689b1cc24da5d99b2937a507a2f775f48f5eb2053e4cbc7f6460824` | 1 | 4 |

After repair review and final-head CI, resume controlled release only in its
separate authorized phase. Reuse the real private queue without resetting
attempts; obtain a genuine v2 reading through the same two-call, one-record,
$0.35 reservation path, inspect it privately, and publish only if QA and manual
first-result checks pass. Do not relabel or publish the old diagnostic readings.
The source-use approval remains valid. The private family gate stays disabled
throughout this repair; source-to-live and automatic follow-on are unverified.


## Office-title and copied-credentials repair (28 October 2026)

Public #893 is merged as `e31977934fcf62ce32790aa37c352a920a990d8a`.
One subsequent genuine v2 medical reading used two calls (2,735 input / 608
output tokens, estimated $0.014187); no explanation was signed or published.
The controlled inspection first rejected English “Head” for Indonesian “Kepala”
and also found a 15-word normalized name/rank/credential sequence. Private queue
`26d903c2d5c8da5a6196f7301536cb82f3b1108f` now retains three medical failures
(two attempts left) and one industry failure (four left); source-version digests
above are unchanged. `KEMHAN_DAILY_ENABLED` remains absent/disabled.

This repair phase permits offline implementation, verification and one review
PR only. Prompt/QA v3 adds a narrow Head-of appositive check: the institution
and complete named holder must match the same cited Kepala role. Only the
observed rank/honorific prefixes may be omitted; spelling and identifiers are
not normalized or rewritten. Unsupported forms, changed institution/actor and
acting/deputy/former qualifications remain held. The check uses a local lexical
projection; it does not edit generated public text or copying inputs.

Generation separates faithful private passage translation from minimal public
actor identity: keep substantive actors, institutions, roles and actions;
omit unnecessary public credentials, honorific stacks and extended ranks.
Names and identifiers that remain must be accurate. The existing 12-word
copying threshold and complete-sentence prohibition are unchanged, with no
name exemption, padding or cosmetic identifier edits.

Full private predicate replay reproduced both observed failures and exposed
another previously masked check: the private translation expanded a named
office abbreviation using a name absent from that passage. That existing
local-evidence gate remains unchanged; the prompt keeps named abbreviations
literal. The unchanged retained reading still fails copying and private-name
locality, plus old-prompt provenance under v3. A labeled diagnostic that omits
public credentials and retains the local private abbreviation passes every
applicable QA predicate. It is an edited offline example, not a new model
result, recovered reading, queue recovery or publication authorization.

Public regressions contain synthetic actors/evidence only. They cover local
Head/Kepala with holder/institution parity, wrong office/actor, cross-passage
support, role qualifications, copied credential sequences and a concise
alternative. Existing date, negation, action-status, rights, copying and retry
checks remain. Focused Indonesia/Philippines/date checks: 95 passed. Source
versions exclude prompt revisions; medical/industry counts and all
held/paused/terminal entries retain their existing treatment. Public admission
accepts v3 only; no Kemhan machine result has been released. Private originals,
translations and replay receipts remain outside public commits/logs/artifacts.


The #899 amendment fixes ordinary clinical “head injury/injuries” falsely
entering office validation. It requires the medical term in the same cited
passage (Indonesian `cedera kepala` or the literal English term). Office
mentions in the same fact still require the unchanged institution/holder
binding, including lowercase forms. Copying uses the unmodified public fact;
no general Head whitelist or capitalization bypass is introduced. Synthetic
regressions cover medical usage, absent/cross-passage medical support, mixed
medical/office usage and lowercase supported/rejected office titles.


## Institutional-name consistency repair (28 October 2026)

The genuine v3 result after #899 remains held: a public fact used a title-only
institution abbreviation, while its cited passage spelled out that institution.
No other applicable v3 QA defect was found. Private queue
`89d23af8974dd360c9369a0add446c18104a6a08` preserves four medical failures
(one attempt left) and one industry failure (four left). This offline repair
authorizes no new calls, queue recovery, merge, activation or publication.

**One institution-name rule for both fields:** use the exact institutional form
present in the cited passage. Do not independently abbreviate, expand, translate
or substitute an alias using knowledge, the title or another passage. No
institution-translation glossary is enabled for this profile. Existing supported
Head/Kepala and medical vocabulary checks remain; they confer no institution
alias permission. The fixed public Kemhan publisher attribution remains separate
from the reported actor's name. Private translations retain original institution
forms while translating the surrounding evidence.

Prompt/QA v4 reuses the unchanged passage-ID/fact-reference contract. Each input
passage carries locally computed literal formal-name/initialism hints; reading
input excludes the title. The model still returns exactly two facts with their
existing sentence, evidence ID and private translation fields. The validator
recomputes local forms from the resolved original passage, never a model-supplied
name list, and applies the same comparison to public and private text. Names in
the hints are literal source spans, not generated aliases or obligations to copy
every name. Parenthesized forms stay separate; a name may not be assembled from
pieces found across punctuation or other passages. A conservative Kemhan/formal
institution vocabulary and initialism grammar bounds this assistance; it is not
general entity resolution or a certificate of arbitrary bilingual semantics.
Generic translated nouns are distinguished from formal institution names.

Public regressions use synthetic institutions and cover full name to unsupported
acronym, acronym to unsupported expansion, untranslated exact local forms,
English translations (including lowercase formal names), wrong institutions,
cross-passage borrowing and assembling names from individually present words.
Office-holder identity, copied credentials, clinical head-injury vocabulary,
dates, quantities, negation and action status remain covered. Prompt revision
retains source-version keys and all failure/held/paused/terminal states, including
the medical version's fourth failure. Public admission accepts v4 only; there
are no released Kemhan machine records to migrate.

All five retained failures were replayed privately against verified immutable
captures, with every applicable predicate evaluated. The v3 input remains held;
under v4, its translated private institution names are also inconsistent with
the literal-form rule. A clearly labeled edited diagnostic uses the exact local
forms in both fields and passes offline QA. This is not new model output, a
recovered rejected reading or publication authority. Artifacts remain unchanged
and private; the remote queue still matches its preserved checkpoint. Focused
Indonesia/Philippines/date checks: 101 passed. Mandatory final-head CI belongs
to the repair PR; no generated output or production database changes occur.

The recognizer strips only explicit grammatical introductions such as “Menurut”
and “Meanwhile”; an institution embedded after an introductory word cannot
hide an alias. Substantive institutional modifiers remain part of the literal
comparison. Regressions cover exact local names after introductions, unsupported
prefixed aliases and a changed institutional modifier.

Known institutional stems are detected even when lowercased; detection does not
normalize their spelling or grant an alias. Regressions reject lowercase
abbreviations and expansions in both fields against the unchanged local forms.
