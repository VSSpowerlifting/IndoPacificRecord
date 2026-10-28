# Kemhan Berita shared Daily — authorized release, 27 October 2026

The owner approved the narrow standing source-use, spending and controlled
release decision on 27 October 2026; see the matching `DECISION_LOG.md` entry.
The three Kemhan policy switches are enabled in this release candidate.
Final-head CI, merges, first live model quality and deployed publication remain
release checks; this document does not claim their completion.

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

The per-sentence QA checks attribution, exact numbers/date notation, names,
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
