# Singapore screening repair and re-screening plan — 2026-09-29

This change repairs how Singapore MINDEF records are judged for relevance. It
does **not** change any stored verdict, screen any record, or enable
Singapore analysis. Every measurement here is from `pla_watch.db` at `main`
`d17646aef` (sha256 `42f4e5a9…b501c`), read-only.

## 1. The defect, in both stages

Every record goes through two stages (`processing/relevance.py`). Both were
written for the China Desk and applied to every desk.

**Stage 1, the keyword pre-filter** (`config.RELEVANCE_KEYWORDS_ZH/EN`).
- The English list is PLA vocabulary plus "defense" and "military".
- Singapore writes "defence", so an SAF release that happens not to say
  "military" fails.
- Record 4721, an SAF discipline notice, was stored as `failed keyword
  pre-filter`.

**Stage 2, the model screen** (`analysis/prompts.py`,
`build_relevance_messages` under `SYSTEM_PROMPT`).
- The prompt asks how substantively "a Chinese-language article" covers
  "Chinese military or security topics".
- The system prompt defines the domain as the PLA, PAP, CCG and Chinese
  defence industry, for a US audience.
- A MINDEF release can only fail that question.

**The stored explanations show it.** Of the 14 Singapore records screened
(stored score in brackets):

| id | published | stage | stored score | title (abridged) |
|---|---|---|---|---|
| 4421 | 09-12 | model | 0.0 | 219 Cadets Commissioned as SAF Officers |
| 4422 | 09-12 | model | 0.15 | Speech by Mrs Josephine Teo … |
| 4425 | 09-14 | model | 0.4 | Minister for Defence to Visit China for the 13th Beijing Xiangshan Forum |
| 4426 | 09-16 | model | 0.4 | Minister for Defence Speaks at 13th Beijing Xiangshan Forum and Meets … |
| 4427 | 09-18 | model | 0.15 | Singapore and Vietnam Reaffirm Defence Relations … |
| 4428 | 09-18 | model | 0.2 | Singapore and Australia Navies Mark Completion of … Exercise Singaroo |
| 4429 | 09-19 | model | 0.0 | SAF Open Mobilisation Exercise |
| 4561 | 09-23 | model | 0.1 | Minister of State for Defence Desmond Choo Visits SAF's Artillery … |
| 4609 | 09-24 | model | 0.1 | SAF Strengthened International Partnerships at Exercise Suman Warrior 2026 |
| 4631 | 09-25 | model | 0.0 | Speech by Coordinating Minister for Public Services … |
| 4679 | 09-27 | model | 0.1 | Minister for Defence Chan Chun Sing to Visit France and Germany … |
| 4680 | 09-27 | model | 0.15 | Singapore and United States Hold 16th Strategic Security Policy Dialogue |
| 4720 | 09-28 | model | 0.1 | Speech by Minister of State for Defence Desmond Choo at the 27th … |
| 4721 | 09-28 | keyword | 0.0 | Media Reply on 1SG N M Pranesh |

- **10 of the 13 model rejections** give the absence of Chinese military
  content as the reason. For example, 4421: *"concerns the Singapore Armed
  Forces, not Chinese military or security organizations"*.
- **4425 and 4426**, the two Xiangshan Forum releases, name PLA officials. They
  scored 0.4 for lacking substantive PLA *activity*. That is the China rubric's
  bar applied to a Singapore minister's visit.
- **4631** is a speech at a hospital's 30th anniversary about ageing. It would
  be rejected under any defence scope.

**What happens after a pass is also China-only.** In `Analyzer.analyze()`, a
record that passed would go on to:
- translation "from Chinese";
- a summary;
- the PLA category taxonomy (`VALID_CATEGORIES`).

So fixing stage 2 alone would send English MINDEF releases through a
Chinese-to-English translation and PLA categories.

## 2. The fix

**`processing/screening.py`** gives each desk a `ScreeningProfile`:
- **China, and any record with no desk:**
  - the shared keyword lists;
  - `build_relevance_messages` under the existing system prompt;
  - in the daily queue.
  - These are the same objects as before.
- **Singapore:**
  - **Stage 1** is skipped for Singapore. The source is the declared scope,
    since every official MINDEF release is inside it. Nearly every release
    names MINDEF or the Minister for Defence, so a keyword list would filter
    nothing.
  - **Stage 2** uses `build_singapore_relevance_messages` under
    `build_singapore_system_prompt(<scope>)`. The scope sentence is read from
    `desks/registry.json` at runtime, not restated in code.
  - **Not in the daily queue.**

**The gate** (`pipeline.py`, and `scripts/backfill_unscored.py`, which runs
the same China-only `analyze()` path).
- Records of a desk whose profile is not in the daily queue are left out of
  all three parts of the analysis queue (new, pending and unscored) and out
  of the backfill.
- On the pinned database, the backfill skips exactly the 50 Singapore records
  and keeps all 566 China ones.
- They stay `passed_relevance IS NULL`, "awaiting screening".
- One log line per run counts them.
- Merging this therefore:
  - stops further China-rule rejections of Singapore records;
  - screens none of the 50;
  - never runs translation or PLA categorisation on a MINDEF release.
- The cost is that no Singapore record is selected for analysis until the
  owner enables it. Enabling it needs a Singapore-appropriate
  post-relevance step first (§5).

**The Singapore rubric is new editorial policy and needs the owner's review.**
- The question it asks: how substantively does the release concern defence or
  security matters? Those are defined as:
  - the SAF and MINDEF's defence agencies (operations, exercises, training,
    readiness, personnel, discipline, capability development, procurement);
  - national service;
  - Singapore's defence policy;
  - Singapore's defence relations (visits, dialogues, agreements, combined
    exercises).
- Its bands match the China rubric's shape:
  - 0.9–1.0: specific facts;
  - 0.6–0.8: ceremonial or general;
  - 0.3–0.5: secondary;
  - 0.0–0.2: not defence, "for example, a minister's speech on another
    portfolio at a non-defence event".
- It says outright that China or PLA involvement is neither required nor a
  reason to score higher.
- The threshold stays `RELEVANCE_THRESHOLD` = 0.60. By design, the ceremonial
  0.6–0.8 band passes.
- Full text: `analysis/prompts.py`.

**Stored verdicts.** None change. Future Singapore records are no longer
written as `failed keyword pre-filter`; they are stored NULL (awaiting
screening).

## 3. Tests

`tests/test_desk_scoped_screening.py` has 14 tests, all offline; the model is
mocked. 12 fail on `main`. The two China invariants pass on `main` by design.

**China is unchanged** in its prompts, its system object, its keyword verdicts
and its backlog order. Slot allocation does change: on a day with more new
records than the cap, Singapore inserts no longer take new-article slots, so
China gets them. The tests check:
- the relevance messages, the system payload and `SYSTEM_PROMPT` match
  SHA-256 hashes recorded on `89e48a2fe`;
- a China call sends the *same* system object;
- keyword verdicts on stored China records are reproduced.

**Singapore uses its own scope:**
- 4721 fails the China keyword list and passes the Singapore stage 1;
- the prompt contains the registry scope and none of the China-only phrases;
- a Singapore call sends the desk system prompt.

**The gate:**
- the real `pipeline.run()` on a temporary database queues the China record;
- it holds both Singapore records, which stay NULL;
- the backfill is offered China records only.

**Re-screening tool:**
- the plan groups records by stage and prices them;
- a proposal calls relevance only (never `analyze()`), leaves the database
  byte-identical, and refuses another desk's ids.

**Fixtures** (`tests/fixtures/screening/desk_screening_records.json`).
- These are 900-character excerpts of stored records, labelled from their
  text:
  - relevant: 4466, 4472, 4425, 4426, 4721;
  - irrelevant: 4631;
  - China: 4708, 4686, 4719.
- **What the tests cannot show:** a mocked model can't prove the rubric
  selects the right releases. That is what the reviewed proposal in §4
  measures.

## 4. Re-screening plan (not run)

`scripts/rescreen_desk.py plan --desk singapore --db <snapshot>` produced the
figures below offline.

**Affected: 64 records.**
- **Never screened (50):** 4417–4420, 4423, 4424, 4430–4473.
- **Model-rejected (13):** 4421, 4422, 4425–4429, 4561, 4609, 4631, 4679,
  4680, 4720.
- **Keyword-rejected (1):** 4721.

**Cost.** One Haiku relevance call per record (`claude-haiku-4-5-20251001`,
$1 / $5 per million tokens as recorded in `scripts/spend_guard.py` on
2026-07-31; re-verify before spending).
- **Input:** 373,019 characters of prompt plus a 457-character system prompt
  per call, about **115k input tokens** at 3.5 characters per token.
- **Output:** 80 tokens per call typical, 500 at the ceiling.
- **Estimate:** **about $0.14 typical and $0.27 at the output ceiling** for
  all 64, with no cache discount assumed. There are no translation, summary
  or analysis calls.

**The list moves until this merges.**
- Every scheduled run screens its **new** Singapore inserts first, under the
  China rules.
- The 2026-09-29 run's window (09-23 → 09-29) should insert `23sep26-mq` and
  any 09-29 releases, so the rejected list will grow.
- The 50 unscreened records are not at risk yet. They sit at positions
  567–616 of the archive backlog, behind all 566 unscreened China records,
  and a daily run takes about 16 backlog records.
- Refresh the plan against the database at merge time.

**Review before any database change:**
1. **Plan.** Run `plan` against a pinned snapshot, and record the snapshot
   sha256.
2. **Propose.** Run `propose --ids … --confirm-spend` with the owner's
   authorization. It calls only the Singapore relevance stage and writes a
   JSON sidecar: stored verdict beside proposed score and reasoning, with an
   empty `review` block for each record. It cannot write the database.
3. **Review.** A human reads each proposed verdict against the record text,
   and fills in `decision` and `note`. Look first at:
   - the 0.6–0.8 band;
   - any reversal of 4631;
   - held and short records (4429 has 258 characters).
4. **Apply.** `update_relevance` stores no prompt version, so an applied row
   cannot show which rules produced it. The apply must therefore record each
   id's `model` and `prompt_version` (`sg-relevance-v1`), through the
   committed, reviewed sidecar and the DECISION_LOG entry.

   The apply itself is a separate, owner-approved change: an update-only delta
   to `passed_relevance`, `relevance_score` and `relevance_reasoning` for
   the approved ids. Check it the way PR #66 checked its insert-only delta:
   - no other column or row changes;
   - the database hash is taken before and after;
   - it is recorded in `DECISION_LOG.md`.

   No apply tool exists yet, by design.

## 5. Decisions for the owner

1. **The Singapore rubric** (§2): accept or amend it.
2. **Re-screening:** whether to authorize `propose` for the 64 (about $0.27
   at most), and who reviews the result.
3. **After a pass.** What Singapore analysis should be: no translation, a
   Singapore summary, and which categories. Until that is decided, Singapore
   stays out of the daily queue.
4. **Sequencing:** merge before or after the 2026-09-29 run. Each run before
   merge adds new China-rule rejections for Singapore.

**Status of these decisions, 2026-10-18.** No owner ruling on decisions 1–4
is in `DECISION_LOG.md`. The branch `claude/ipr-desk-completion-7e9246` (§6)
builds the analysis path that decision 3 describes, and puts Singapore in the
daily queue. **Merging that PR is the owner act that adopts the rubric
(decision 1) and the analysis shape (decision 3).** Until it merges, Singapore
stays held as written above. Decision 2 is not affected by the merge: the 14
records already rejected under the China rules stay rejected until a
`propose` run is authorized and reviewed. Decision 4 is moot, since every
Singapore record collected since 2026-09-29 is still unscreened (the hold
kept them out of the China screen).

## 6. Finish line: Singapore desk, end to end — 2026-10-18

Measured against `pla_watch.db` at `main` `7a1367102c` (sha256
`d1c322449c1dedca…`), read-only. Every replay and failure test below ran on a
copy; the tracked database hash was the same before and after each one. No
model was called and nothing was paid for.

Three kinds of evidence are kept apart:
- **historical replay**: a past window re-collected through the real
  pipeline on a copy;
- **manual integrated execution**: one live collection plus analysis on a
  copy, with the two model replies scripted;
- **observed scheduled operation**: the GitHub Actions run doing the work
  in production.

Status words:
- **configured**: the code or setting exists;
- **demonstrated**: shown working here on a copy or in tests;
- **operating**: observed in scheduled production runs.

### 6.1 Checklist

**1. Source family**
- *Included:* `sg_mindef_releases`, MINDEF news releases (public;
  `robots.txt` read every run, and a disallow stops the run).
- *Excluded:*
  - `15aug26-speech` and `16sep26-speech`, governed holds removed before
    the window is applied. Both stored captures have CJK bytes destroyed by
    a whitespace collapse; `16sep26-speech` also cannot be recaptured,
    because MINDEF revised a sentence after capture
    (`shadow/singapore_mindef/CORRECTIONS.md`; DECISION_LOG 2026-09-21).
  - Speeches outside the release sitemap, and every other MINDEF or SAF
    channel. These were never declared in the manifest.
- *Status:* **operating** since promotion (2026-09-21).
- *Missing:* nothing.
- *Check:* `desks/singapore/manifest.json` has one enabled source, and
  `HELD_RELEASE_SLUGS` lists the two holds.

**2. Capture and evidence**
- *Working:*
  - sitemap discovery over a 7-day window (`production_lookback_days=6`);
  - full-text capture, with 2 retries and a 1.5 s interval;
  - atomic batch admission (`ATOMIC_BATCH_SLUGS`);
  - per-run `source_run_results`.
- *Status:* **operating**.
- *Missing:* nothing.
- *Check:* §6.2 reconciliation. Every official release in the window has
  one row, and no URL is duplicated.

**3. Processing**
- *Working:*
  - the desk relevance screen, `sg-relevance-v1` (Haiku);
  - on a pass, one desk analysis call, `sg-analysis-v1` (Sonnet). It writes
    an English summary that states the concrete development first, and it
    keeps MINDEF's own statements apart from commitments, implementation and
    inference.
- *Not done for Singapore:*
  - no translation: `title_english` and `text_english` stay NULL;
  - no PLA categories;
  - no `executive_readout`.
- *Labelling:* on the record page the flag appears under the "Machine
  assessment" label as "Model-flagged for closer review. This is a software
  triage cue, not an editorial judgment." (or "Not flagged…"). The model's
  flag reason is stored in `significance_reasoning` and not displayed. A
  summary without a usable flag, or a flag without a reason, writes nothing
  and is retried as pending analysis.
- *Status:*
  - **configured** and **demonstrated**: tests, plus the §6.3 integrated
    run;
  - not yet **operating**: held from the daily queue until this PR merges.
- *Missing:*
  - adoption of the rubric and the analysis shape (§5, decisions 1 and 3);
  - `sg-analysis-v1` has never run against the live model. Its first real
    outputs will appear on record pages, under machine labels, without a
    human having seen a sample. A one-record paid probe on a copy (PR body)
    is available if the owner wants a sample first.
- *Check:*
  - the first scheduled run after merge logs `Analysis queue: … backlog` with
    Singapore records;
  - `prompt_version = 'sg-relevance-v1+sg-analysis-v1'` on the records it
    analysed.

**4. Admission**
- *Working:*
  - URL uniqueness;
  - all-or-nothing batch insert;
  - `is_retired` policy;
  - blank-body withholding: 4936 has an empty stored body, so it is kept
    but never sent to the model.
- *Status:* **operating** for collection; the crash and recovery case is
  **demonstrated** (§6.4, F4).
- *Missing:* nothing.
- *Check:* `SELECT url FROM articles GROUP BY url HAVING count(*)>1` returns
  nothing.

**5. Reader experience**
- *Reader route:* the desk page (`singapore.html`) links to the Singapore
  week pages and to the archive filtered to the desk
  (`archive.html?desk=singapore`). It does not list records itself. Week
  pages and the filtered archive (driven by `corpus-index.json`) link to each
  record page. Search (`archive-research-index.json`) and citation are on the
  record page.
- *Labels on a record page:*
  - a machine summary says "Machine-generated from the original text. Not
    reviewed by a human";
  - the Translation row now reads "Not needed: the source publishes in
    English" instead of implying a missing translation.
- *Status:* **operating** for unanalysed records. The summary display is
  **demonstrated** on an isolated render (§6.3).
- *Missing:* summaries on public pages wait on item 3.
- *Check:* `output/record/<id>.html` for an analysed Singapore record shows
  the summary under the machine label and the "Machine assessment" flag line,
  with no "significant" wording and no analyst readout (§6.3 shows both flag
  states on an isolated render).

**6. Ongoing operation**
- *Schedule:* `.github/workflows/daily_update.yml`, cron at 12:23, 12:53,
  13:23, 13:53 and 14:23 UTC (the first success ends the day), all sources.
- *Failure reporting:*
  - `scrape_runs.status = 'degraded'`, plus a `source_run_results` row with
    `is_failure` and `error_detail`;
  - `scripts/source_health_report.py --db pla_watch.db`;
  - `scripts/check_source_liveness.py --db pla_watch.db` (7-day threshold).
- *Status:* collection **operating**; failure and recovery
  **demonstrated** (§6.4).
- *Missing:* observed scheduled analysis (after merge).
- *Check:* the first post-merge scheduled run completes without a
  Singapore analysis failure in its log.

### 6.2 Bounded MINDEF reconciliation, 2026-10-04 to 2026-10-18

Live sitemap, read-only, against the tracked database and `output/`. MINDEF
listed 9 releases in the window. All 9 are captured and unscreened. Each has
a record page, a row in `corpus-index.json` `records` (so the filtered
archive lists it), an entry in the search index, and a link from its week
page. None is linked from `singapore.html` directly, by design (§6.1 item 5).

| Slug | Date | Record | Chars |
|---|---|---|---|
| 4oct26-nr | 10-04 | 4891 | 1,840 |
| 05oct26-mq | 10-05 | 4911 | 378 |
| 06oct26-mq | 10-06 | 4986 | 514 |
| 06oct26-pq | 10-06 | 4985 | 1,587 |
| 8oct26-nr | 10-08 | 4984 | 853 |
| 8oct26-nr2 | 10-08 | 4983 | 3,094 |
| 9oct26-nr | 10-09 | 5026 | 2,206 |
| 10oct26-fs | 10-10 | 5071 | 7,556 |
| 10oct26-nr | 10-10 | 5070 | 4,706 |

Nothing was published from 10-11 to 10-18, which is official silence, not a
collection gap (the caveat: the sitemap can lag up to about two days). The
liveness check therefore reports Singapore OVERDUE at 8 days against a 7-day
threshold. That is accurate reporting of a quiet source, and it will clear on
MINDEF's next release.

### 6.3 Manual integrated execution (isolated copy)

- **Run 173:** live MINDEF collection for 2026-10-18, then analysis with the
  cap set to 2.
  - Collection: `ok_no_publications`.
  - Queue: 2 of 71 backlog records.
  - Model calls: three, all scripted (two relevance, one analysis).
  - Record 4891 passed: summary stored (a labelled REPLAY FIXTURE), English
    title and text NULL, `is_significant` 0, no categories, prompt
    `sg-relevance-v1+sg-analysis-v1`.
  - Record 4911 was rejected, with no analysis call and no summary.
- **Run 174:** historical replay of 2026-10-10, collection only. 9
  discovered, 9 duplicates, 0 new.
- **Isolated render:**
  - `record/4891.html` shows the summary under the machine label, the
    Translation row "Not needed: the source publishes in English" (all 86
    Singapore rows carry `language_tag = 'en'`), and "Machine assessment —
    Not flagged for closer review";
  - the fixture text appears on no other page;
  - neither held slug and no shadow path appears anywhere in the render.
- **Flagged path (second copy):** 4891 was set to `is_significant = 1` with a
  fixture reason, then rendered. The record page shows "Machine assessment —
  Model-flagged for closer review. This is a software triage cue, not an
  editorial judgment." The reason is not displayed. "significan…" appears
  nowhere on the record page, its week page (which shows "Analyzed"),
  `singapore.html` or `corpus-index.json`. The one hit in
  `archive-research-index.json` is a pre-existing PLA Watch edition summary,
  present identically in `output/`.
- **Editorial intake (behaviour, not files).** No Brief, Sunday or draft
  file changes. The Sunday and weekly auto-writers already take Singapore
  evidence in desk-balanced slots; within a desk they rank analysed and
  model-flagged records first (`scripts/sunday_briefs_auto_writer.py`,
  `rank`). The source trail then shows Singapore records as `analyzed` with
  their model flag (`core/brief_contract.py`, `trail_entry`). After merge,
  that existing logic will treat analysed Singapore records exactly as it
  treats analysed China records. Which Singapore records are offered to the
  editor can therefore change. Human approval (`approve()`) and Dylan's
  editorial role do not change.

### 6.4 Controlled failures (isolated copies, real `pipeline.run`)

| Case | Injected fault | Articles | Recorded result |
|---|---|---|---|
| F1 | `robots.txt` HTTP 503 | 912→912 | `listing_failure` "robots.txt returned HTTP 503"; run `degraded`; health report `is_failure=1`, last success kept |
| F2 | sitemap `ConnectionError` | 912→912 | `listing_failure` "sitemap unreachable: ConnectionError" |
| F3 | sitemap 200 with HTML body | 912→912 | `listing_failure` "sitemap parsed to zero release URLs" |
| F4a | DB error on the 2nd insert of a 2-record batch | 910→910 | `storage_failure` "atomic batch insert failed; no new records committed this run" |
| F4b | next run, no fault | 910→912 | `ok`, 2 new |
| F4c | same window again | 912→912 | `ok_all_duplicates`, 9/9 |

- After F4 the database held 0 duplicate URLs.
- The two re-admitted releases are unscreened, so they enter the queue.

**Interrupted publication** is governed by code and was not injected:
- a render exception exits 1;
- validation, the output commit and the Pages deploy are then skipped;
- "Persist scraped articles" commits `pla_watch.db` only;
- a whole-queue analysis failure exits 2 with the same persist path.

**Recovery command.** The next scheduled run re-collects the 7-day window.
For a longer outage, or to replay one day by hand:

```bash
.venv/bin/python pipeline.py --source sg_mindef_releases --date YYYY-MM-DD
```

Records stored without analysis (`--no-analysis`, or an API outage) drain as
backlog on later runs.

### 6.5 Cost once merged

Priced from `analysis/pricing.py` at 3.5 characters per token:
- Haiku relevance, $1 / $5 per million tokens;
- Sonnet analysis, $3 / $15 per million tokens.

There are 72 unscreened Singapore records. 4936 is withheld for its blank
body, so 71 are sent. Input is measured from stored text; output is
estimated, with the `max_tokens` ceiling as the bound:

| Call | Input | Output (est. / ceiling) | Cost (est. / ceiling) |
|---|---|---|---|
| relevance, 71 × Haiku | ~128K → $0.13 | ~60 / 500 per call → $0.02 / $0.18 | $0.15 / $0.31 |
| analysis, ≤71 × Sonnet | ~154K → $0.46 | ~300 / 1,000 per call → $0.32 / $1.07 | $0.78 / $1.53 |

Order of magnitude, about **$1** for the backlog if every record passes
(about $1.85 at the output ceiling). It is an estimate, not a quote.

The backlog drains at no fewer than 16 records a run (the 30% backlog
reserve of the 55 cap), and up to 55 on a quiet China day, so it clears in
two to five runs. After that, a MINDEF release costs about 1–3 cents to
screen and summarize. The 14 China-rule rejections (4421, 4422, 4425–4429,
4561, 4609, 4631, 4679, 4680, 4720, 4721) are not re-screened by the merge;
that is decision 2.
