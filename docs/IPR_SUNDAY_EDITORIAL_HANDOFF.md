# IPR Briefs — Saturday provisional draft and Sunday readiness

## Staged implementation, 2 November 2026 — no production activation

The callable cycle is `scripts/saturday_sunday_briefs.py`. It reuses the existing
writer, discovery/eligibility, worksheet, Word rendering, editor return and Brief
contracts. It introduces no database, publication category, new workflow file or
paid feedback pass. The current public main is the base for this review candidate;
this section describes code qualification, not a running service.

The owner target in **America/New_York** is Saturday about 12:30 p.m. after actual
successful Saturday collection, editor delivery by Saturday 9 p.m., an agreed
Sunday-noon editor return and Sunday-evening owner review after successful Sunday
collection. These are targets, not source completeness or cron guarantees. The
optional analyst is not required by this track.

### What works offline or through explicitly authorized local calls

- `prepare` rejects early/off-day/stale-marker attempts, reads the admitted
  Sunday–Saturday corpus through a scratch DB and requires eligible preserved
  originals from two production desks. This initial cycle deliberately keeps the
  stricter two-production-desk floor; it does not borrow Sunday private-research
  exceptions. Existing full-discovery semantics and one bounded model request
  remain. No source-specific right or new source admission is created.
- The default **does not call a model or send mail**. It writes a mode-0600
  scaffold in an outside-Git mode-0700 directory. Only `--execute-model` authorizes
  the existing paid draft invocation. A model-attempt reservation prevents paid
  retries after an ambiguous failure. Abstention preserves its private selection
  receipt and writes no manuscript. Accepted output is reused by SHA on replay.
- Successful composition preserves the existing `IPR-<Saturday>` identity and
  writes TXT, DOCX, manuscript JSON and source/policy inventory hashes. The prompt
  and worksheet explicitly say Saturday is incomplete and Sunday recheck is
  required. The scaffold carries a provisional `saturday_sunday_cycle` marker;
  retain it when preparing the canonical Brief candidate.
- `deliver()` is a reusable interface, **no-send by default**. It checks current
  evidence/permissions against the draft, the current Saturday marker, exact TXT,
  distinct configured editor/owner, explicit exact-SHA owner confirmation and
  disabled legacy services before a send. It reuses the established SMTP/DOCX
  mechanics. A private per-week/editor/phase reservation prevents duplicate
  attempts; uncertain SMTP outcomes hold for manual Sent review, never retry
  automatically. Fake recipients and patched send mechanics are used in tests.
- Sunday `recheck` requires the real same-Sunday marker, hashes every weekly
  production row and metadata discovery row plus associated machine records, and
  compares current source/rights configuration. Added backdated Saturday sources,
  changed body/hold/representation or machine explanation and policy/desk drift
  hold. This is a deterministic version comparison, **not factual verification**.
- Owner source-to-claim review must be explicitly referenced. A changed inventory
  requires a separate `resolved` decision for every added/removed/changed source
  and policy/desk change, each with reason, reviewer and reference, bound to the
  exact current inventory and final manuscript SHA. There is no general bypass
  flag. Essential unresolved facts remain held. A later prose/credit/citation
  change invalidates the receipt and requires another source review.
- Shared `core.brief_contract` blocks approved tagged provisional/held records
  and validates exact Sunday review binding for every publication caller.
  `author_brief.py ready/approve` additionally re-reads current inventory to catch
  later drift. Untagged historical/manual publications retain their contracts.
  This receipt never supplies Ben's independent publication or presentation
  approval and never assigns authorship or an issue number.

### Owner-only rehearsal and controlled editorial return

All paths below are private, outside any Git checkout. A real current Saturday
marker is required even without a model. Do not run `--execute-model` without
separate spending authority; a no-email model preview still costs money.

```sh
python -m scripts.saturday_sunday_briefs prepare \
  --week-ending YYYY-MM-DD --private-dir /private/ipr-cycle
```

After separately authorized generation/delivery, retain the original TXT and Word
files privately. Use existing `import_sunday_editor_docx`,
`validate_editorial_return` and `analyze_editor_return` against that exact original.
A structurally valid return remains untrusted editorial input: changed claims
need source review and a final candidate prepared through the existing authoring
path, retaining its provisional cycle marker. This track does not silently
import an editor's Word return or infer factual approval from style edits.

```sh
python -m scripts.saturday_sunday_briefs recheck \
  --state /private/ipr-cycle/IPR-YYYY-MM-DD.json \
  --manuscript /private/ipr-cycle/final-candidate.json \
  --out /private/ipr-cycle/sunday-reviewed-candidate.json \
  --reviewed-by 'Actual reviewer' --review-reference 'Actual source-review reference'
```

The output is still a private, unapproved candidate. For a changed inventory,
`--decisions` accepts the explicit exact-version review object described above;
missing, stale or unresolved decisions hold. Source and presentation checks,
actual author credit adjudication and Ben's exact final publication authority
remain mandatory. Do not treat a passed dry run as publication authorization.

### Precise remaining integration and activation boundary

**Unattended scheduling is not implemented or activated by this candidate.**
The existing Sunday workflow has only a replacement-exclusion guard:
`IPR_SATURDAY_SUNDAY_CYCLE_ENABLED=true` would disable its legacy generator/send.
Do not set it yet: there is no replacement unattended runner in this phase.
The Friday lane stays retired. No repository variable/secret was changed.

Before later activation, the integration owner must connect the verified callable
cycle to the existing workflow, reuse/reconcile open PR #807's authenticated
Daily-completion guard, verify actual pipeline/deploy/marker steps (green skipped
Daily runs are insufficient), and arrange durable **private** storage/locking for
accepted drafts, reservations and receipts across runner restarts. Runner temp
storage or public Actions artifacts cannot meet that requirement. Preserve the
workflow-file freeze: modify the existing lane, do not add a new one. The relevant
open #945–#947 editorial instructions/identities need explicit integration without
copying unrelated branches; #952 Record admission remains independent.

Confirm editor availability and the Sunday-noon return target, verify separately
permitted destinations/source distribution, decide the existing bounded model
budget, run an authorized end-to-end private no-send rehearsal, and obtain Ben's
explicit activation authority before any schedule, email or spend. Track B analyst
packet/feedback work connects only after both heads are verified. The remaining
integration is a fresh bounded session; these local interfaces do not claim an
automated inbox, production private persistence, real delivery or Sunday release.

## Historical Sunday-draft operating instructions

The dated sections below preserve the earlier Sunday/Monday/Wednesday service.
They describe the legacy lane until the replacement is explicitly integrated and
activated; they do not override the target cycle and staging boundary above.

## Narrative reform — article-first manuscript (25 October 2026)

The writer now asks for one cohesive article (lead on the concrete development, optional
story-specific subheads, no forced sections) plus a private `audit` block, under the
standard in `docs/IPR_BRIEFS_WRITING_STANDARD.md`. Dylan's TXT/Word/email show the title,
dek, article and (TXT only) the editorial questions; the audit notes, source accounting,
limitations ledger, source-use receipt and a **NARRATIVE QUALITY REPORT** stay in the
private appendix. The owner preview adds a counts-only quality line. Mechanical failures
(placeholder, truncation, doubled words, duplicated or forced material) mark a hold that
is enforced in `send_packet` (the October 10 pilot gate does not cover later weeks): a
held draft is **never mailed to Dylan**. Instead the identical TXT and Word bytes go to the
owner-only `IPR_PREVIEW_TO` address as a "HELD BY QUALITY GATE" notice stating the SHA-256,
and the job then fails visibly. If `IPR_PREVIEW_TO` is missing or equals the editor
address, nothing is sent. To release, Ben saves the TXT from that notice, reviews or
corrects it, and runs `scripts.sunday_send_reviewed_packet` with the file, the week and
`IPR_SUNDAY_OWNER_REVIEWED_WEEK` / `IPR_SUNDAY_OWNER_REVIEWED_SHA256` set to its digest
(dry run first; `--send --confirm-owner-reviewed` to mail Dylan). That path sends exactly
those bytes, makes no model call and accepts article-first and legacy worksheets.
Limitations: **do not rerun the scheduled delivery for a held week**; a rerun
regenerates a different draft (a new model call) and, if clean, could email Dylan
separately. The manual sender cannot detect an earlier Dylan send, so check Gmail Sent
before releasing. Owner previews now attach both TXT and Word; they go only to the
owner. Style findings are advisory and never trigger a second model call. Nothing in this
reform sends, numbers, publishes or spends; the first live use is a separate
owner-authorized step.

## Scheduled-delivery correction — October 11, 2026

After this change, the Sunday 19:17 UTC schedule **attempts one guarded
provisional Dylan delivery by default**. The variable
IPR_SUNDAY_EDITOR_DELIVERY_ENABLED=true remains required for an explicit
manual workflow_dispatch editor send, not scheduled runs.

Safeguards remain unchanged: the October 10 first-pilot edition still
requires exact owner-reviewed week and attachment SHA-256; never regenerate
that issue for automatic delivery after the manual handoff. Later editions
still require same-Sunday successful collection, eligible source evidence,
non-conflicting delivery modes and valid SMTP credentials. No Brief is
automatically approved, numbered or published.

Before next Sunday, the owner should:
- Confirm the Sunday workflow is ENABLED in GitHub Actions; missing schedule
  executions cannot be diagnosed solely from the repository YAML.
- Keep legacy Friday IPR_EDITOR_DELIVERY_ENABLED=false. The old
  IPR_SUNDAY_OWNER_PREVIEW_ENABLED variable is ignored by scheduled runs;
  Sunday sends one manuscript to Dylan. Use manual workflow_dispatch for
  owner-only previews, never together with editor delivery.
- Verify ANTHROPIC_API_KEY, IPR_EDITOR_TO, IPR_SMTP_USER and
  IPR_SMTP_APP_PASSWORD are configured (never log or share secret values).
- Inspect the real Sunday Actions execution and one SMTP receipt. GitHub
  schedules can be delayed or silently skipped; changing the default does
  not guarantee a schedule was triggered or that SMTP credentials work.
- Do not add a second sending cron without a durable, week-specific
  de-duplication receipt.

The older staged-migration instructions below remain background only where
they say the scheduled Sunday job needs a separately enabled delivery flag.


## Operating schedule

The new, **separately gated** Sunday workflow is designed for this cycle:

- **Sunday at 19:17 UTC:** approximately 3:17 p.m. EDT or 2:17 p.m.
  EST. This is a best-effort GitHub Actions schedule, not a guaranteed
  clock-time commitment; Actions can start late.
- **Sunday before any Claude call:** require the main branch's existing
  .github/state/last_daily_run_date.txt to equal **today's Sunday date in
  New York**. That state marker is written only after the daily production
  pipeline/validation has succeeded. A green daily workflow that skipped
  collection is NOT sufficient by itself.
- **Sunday afternoon after that gate:** read the stored official-source
  corpus dated Sunday through **Saturday inclusive**, select a maximum of
  10 validated full-text bodies across at least two live desks, compose
  source-cited full prose with Claude Sonnet 4.6, validate the actual
  record IDs and per-section prose, and email Dylan one editable text file.
- **Monday 8 p.m. Eastern:** Dylan replies to the original message with
  his edited text file attached. He may reply early, or tell Ben promptly
  if he cannot meet the deadline. This is a turnaround target, not an
  automatically enforced rejection of late editorial work.
- **Tuesday:** Ben asks ChatGPT to find Dylan's reply in the connected
  Gmail account, inspect the attachment and compare against the original
  (see scripts/validate_editorial_return.py). Ben independently checks
  that cited source bodies support claims and that the week is sufficiently
  covered.
- **Wednesday target:** Ben may authorize final prose, the native
  unnumbered briefs/<slug>.json sidecar, approval, numbering and release
  through the existing governed workflow. Nothing publishes automatically.

## Important: full week != exhaustive source capture

Saturday has elapsed and Saturday-dated archived records may be included.
The daily state marker proves a **successful Sunday production pipeline**,
not that every government website has published and been captured by Sunday.
Late-collected/backdated documents, source outages and unverified
translations require additional human editorial judgment. The system does
not assert a complete global news survey or infer silence from a missing
record.

## Safe migration from the working Friday service

The **existing Friday workflow remains unmodified**. Do not activate both
delivery services at once.

1. Merge this PR only after focused tests and complete PR CI pass.
2. On **Actions**, manually run **Sunday IPR Briefs Full-Week Draft to Dylan**
   on main with **Email Dylan unchecked** and an explicit past Saturday
   (for example 2026-10-03). The Sunday workflow will use the Anthropic
   API for this preview, but will not email Dylan. No public article
   artifact is uploaded.
3. If the preview passes, set existing repository variable
   IPR_EDITOR_DELIVERY_ENABLED to **false**, disabling the Friday
   automatic sends.
4. Set the *new* repository variable
   IPR_SUNDAY_EDITOR_DELIVERY_ENABLED to **true**, enabling the Sunday
   workflow. If the old Friday variable is still true, the new Sunday
   code **refuses email**, even when triggered manually.
5. On the next Sunday, check the daily update and Sunday handoff jobs.
   Do not manually send another copy of the same week unless you
   explicitly want a duplicate and have coordinated with Dylan.

For manual previews, leave the historical date blank to select the latest
reached Saturday. On Sunday, that particular Saturday cannot be previewed
until Sunday's daily success marker exists. Older week previews are allowed
without Sunday's marker, but **manual email** outside the current Sunday
requires both the separate historical-send checkbox and the Sunday delivery
variable. Full-week generation for an unfinished Saturday is refused.

If Sunday collection is incomplete or the GitHub scheduled job starts on
Monday, the automatic job **fails closed**: no Claude cost, no email. The
operator can rerun manually after examining the now-current corpus and
authorizing a historical send. A small missed dispatch is preferable to
sending Dylan a misleading or incomplete edition.

## Gmail reply intake

Dylan's reply goes to the SMTP sending account because the email uses its
address as Reply-To. The ChatGPT Gmail connector can find and read the
reply and attachment **only if that particular mailbox is connected**.
Currently the owner intends to connect benyang0313@gmail.com; do not
assume access or claim an automated inbox listener is active.

Neither this PR nor the Gmail connector automatically polls Dylan's
inbox, imports the reply into GitHub, prepares a final Brief, assigns an
issue number, approves editorial text or publishes the site. Ben must
explicitly request and authorize subsequent actions. The original sent
text file should remain accessible privately, since the return validator
requires both the original and the edited versions.

## Permissions and secrets

This is a **new, manual-disabled-by-default** workflow. The only new
configuration needed for scheduled sending is the repository variable
IPR_SUNDAY_EDITOR_DELIVERY_ENABLED=true. It reuses the existing
ANTHROPIC_API_KEY, IPR_EDITOR_TO, IPR_SMTP_USER and
IPR_SMTP_APP_PASSWORD secrets. No plain passwords, inbox credentials,
unpublished article artifacts, source DB changes, Git writes, or
publication rights are added.

The existing GitHub Actions token is contents: read. Automated writing
uses a private runner temporary directory; invalid model output aborts
without SMTP delivery. No automatic retries are made after network errors;
invalid completed drafts may undergo one bounded correction attempt.

## Unified Japan/Vietnam drafting research (this successor PR)

The Sunday editor's single synthesized manuscript may use a strict, week-specific research packet of **short, attributed editorial synopses** from Japan/Vietnam official sources (not copied source bodies). The private model sees the source URLs, dates, original-language headlines, short summaries, source-state hashes where an actual shadow extraction exists, and prominent human-review cautions. It can choose a single theme and cite sources by **typed external IDs**. It is told to omit any country material that does not genuinely fit that theme.

The returned text includes a unified immutable appendix that distinguishes real production record IDs from external, publisher-hosted source IDs. Dylan edits ONE draft and reviews any external citations; no separate national supplement is expected. The external material does not qualify the desks as live, does not become a production DB record, and is **not preapproved for publication**. Before a final Brief, human editorial checking and the independent publication contract still apply.

The Sunday workflow uses `--full-week --include-research` and **cannot send** before the owner enables the new Sunday delivery variable. Do not activate until the current-week full CI and no-send Sunday preview pass.

### Synchronization with the Vietnam desk-page publisher-link lane

This Sunday editorial draft lane is separate from the individually reviewed
publisher-link feature merged in PR #195. The branch's explicit mainline
synchronization preserves both: the public Vietnam desk may display vetted
publisher bibliography links, while the private Sunday writer uses separately
typed, clearly unapproved candidate evidence. Neither feature promotes the
Vietnam Desk to live production coverage or grants a source's reuse rights.

## Private owner preview before emailing Dylan

A no-send manual rehearsal writes its draft only into GitHub Actions temporary
storage. The workflow **does not** publicly upload an unpublished draft, so
a no-send execution alone cannot supply a human-readable file to the owner.

For an actual private manuscript quality review, configure a GitHub Actions
repository **secret** called `IPR_PREVIEW_TO` with the owner's email address,
distinct from `IPR_EDITOR_TO` (Dylan). Keep SMTP secrets on the existing
read-only source workflow. On the Sunday after a real successful daily
production update, select **Run workflow** on `main` and enter:

- `send_email=false` (must remain false)
- `preview_to_owner=true`
- `reporting_saturday=2026-10-10` for the first reporting week, or blank
  to choose the most recent completed Saturday
- `allow_historical_send=false`

This branch requires the regular full-week evidence gates and generates a
real, private, automatically drafted `.txt`. It **sends only to
`IPR_PREVIEW_TO`**, not Dylan. It explicitly refuses an owner-preview
address identical to Dylan's editor address, a missing preview secret,
simultaneous send-to-editor and owner preview, or a preview with no full-week
model draft. No manuscript content is placed in Actions artifacts or logs.

A normal `send_email=false`, `preview_to_owner=false` rehearsal remains
a true no-email run and yields no downloadable plaintext artifact. The
owner-only preview is a *separately authorized email*, not a proof of factual
source accuracy or official source-use approval.

After independently reviewing the actual manuscript and source citations,
switch off the legacy Friday delivery option (the Friday cron is separately
retired by PR #238). Only with explicit owner authorization may
`IPR_SUNDAY_EDITOR_DELIVERY_ENABLED=true` be set for Dylan's Sunday send.
