# Japan Coast Guard linked-PDF completeness — research review (2026-10-08)

## Superseding source-scope decision — 9 November 2026

The founder has approved **English HTML article text as an independently qualifying original source** for JCG. The exact first-party /e/topics_archive/articleNNNN.html body and publisher date are the scope; linked PDFs, photographs and media are separate artifacts and do **not** gate eligibility, preservation, model preparation or release of an independently written factual explanation from the verified HTML text.

The historical comparison below remains useful for describing what the HTML does **not** cover. Do not claim HTML-plus-PDF completeness or silently combine the PDF content into an HTML record. Existing PDL1.0 first-party text conditions (attribution, changed-text notice where applicable, third-party and separately marked exclusions), authentic source-version replay and substantive QA still govern use. The standing source eligibility gate now includes `jp_jcg_press_en`. The code change does not activate collection, a model, public release or any paid work.


**Status: bounded research only; no documents admitted, no collector changes, no editorial approval.** This work is deliberately separate from main-target collector integration PR #212 and does not alter its CI.

## Why this matters

The JCG English HTML releases are first-party, substantive original sources, but each links a distinct original PDF. The live JCG adapter (#208, consolidating into #212) correctly archives only English HTML article body text and preserves the linked PDF URLs as *uncollected attachments*. An extracted HTML body of 985, 1,158 or 1,191 characters **cannot be called the entire release document** without comparing the attachments and determining their publication/status relationship.

Three official release identities are fixed for this test:

| ID | Official release | Publisher date | Linked attachment |
| --- | --- | --- | --- |
| jcg-en:9455 | https://www.kaiho.mlit.go.jp/e/topics_archive/article9455.html | 2026-10-06 | one official linked PDF, URL obtained from article |
| jcg-en:9453 | https://www.kaiho.mlit.go.jp/e/topics_archive/article9453.html | 2026-10-06 | one official linked PDF, URL obtained from article |
| jcg-en:9436 | https://www.kaiho.mlit.go.jp/e/topics_archive/article9436.html | 2026-09-29 | one official linked PDF, URL obtained from article |

The public BAKAMLA and PCG pages expose those links separately from the English HTML prose. The links are not citation-neutral duplications unless their actual contents establish it.

## Exactly scoped Actions experiment

`scripts/probe_japan_jcg_pdf_completeness.py` performs one `robots.txt` request (readable policy or an exact 404 absence only), then at most one GET for each of the three declared HTML article URLs, followed by one GET for the **single, publisher-linked, same-origin PDF** on each page. No URL guessing, redirects, retries, proxies, challenge solving, cookies, or third-party mirrors.

- HTML maximum 256 KiB; PDF maximum 2 MiB; max 12 PDF pages; request timeout 18 seconds and delay 2 seconds between GETs.
- PDFs are parsed **in memory** using the already declared `pypdf` dependency; encrypted, malformed or oversized documents are refused.
- Emit only official source URLs, HTTP-independent content SHA-256, byte count, PDF page count, machine-extracted text character counts, possible image-only pages, and limited token-overlap metrics.
- Never log, upload, commit or preserve PDF bytes, original HTML, extracted original prose, photographs or images. The Actions artifact is metadata only.
- Source-policy check: the JCG's stated PDL 1.0 default does **not** grant automatic permission over logos, separately marked material, or third-party photographs. This work does not copy any media or images.

## How to interpret the metrics

`html_coverage_ratio` is a mechanically computed approximate overlap of English word tokens found in the extracted PDF vs the scoped HTML body. It is not semantic equivalence, independent corroboration, translation verification or a publication permission determination. PDF image pages may contain text that `pypdf` cannot extract. It is **not** an automated statement that the HTML body contains every publisher disclosure.

- If PDFs provide additional substantive prose, create an **independently governed PDF companion extractor**, with official URL/date/issuer association, attachment-specific hashes, rights checks and distinct extraction fidelity tests. Do not inject new words into the existing HTML source record without an audit trail.
- If PDF is substantially identical to the HTML but adds images, preserve metadata about the linked original PDF and explain that its imagery was not archived.
- If a PDF is text-sparse or image-only, escalate to human original-document comparison. Do not substitute OCR or make invented completeness claims.
- If origin/rights/size/route is blocked, record explicit **not retrieved**, do not reinterpret the HTML article as full publisher coverage.

## Relation to production promotion

JCG's HTML article text can qualify independently once its exact captured HTML/text version, publisher dates, source authenticity, standing-text PDL1.0 application and relevant exceptions, and factual QA are verified. Preserve the `published_html_text_only` scope label and any attachment URL as **uncollected separate material**. A missing or text-different PDF cannot block the HTML-text component; it can only prevent claims that IPR has reproduced a full HTML-plus-PDF package. Historical Day 7/14/30 checkpoints describe observed reliability and never substitute for actual recurring source-to-reader verification or impose a new fixed wait.

Once the metadata-only Actions run finishes, preserve its exact run ID and the three per-source verdicts in activation issue #205. This research does not authorize any state branch writes or immediate production admission.
