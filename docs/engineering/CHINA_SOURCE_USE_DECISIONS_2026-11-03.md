# China source-use decisions — owner decision record (draft, 3 November 2026)

**Status: OWNER DECISION PENDING for all five families. No approval, grant or
restriction is recorded in this file.** It is the single decision record the
[3 November 2026 China Desk certification audit](https://github.com/VSSpowerlifting/IndoPacificRecord/issues/673#issuecomment-6622171689)
asked for. The audit found that none of `mod_china`, `pla_daily`,
`xinhua_mil`, `china_mil_online` and `global_times_mil` has a recorded
source-use decision for retention, model input or any public component.
Benjamin Yang decides; this memo only puts the evidence, options and exact
questions in front of him. Pointer entry:
[`DECISION_LOG.md`](../../DECISION_LOG.md) (2026-11-03, pending).

What this memo is not:

- **Not a legal conclusion.** Publisher notices below are *evidence of what each
  publisher says*, quoted minimally and dated. Nothing here says that IPR's
  current behaviour is or is not permitted, and no option is "required".
- **Not an implementation.** No gating, manifest field, collector, workflow,
  database or `output/` change accompanies it. Per
  [`docs/desks/README.md`](../desks/README.md) §1, `desks/china/manifest.json`
  may reference the actual decision only after the owner makes it; engineering
  follows that, not this draft.
- **Not publisher contact.** No publisher was contacted.

## 1. The decision in one table

For each family the owner is asked for the same ten fields (Section 4 defines
them). `Rec.` is this memo's *advice*, marked so the owner can overrule it; it
pre-fills nothing.

| Family | Records held | Publisher-stated use text found (3 Nov 2026) | Rec. (advice only) | Section |
|---|---:|---|---|---|
| `mod_china` | 201 | Reprint/excerpt/mirror needs written authorization; works marked as from non-MOD outlets are pointed to the supplying unit | B | [4.1](#mod_china) |
| `pla_daily` | 826 | "未经协议授权，禁止下载使用" on the 81.cn footer; no terms page found | B | [4.2](#pla_daily) |
| `xinhua_mil` | 223 | Ownership footer only; no use-restriction wording | C | [4.3](#xinhua_mil) |
| `china_mil_online` | 203 | Generic copyright line; `robots: noindex` meta; no terms link | C | [4.4](#china_mil_online) |
| `global_times_mil` | 60 | Full Terms of Service: personal non-commercial licence; no derivative use, data mining or automated access; linking needs permission | B, plus decide retention and model input first | [4.5](#global_times_mil) |

Option letters: **A** keep current behaviour, **B** retain and show link-only,
**C** retain and show a bounded excerpt. Defined in Section 3. Retention and
model input are separate fields and are not implied by the letter.

## 2. What is true today (verified 3 November 2026)

Counts are from the tracked `pla_watch.db` opened read-only. The live-site
snapshot of 3 November 2026 listed 1,623 records. Data were not modified.

| Family | Rows | Stored original text | Machine body translation stored (`text_english`) | Machine summary stored | First / last collected |
|---|---:|---:|---:|---:|---|
| `pla_daily` | 826 | 821 | 547 | 547 | 2026-05-07 / 2026-11-03 |
| `xinhua_mil` | 223 | 223 | 23 | 23 | 2026-09-15 / 2026-11-03 |
| `china_mil_online` | 203 | 203 | 169 (109 identical to the original) | 169 | 2026-05-12 / 2026-11-03 |
| `mod_china` | 201 | 197 | 183 | 183 | 2026-05-20 / 2026-11-03 |
| `global_times_mil` | 60 | 60 | 60 (18 identical to the original) | 60 | 2026-05-13 / 2026-11-03 |
| **Total** | **1,513** | 1,504 | 982 | 982 | |

English-original sources (`china_mil_online`, `global_times_mil`) get no real
translation; their `text_english` column is mostly a copy of the original.

**Where each thing currently lives**

1. **Retention.** Full original text and the machine body translation are in the
   tracked `pla_watch.db`. The GitHub repository is **public**, so that text is
   in a public file and in git history. A separate custody-backup workflow in the
   private evidence companion also holds the China corpus; that companion's
   README says "Storage does not establish source-use rights". No China rights
   decision exists there either.
2. **Model input.** Three model stages touch China text. (a) *Relevance
   screening*: after a free keyword pre-filter, the pipeline sends each
   surviving article's title and body to an external model for a relevance score
   (`pipeline.py`, `processing/relevance.py`, `analysis/prompts.py`
   `build_relevance_messages`; whether the body is truncated was not checked).
   (b) *Analysis*: records that pass get a machine summary and, for Chinese
   originals, a body translation. (c) *Headline translation*, authorized
   18 Oct 2026 for spend and engineering only. The table below counts stage (a)
   as rows whose stored relevance note is not the keyword pre-filter note, so it
   is an approximation from stored fields, not an audit of prompts or logs; stage
   (b) is the stored-summary count above. No model-input permission is recorded
   for any China family, so the real exposure is larger than the summary counts
   in Section 4 suggest.

   | Family | Rows | Relevance-screened by a model (approx.) | Analysed (summary stored) |
   |---|---:|---:|---:|
   | `pla_daily` | 826 | 762 | 547 |
   | `mod_china` | 201 | 199 | 183 |
   | `china_mil_online` | 203 | 196 | 169 |
   | `xinhua_mil` | 223 | 184 | 23 |
   | `global_times_mil` | 60 | 60 | 60 |

3. **Record page.** `output/record/{id}.html` exists for **all 1,513** China rows.
   The template's default branch renders the machine summary (where one exists)
   and the whole stored original under the heading "Stored source text"
   ([`record.html:155`](../../site/preview/templates/record.html)). It was
   live-confirmed on indopacificrecord.org for record 5956. The stored machine
   *body* translation of Chinese originals appears nowhere under `output/`.
4. **"Copy source text" control.** It copies a *citation string* about the
   publisher's item (`cite.source_text`), not the article body
   ([`record.html:283`](../../site/preview/templates/record.html)). "Copy as held"
   is a second citation. Confirmed in the rendered `output/record/5956.html`,
   where the copied paragraph reads "Source text. Ministry of National Defense.
   … MOD China (国防部), 2026-11-02. http://www.mod.gov.cn/…" (title, source, date, URL). The
   `gallery.html` button is a design specimen. This control is therefore not the component at issue
   for text reuse; the "Stored source text" body is.
5. **Archive and search.** `output/archive-research-index.json` lists all 1,513
   China records with titles and original titles and an empty `text` field.
   `output/data/articles.json` (633 entries) exposes titles and machine
   summaries, no body.
6. **Existing limited-text precedents.** The template already has link-only or
   withheld-text branches for `sg_mindef_releases` ("Source-use limits",
   `record.html:139`), Vietnam `original_withheld` (`record.html:125`), and a
   Korea KOGL branch. China has no such branch today.

**Existing decisions that are *not* China source-use decisions**

- 18 Oct 2026 owner authorization for China headline translation
  ([`CHINA_TITLE_TRANSLATION_2026-10-17.md`](CHINA_TITLE_TRANSLATION_2026-10-17.md)):
  headline spend and engineering only; it states it is not source policy.
- 25 Oct 2026 Maritime-dossier projection grant for five records (3924, 4102,
  4164, 4466, 4472) in [`DECISION_LOG.md`](../../DECISION_LOG.md): narrow, not a
  general China text grant. Any decision below should say whether it leaves that
  grant untouched.
- [`CONTENT_AND_DATA_RIGHTS.md`](../../CONTENT_AND_DATA_RIGHTS.md) §3 and §5:
  official documents stay under the originating institution's terms, and
  metadata is not the document.

**Correction to the audit.** The audit recorded "Xinhua: none seen". The live
`news.cn` page *does* carry a footer copyright and ownership statement (4.3). It
carries no use-restriction wording. The audit's other negatives were confirmed.

## 3. Options, defined

Option letters describe the **public record component** only. The owner sets
retention and model input independently (Section 4).

| | A — keep current | B — retain, link-only | C — retain, bounded excerpt |
|---|---|---|---|
| Record page | Full "Stored source text" body, machine summary and machine headline as now | Official link, source identity, date, IPR record ID and citation blocks; no stored body; labelled like the existing "Source-use limits" branch | Short excerpt of a length the owner sets, with link; machine output labelled as now |
| China Desk | Unchanged | Entries show as link-only records, not full-text records (README §2: must not masquerade) | Entries show the excerpt |
| Archive | Unchanged (titles, no text) | Unchanged unless the owner also restricts headlines | Unchanged |
| Search | Unchanged | Index on permitted fields only; body text no longer indexable | Index on the excerpt only |
| Engineering | None | A China link-only branch fed by a permitted-field projection shared by record, desk, Archive, search, feed and the DB/export surfaces (README §2). Tests that a withheld body cannot reach any surface. | Same projection plus a deterministic excerpt rule. |
| What it does **not** change | | The public repository's tracked DB and git history still contain the text already committed. Removing it is a separate decision and this memo does not propose history rewriting. | Same |

None of A, B, C is a legal safe harbour. They differ in how much publisher text
IPR republishes and in how much work they take.

## 4. Per-family decision records

Each section is self-contained. Quoted text is verbatim from pages fetched on
**3 November 2026** (HTTP 200, no cache). "Stored" means the tracked DB.

### The ten decision fields (identical in each family)

1. Retention: collector access, tracked DB, public git, private custody.
2. Model input: external model processing of title and stored text — relevance screening, analysis, headline translation (Section 2, item 2).
3. Full original text on the record page.
4. "Copy source text" and "Copy as held" controls (citation strings today).
5. Machine headline translation.
6. Machine summary / analysis.
7. Machine body translation (stored; not rendered today).
8. Link-only record.
9. Scope in time: new records only, or also the existing records, the tracked DB and the private backup.
10. Who decided, when, and where it is recorded.

<a id="mod_china"></a>
### 4.1 `mod_china` — Ministry of National Defense (国防部), Tier A, original

**Evidence**

| Item | Finding |
|---|---|
| Stored | 201 records, 197 with text; 2026-05-20 to 2026-11-03. Record 5793 (spokesperson release) has no stored text. |
| Live page checked | Record 5956, `http://www.mod.gov.cn/gfbw/wzll/hj/16497514.html`. Byline 来源：解放军报 (PLA Daily), published 2026-11-02 07:19:43. |
| Footer notice | `未经本网书面授权，请勿转载、摘编或建立镜像，否则视为侵权。` with `Copyright © 2026 mod.gov.cn All Rights Reserved`. |
| 版权声明 page | `http://www.mod.gov.cn/zjlm/wzdt_226173/index.html#S3`: `凡本网注明 “来源：XXX（非国防部网站）” 的作品，均由其他媒体及相关单位提供。任何媒体或互联网站如需转载，必须与相应提供单位直接联系获得合法授权。` |
| robots.txt | None found (404 redirect). Separate evidence from the terms above. |

Reading, not a conclusion: the footer names reprinting, excerpting (摘编) and
mirroring. The 版权声明 points reuse of works marked as from non-MOD outlets to
the supplying unit. Record 5956 is marked as from PLA Daily, so for such records
the relevant publisher may be 81.cn (4.2), whose notice is different. Whether
the owner wants one rule for the whole family regardless of byline, or a
per-byline rule, is a question below. Classifying records by byline is
engineering work not done here.

**Options and consequences** (counts are this family's records)

| | A | B | C |
|---|---|---|---|
| Record page | 197 full bodies stay public | 201 link-only; 183 machine summaries a separate choice | Excerpt on 197; summaries as chosen |
| China Desk / Archive / search | Unchanged | Desk shows link-only; Archive titles unchanged; body leaves search | Excerpt only in search |
| Engineering | None | Source-level link-only branch and projection (Section 3) | Plus excerpt rule |
| Note | The footer names 摘编, so C is not obviously closer to the notice than A | Closest to the notice's wording | |

**Recommendation (advice only): B.** Of the three options, B republishes the
least text of an institution that states a written-authorization requirement
for reprint and excerpt. The footer's wording also bears on C. This is a risk
and editorial judgment, not a finding that A is impermissible.

**Exact owner questions**

1. Retention: keep collecting and storing full text for this family? Keep it in the tracked (public) DB, or only in private custody going forward?
2. Model input: may titles and stored text continue to go to the external model for relevance screening and analysis (about 199 screened, 183 analysed so far)?
3. Public body: A, B or C for the record page?
4. Machine headline translation and machine summary: keep, or withhold along with the body?
5. Machine body translation: keep stored and unrendered, or stop producing it?
6. Citation controls: keep as citation-only?
7. Byline: one rule for all `mod_china` records, or different treatment where the byline names another outlet (as 5956 does)?
8. Scope: new records only, or also the 201 existing records and the stored copies?

**OWNER DECISION PENDING** — retention: PENDING · model input: PENDING · full
text: PENDING · copy controls: PENDING · headline translation: PENDING ·
summary: PENDING · body translation: PENDING · link-only: PENDING · scope:
PENDING · decided by / date / record: PENDING.

<a id="pla_daily"></a>
### 4.2 `pla_daily` — PLA Daily (解放军报) via 81.cn, Tier B, original

**Evidence**

| Item | Finding |
|---|---|
| Stored | 826 records (55% of the China corpus), 821 with text; 2026-05-07 to 2026-11-03. |
| Live page checked | Record 6007, `http://www.81.cn/yw_208727/16497826.html`. Byline 来源：国防部网. |
| Footer notice | `本网站刊登的新闻信息和专题专栏资料，均为中国军网版权所有，未经协议授权，禁止下载使用` with `Copyright ©1999- 2026 www.81.cn All Rights Reserved`. |
| Terms page | No dedicated 版权声明 link found on the page; a guessed URL returned a 404 body. Not located is not "does not exist". |
| robots.txt | Empty. Separate evidence. |

Reading, not a conclusion: the footer claims copyright for 中国军网 and
prohibits download use without an agreement. The page is bylined to the MOD site
while claiming 中国军网 as owner, so ownership and byline do not line up. That
mismatch is only noted, not repaired.

**Options and consequences**

| | A | B | C |
|---|---|---|---|
| Record page | 821 full bodies stay public | 826 link-only; 547 machine summaries a separate choice | Excerpt on 821 |
| China Desk / Archive / search | Unchanged | Largest effect of any family: most desk entries become link-only | Excerpt only in search |
| Engineering | None | Source-level branch and projection | Plus excerpt rule |
| Note | The footer says download use needs an agreement | | |

**Recommendation (advice only): B.** The stated restriction names download use,
and storing and republishing the body is the closest analogue. B also has the
widest visible effect, which the owner may weigh.

**Exact owner questions**

1. Retention: continue collecting and storing the 826 records' text? Tracked DB or private only?
2. Model input: may titles and stored text continue to be sent to the external model for relevance screening and analysis (about 762 screened, 547 analysed so far)?
3. Public body: A, B or C?
4. Machine headline translation and summary: keep or withhold?
5. Machine body translation (547 stored, unrendered): keep stored, or stop?
6. Citation controls: keep as citation-only?
7. Whether to seek an agreement (a contact decision for the owner; none was made here).
8. Scope: new only, or the 826 existing records and stored copies?

**OWNER DECISION PENDING** — retention: PENDING · model input: PENDING · full
text: PENDING · copy controls: PENDING · headline translation: PENDING ·
summary: PENDING · body translation: PENDING · link-only: PENDING · scope:
PENDING · decided by / date / record: PENDING.

<a id="xinhua_mil"></a>
### 4.3 `xinhua_mil` — Xinhua Military (新华军事), Tier C, syndicated

**Evidence**

| Item | Finding |
|---|---|
| Stored | 223 records, all with text; 2026-09-15 to 2026-11-03. Only 23 have a machine summary or translation. |
| Live page checked | Record 6030, `https://www.news.cn/milpro/20261103/df6fd6a0deaa4445b9e4328edd4f3e12/c.html`. Header 新华通讯社主办; byline 来源：新华网. Stored body is a 57-character video caption (secondary finding, out of scope). |
| Footer notice | `Copyright © 2000 - 2026 XINHUANET.com　All Rights Reserved.` and `制作单位：新华网股份有限公司　　版权所有：新华网股份有限公司` |
| Use restriction | None seen on the page. No Xinhua terms page was fetched. |
| robots.txt | `Allow: /` (file headed for `www.xinhuanet.com`). Separate evidence from any terms. |

Reading, not a conclusion: the page states ownership and no restriction. An
absent restriction is not a grant, and generic ownership text is the same kind
of statement as `china_mil_online`'s.

**Options and consequences**

| | A | B | C |
|---|---|---|---|
| Record page | 223 full bodies (many short captions) stay | 223 link-only | Excerpt; for short items the excerpt may equal the body |
| China Desk / Archive / search | Unchanged | Smallest family; small visible effect | Smallest effect |
| Engineering | None | Source-level branch and projection | Plus excerpt rule |

**Recommendation (advice only): C**, at lower confidence than for the other
families. The evidence found contains no use restriction, so A is also
consistent with it; C keeps the record readable while limiting full
republication of a state agency's text. The owner's editorial preference and
risk appetite decide between A and C.

**Exact owner questions**

1. Retention: continue storing text? Tracked DB or private only?
2. Model input: continue? (About 184 of 223 were screened by a model, 23 analysed; screening sends the body too.)
3. Public body: A, B or C? If C, what excerpt rule?
4. Machine headline translation and summary: keep or withhold?
5. Machine body translation (23 stored, unrendered): keep stored, or stop?
6. Citation controls: keep as citation-only?
7. Scope: new only, or the 223 existing records?

**OWNER DECISION PENDING** — retention: PENDING · model input: PENDING · full
text: PENDING · copy controls: PENDING · headline translation: PENDING ·
summary: PENDING · body translation: PENDING · link-only: PENDING · scope:
PENDING · decided by / date / record: PENDING.

<a id="china_mil_online"></a>
### 4.4 `china_mil_online` — China Military Online (English), Tier B, mirror

**Evidence**

| Item | Finding |
|---|---|
| Stored | 203 records, all with text; 2026-05-12 to 2026-11-03. 34 have no machine output. Manifest declares host `english.chinamil.com.cn`; records are served from `eng.chinamil.com.cn`. |
| Live page checked | Record 5999, `http://eng.chinamil.com.cn/2025xb/H_251454/L_251456/16497862.html`. Byline "Source China Military Online, Editor Chen Zhuo, Time 2026-11-03 20:26:54". |
| Footer notice | "Copyright © China Military. All rights reserved." (generic) |
| Meta | `robots: noindex` on the page. No terms link; only About Us and the Chinese edition. |
| robots.txt | None found (404 redirect). Separate evidence. |

Reading, not a conclusion: a generic copyright line and a `noindex` directive.
`noindex` is a request about search-engine indexing, not a reuse term, but it is
relevant to whether IPR's own search and Archive should expose this family's
text.

**Options and consequences**

| | A | B | C |
|---|---|---|---|
| Record page | 203 full English bodies stay | 203 link-only | Excerpt on 203 |
| China Desk / Archive / search | Unchanged | Body leaves search | Excerpt only in search |
| Engineering | None | Source-level branch and projection | Plus excerpt rule |
| Note | English original: no translation involved | | |

**Recommendation (advice only): C**, at lower confidence. The restriction
evidence is a generic line, so A is also consistent with it. `noindex` is a
reason to consider keeping this family's full text out of IPR search.

**Exact owner questions**

1. Retention: continue storing text? Tracked DB or private only?
2. Model input: continue? (About 196 screened, 169 analysed so far.)
3. Public body: A, B or C?
4. Should the publisher's `noindex` shape IPR search and Archive exposure for this family?
5. Machine summary: keep or withhold? (Headline translation is not applicable to English originals.)
6. Citation controls: keep as citation-only?
7. Scope: new only, or the 203 existing records?

**OWNER DECISION PENDING** — retention: PENDING · model input: PENDING · full
text: PENDING · copy controls: PENDING · headline translation: not applicable
unless owner says otherwise · summary: PENDING · body translation: not
applicable (English original) · link-only: PENDING · scope: PENDING · decided
by / date / record: PENDING.

<a id="global_times_mil"></a>
### 4.5 `global_times_mil` — Global Times, Defense, Tier D, original (English)

**Evidence**

| Item | Finding |
|---|---|
| Stored | 60 records, all with text and machine summary; 2026-05-13 to 2026-11-03. |
| Live page checked | Record 6002, `https://www.globaltimes.cn/page/202611/1373566.shtml`. |
| Page notices | Footer "Copyright © 2025 Global Times All Right Reserved"; meta COPYRIGHT "Copyright 2021 by The Global Times"; footer link "Terms of Service". |
| Terms | `https://www.globaltimes.cn/term/index.html`, "Latest update: December 8, 2020". |
| robots.txt | `User-agent: *` with a Sitemap line and no Disallow. Separate evidence from the Terms. |

Terms of Service, quoted minimally:

- §1 grants a "limited, revocable, non-exclusive, non-transferable license to access and make personal, non-commercial use". The licence does not include "any derivative use" or "any use of data mining, robots, or similar data gathering and extraction tools".
- §2: content is owned by GT or its licensors; users "may not copy, distribute, transmit, display, perform, reproduce, publish, license, create derivative works from, transfer or sell any Content", introduced by "Except as permitted by any applicable local copyright laws"; reuse needs "prior written permission", qualified by "Except as authorized under any applicable local copyright law".
- §7: "Creating or maintaining any link from another web site to any page on the Sites without our prior written permission is prohibited."
- §11: "you will not use any robot, spider, scraper or other automated means to access the Sites for any purpose without our prior express written permission".
- §17 and §19: governed by PRC law with Beijing courts; "Copyright © 2020, Global Times or its licensors."

Reading, not a conclusion: this is the most detailed publisher text in the
family set and it speaks to retention (automated access), model input
(derivative use, data mining) and display (copy, reproduce, link). The robots
file and the Terms say different things and are separate evidence. **None of
A, B or C fully matches the Terms as written**, because §7 addresses even
linking. The Terms are dated 2020 and apply "except as authorized under any
applicable local copyright law", which this memo does not interpret.

**Options and consequences**

| | A | B | C |
|---|---|---|---|
| Record page | 60 full bodies stay | 60 link-only (still a link, which §7 addresses) | Excerpt on 60 |
| China Desk / Archive / search | Unchanged | Body leaves search | Excerpt only |
| Engineering | None | Source-level branch and projection | Plus excerpt rule |
| Beyond the brief | A fourth path exists: no public reference to this family and/or stopping collection. It would change source activation, so it is outside this docs phase and is named only so the owner knows it exists. | | |

**Recommendation (advice only): B for the public body**, and settle retention
and model input first, because §1 and §11 bear on automated collection and
derivative use rather than only on display. If the owner wants the family kept
in the corpus, B is the lower-republication choice; it does not resolve the
§7 linking text.

**Exact owner questions**

1. Retention: continue automated collection and storage for this family? Tracked DB or private only?
2. Model input: continue sending titles and stored text to the external model (all 60 screened and analysed so far)?
3. Public body: A, B or C? Is a link-only record acceptable given §7?
4. Machine summary: keep or withhold?
5. Citation controls: keep as citation-only?
6. Is a permission request to the publisher wanted? (A contact decision for the owner; none was made here.)
7. Scope: new only, or the 60 existing records?

**OWNER DECISION PENDING** — retention: PENDING · model input: PENDING · full
text: PENDING · copy controls: PENDING · headline translation: not applicable
unless owner says otherwise · summary: PENDING · body translation: not
applicable (English original) · link-only: PENDING · scope: PENDING · decided
by / date / record: PENDING.

## 5. Questions that cut across all five families

1. **Public repository.** The repo is public and tracks `pla_watch.db`, so full
   original text and the machine body translation for all 1,513 rows are already
   in a public file and in git history. A link-only *site* does not remove that.
   The owner decides whether the tracked DB's text columns need handling, and
   this memo does not propose history rewriting.
2. **Retroactivity.** Does each decision apply to new records only, or also to
   the 1,513 live record pages, the DB and the private custody backup? Accepted
   paid model output is preserved and not regenerated merely to change its
   wrapper (AGENTS.md).
3. **Maritime-dossier grant.** Does anything decided here change the narrow
   25 Oct 2026 five-record grant, or is it left as it is?
4. **Headline policy.** Headlines and original titles appear in the Archive index.
   Are they treated as a separate component, or as part of the body decision?
5. **Where the decision is recorded.** The README §1 model is one authoritative
   record that the manifest references. The owner chooses whether that is
   [`DECISION_LOG.md`](../../DECISION_LOG.md) or this file once filled in.

## 6. What happens after the owner decides

Only after a decision exists: `desks/china/manifest.json` may reference it;
then one bounded engineering phase can add the China projection and gating
(Section 3), with tests that a withheld component cannot reach the record
page, desk list, Archive, search, feed or DB/export. Engineering is not started
speculatively.

## 7. Limits and what was not done

- Legal status was not assessed. No publisher was contacted. No source was
  activated, deactivated or reprocessed.
- Stored text was not compared with the live page body; the comparison covers
  record identity (URL, byline, date) and publisher notices.
- `output/china.html`, `output/article/*.html` and feed contents were not
  inspected in detail.
- No Xinhua or China Military Online terms page was fetched; none was linked
  from the pages checked.
- Not addressed (the audit's secondary findings): origin-label mismatch on
  records 5956 and 6007, the undisplayed mirror/syndicated flag, the Xinhua
  57-character stub (6030), stale registry and collection-health text, and
  historical gaps.
- Publisher text was fetched with the Firecrawl scrape tool, and `robots.txt`
  files with a labelled one-off request. Nothing else was fetched.
