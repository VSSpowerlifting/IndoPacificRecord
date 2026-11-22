# Desk strength criteria

> **Desk architecture/process supersession — 30 October 2026:** the
> [mandatory shared desk standard](desks/README.md) governs every current and future
> desk. This document's older common architecture, onboarding order and launch
> clocks do not override it. Source-specific decisions, restrictions, real
> evidence and still-used commands remain valid in their actual scope. This
> notice does not claim runtime migration, change permissions or activate a source.


What it takes for a desk to be called operationally strong, and what each
weaker word is allowed to mean. Written because "the Japan desk works" and "the
Japan desk discovers documents it cannot read" had been said about the same
desk in the same week, and only one of them was true.

This document defines **testable** criteria. Where a criterion cannot be
settled by evidence already in the repository — a ledger, a manifest, a
database, a review packet — it says so and names what would settle it.

`desks/registry.json` remains authoritative for a desk's status and public
presentation, and each desk's manifest remains authoritative for its sources.
Nothing here changes either. This document governs the **vocabulary** those
files are allowed to use about themselves.

---

## 1. Seven stages, and no borrowing between them

A desk is not one capability. It is seven, in order, and each is measured on
its own evidence:

| # | Stage | The question it answers | Settled by |
|---|---|---|---|
| 1 | **Discovery** | Can we learn that a document exists? | listing/feed status in the ledger |
| 2 | **Retrieval** | Can we fetch that document's bytes? | `retrieved` / `challenged` / `fetch_failures` |
| 3 | **Extraction** | Can we turn those bytes into correct text? | `extraction_failures`, stored body lengths |
| 4 | **Storage** | Is the result stored identifiably and once? | corpus counts, duplicate rate, state hash chain |
| 5 | **Analysis** | Does the record survive the processing pipeline? | analysis completion, terminal-state counts |
| 6 | **Public rendering** | Does a reader see it, described honestly? | renderer output, validator |
| 7 | **Promotion readiness** | Should any of this become public coverage? | checkpoint reviews + owner sign-off |

**A verdict at one stage never implies the next.** The rule this encodes:

> A desk must not be called functional because discovery works.

Discovery working means stage 1 passes. It says nothing about stages 2–7, and a
desk whose stage 2 fails is **access-constrained**, not functional. The honest
phrases are fixed:

* *discovery works, retrieval does not* — say exactly that; never "partial
  coverage", never "working";
* *retrieval works for one document family only* — name the family and its
  share; a 6 % yield is not "collecting";
* *collecting* — stages 1–4 pass on the desk's declared scope;
* *functional* — stages 1–5 pass;
* *public* — stage 6, and only after stage 7.

---

## 2. The criteria

Each criterion is **PASS**, **FAIL** or **UNMEASURED**. `UNMEASURED` is a real
verdict and is never rounded to `PASS`.

### C1 — At least one reliable authoritative listing path
*Stage 1.* The desk has at least one official, openly accessible route that
enumerates documents: a feed, an index, a sitemap, or a documented API.

**Measured by:** `listing_status == "ok"` on every scheduled run in the
evaluation window, with no run recording `listing_failure`.
**Fails when:** the only enumerating route is an index the edge refuses, or
when document URLs would have to be guessed. **Guessing URLs is not a listing
path** — a namespace an institution has not published to us is not discovery,
it is enumeration, and this project does not do it.

### C2 — Compliant access under robots and published policy
*Stage 1–2.* `robots.txt` is readable and permits every path touched.

**Measured by:** `robots_status == "allowed"` on every run.
**Fails when:** `robots.txt` is unreadable, or disallows the paths needed.
**A 403 on `robots.txt` and a 404 on `robots.txt` are different facts.** A 404
means no file exists and no restriction is stated. A 403 means the host is
refusing to tell this client the rules, and collection then has **no permission
basis** — which is a blocker on its own, independent of whether some other
endpoint happens to answer. Recording the distinction is mandatory.

### C3 — Deterministic canonical URLs and dates
*Stage 1, 4.* Every record has one canonical URL derived by a pure function of
the discovered link, and one publication date derived by a stated rule.

**Measured by:** re-deriving both from stored inputs reproduces the stored
values, for every record.
**Fails when:** a date is the feed's generation time rather than the document's
publication date, or when the URL-encoded date and the feed date disagree
without a ruled precedence. Where they disagree, the rule must be written down
and the disagreement rate reported — not averaged away.

### C4 — Successful body or document retrieval
*Stage 2.* A stated, measured share of discovered documents yields bytes.

**Measured by:** `retrieved / selected` per run, and the same ratio per
document family.
**Fails when:** the overall yield is below the desk's declared threshold, or
when yield is concentrated in one document family that is not representative of
the desk's declared scope. **Concentration is a failure even when the ratio is
not** — a desk retrieving only one recurring administrative notice type has not
retrieved its scope.

### C5 — Extraction and encoding integrity
*Stage 3.* Retrieved bytes become correct text in the correct encoding.

**Measured by:** fixture tests over real captured responses, asserting body
text, character encoding, and that navigation chrome is not mistaken for a
body.
**Fails when:** a stored body is empty for a document that is live and has
text, or when a stored body is the page's navigation rather than its article.
An empty body for a live document is an **extraction defect**, never a source
silence, and must never be reported as one.

### C6 — Deduplication
*Stage 4.* Identity is by canonical URL and by content hash of extracted text.
Never by title.

**Measured by:** duplicate rate per run, and a test asserting that a recurring
official title produces as many records as there were publications.
**Fails when:** dedup is title-derived, or when the duplicate rate is
indistinguishable from a stalled listing.

### C7 — Honest result taxonomy
*Stages 2–5.* Every run ends in one of the repository's existing results
(`ok`, `ok_no_publications`, `ok_all_duplicates`, `ok_all_filtered`,
`listing_failure`, `extraction_failure`, `fetch_failure`, `auth_failure`), and
failures are split into **fetch**, **extraction** and **access**.

**Measured by:** the ledger.
**Fails when:** a policy refusal is filed as an outage, or an outage as a
policy refusal. An access challenge is `access_challenged`; it is not a
`fetch_failure`, and a reader comparing two desks must not be led to conclude
one ministry publishes less than it does.

### C8 — Isolated shadow storage
*Stage 4.* A shadow desk writes only to its own database, on its own branch,
and the runner cannot name the production database or `output/`.

**Measured by:** the four barriers in `docs/SHADOW_COLLECTION.md` §Isolation,
each already covered by a test.
**Fails when:** any barrier is removed, including "temporarily".

### C9 — Append-only, hash-chained state
*Stage 4.* Each run appends one ledger entry carrying `state_sha256_before` and
`state_sha256_after`, and the chain is continuous.

**Measured by:** `scripts/review_shadow_state.py`, which reports
`state chain: coherent` or names the break.
**Fails when:** the chain breaks, a ledger is rewritten, or a push is forced.

### C10 — Scheduled-run continuity
*Stage 1–4.* Every scheduled day has a recorded terminal result, and expected
empty days are distinguishable from failures.

**Measured by:** one ledger per nominal target date, with
`target_date_source` recording which rule applied.
**Fails when:** a nominal day has no ledger. A missing day is an **anomaly
requiring disposition**, not a gap to be smoothed. Historical anomalies are
never rewritten to make a later count look tidy.

### C11 — Health and freshness reporting
*Stages 2–5.* Every run publishes a health verdict, and the desk's freshness is
readable without opening the database.

**Measured by:** `health` in the ledger; `scripts/source_health_report.py` for
production.
**Fails when:** a source that has never produced a record is left silently
enabled. A source with no working collector is reported as
`not_implemented` — or reclassified — and is never hidden.

### C12 — Source-version evidence, using shared review tooling
*Stage 7.* The existing common source/custody review path may be used with
source-specific issuer, identity, date, language, extraction and exception rules.
No separate country-specific review engine, fixed checkpoint day or new
per-record founder signature is compulsory for ordinary standing-eligible
machine Records.

**Measured by:** immutable authentic source and capture/version hashes,
reviewable exact-revision custody, truthful run and attempt dispositions,
correct source-specific rights, QA and retained exceptions. Source-specific
failed or incomplete evidence never qualifies through a generic checker.
**Fails when:** review substitutes another source's rules, ignores a hold,
omits meaningful original content or mistakes a metadata lead for its body.

### C13 — Minimum source-to-reader acceptance without launch clocks
The **11 November 2026 founder milestone** is one genuinely operational
source family per desk, with the sixteen-family original roster retained
as full-coverage completion. There is **no mandatory seven-day or thirty-day
prelaunch wait** or obligatory Day 7/14/30 human-review ceremony. Existing
successful review receipts remain valid evidence, but not independent
permission to activate a publisher or publish an item.

A minimum-operational family must demonstrate authentic permitted original
retrieval, versioned recoverable authorized custody, source-appropriate
factual and language QA, accurate machine-labeling and public-component
rights, a signed/authenticated shared processing/admission path, real
production DB and rendered Record/desk/Archive/search, controlled deployment
and independent HTTPS readback of the exact version. A subsequently observed
genuine unattended cycle must honestly report new, duplicate, quiet, error
or hold behavior, and prove representative recovery without resetting paid
attempts. This can happen as quickly as evidence allows; no invented streak
or thirty-day elapsed clock stands in for actual recurrence.

**Initial milestone:** at least one qualifying family independently passes
every applicable stage, with public labels naming that source and remaining
coverage gaps. **Full-scope milestone:** every family from the retained
2 November roster independently passes those same gates. Neither
metadata-only links nor synthetic tests certify a substantive family.
A separate editorial research desk may publish approved original IPR work
and verified references without pretending collection is live; human-authored
publications still require actual human editorial approval.

**Fails when:** the original is unavailable or held, source use is unresolved,
QA fails, versions/signatures mismatch, public use exceeds approved scope,
unattended recurrence is only scheduled rather than witnessed, recovery is
unproven, or live HTTPS readback has not occurred. A source rights finding,
PR merge, release switch, deployment and desk certification remain separate
events. No rule here activates a source, spends money, removes publisher
restrictions, changes a public desk status or certifies past runs.

---

## 3. Applying this to a blocked desk

A desk that fails C1 or C2 has no compliant path and cannot be repaired by
effort. The permitted responses are, in order:

1. **Find another openly accessible official route.** A different official
   index, an official feed, directly linked official PDFs, or another official
   publication system of the same institution.
2. **Retain as declared-only.** The desk keeps its declared scope and an honest
   status (`access_blocked`, or `shadow` with its constraint stated), collects
   nothing it cannot collect compliantly, and claims nothing.
3. **Replace the desk**, on evidence, through the comparison in
   `docs/DESK_RELIABILITY_REVIEW_2026-09-16.md` §7.

The responses that are **not** permitted, at any coverage cost: solving or
bypassing an access challenge, impersonating a browser, rotating identities,
using residential proxies, ignoring `robots.txt`, or enumerating a URL
namespace the institution has not published. Defeating a challenge destroys the
capability the rule protects — an institution must be able to recognise this
collector and refuse it.
