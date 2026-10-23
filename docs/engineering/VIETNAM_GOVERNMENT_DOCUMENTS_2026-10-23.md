# Vietnam Government Office official documents — source and use determination (2026-10-23)

Source family: `vn_vpcp_official_documents_vi` · desk: Vietnam · publisher
portal: `https://vanban.chinhphu.vn/` · issuer: Văn phòng Chính phủ
(Government Office).

This is an **engineering determination** within the October 18–21 desk-delivery
rulings. It is not an owner approval, a publisher licence or a legal opinion.
It is machine-enforced by `config/vietnam_vpcp_metadata_policy.json`; the
collector refuses to run if that file differs from the values below.

## What the source is

The portal's document-search listing (`https://vanban.chinhphu.vn/`, first
page, 50 entries, newest issue date first) links each formal document to a
detail page (`?pageid=27160&docid=N`) that carries a metadata table: document
number (`Số ký hiệu`), issue date, type, **issuing body (`Cơ quan ban hành`)**,
signatory, subject (`Trích yếu`) and the PDF attachment link. The portal hosts
documents of many institutions (Prime Minister `QĐ-TTg`, ministries, provinces,
consolidated texts `VBHN`). Only documents whose detail page names
`Văn phòng Chính phủ` as issuer qualify; the number's `VPCP` token is a cheap
pre-filter, never the proof. Hosting portal (operated by the Government
Information and Communications Department), issuer, signatory and the
authority a document refers to are stored and shown separately.

## Access conditions observed on 2026-10-23

| Host | Check | Result |
|---|---|---|
| `vanban.chinhphu.vn` | `/robots.txt`, identifiable collector User-Agent | HTTP 200, `User-agent: *` / `Allow: /` |
| `vanban.chinhphu.vn` | listing and detail pages | HTTP 200 HTML, no access challenge |
| `datafiles.chinhphu.vn` | `/robots.txt` | HTTP 403 `AccessDenied` (object-store error, not a rules file) |

The collector reuses the screened Vietnam transport (HTTPS, host allowlist,
robots check, spacing, request/byte budget, no redirects off host, challenge
detection). It makes at most 52 requests per run (robots, listing, and a
detail page per Government Office candidate; the listing has at most 50
entries). Documents not yet stored are always fetched, so a busy week cannot
silently drop one. Only re-reads of already stored documents are capped (15,
newest first) and the number skipped is reported as
`rechecks_skipped_by_budget`.

## Permitted use (enforced)

1. **Public bibliographic metadata** — document number, type, issuer,
   signatory, issue date, effective date only when the table states it, the
   official subject line, and the official link. Issue date is *not* a posting
   date; first observation by IPR is recorded separately.
   *Basis for the subject line:* a formal document's number and subject are the
   document's own identifier. Vietnam's Law on Intellectual Property (50/2005/QH11,
   as amended) Article 15 places legal-normative and administrative documents
   outside copyright subject matter. That supports reproducing a document's
   identifying subject line with source credit. It is not read as covering PDF
   annexes, figures, photographs or third-party material, and the portal's
   request for attribution is honoured by naming the Government Office, the
   portal operator and the official link on every record.
2. **No production attachment download.** The PDF host returned 403 for `robots.txt`, no
   standing decision covers copying originals, and nothing downstream needs
   them. `attachment_download: false`.
3. **No external-model transmission, no public body, translation or machine
   explanation.** The 2026-10-22 MPS decision applies only to MPS; the MOIT
   consent hold applies only to MOIT. Neither is inherited. A one-line subject
   is not a document, so no analysis is generated from it: the page says the
   text has not been read.
4. **Subject-index routing.** `processing/government_document_intake.topics()`
   lists a record on the desk only when the portal subject matches a bounded
   set of strategic topics (energy supply, aviation security, defense and
   maritime security, strategic infrastructure, strategic industry). It is a
   routing label from metadata, not a statement about the document's contents,
   implementation or significance. Routine personnel, ceremonial and
   other administrative documents are retained as version evidence only.

## Operation

* Runs as a step of the existing scheduled Daily (same DB writer, commit
  protections and single Pages deploy), guarded by repository variable
  `VIETNAM_VPCP_METADATA_ENABLED=true`, `continue-on-error`, so an upstream
  failure cannot stop MPS or any other desk. A dispatch with
  `vpcp_metadata_only=true` collects and renders without any other source,
  model, handoff or success marker.
* Every attempt, including zero-new and failed ones, is stored in
  `official_document_collection_runs`. Failure modes (challenge, malformed or
  truncated listing, non-HTTPS/off-host links, unsupported attachment link,
  detail/listing date mismatch) hold only the affected record or run and say why.
* Identity is the portal `docid` (`vpcp-vi:<docid>`), never the number or title.
  Every observed metadata version is kept in `official_document_versions`; the
  public projection follows the newest validated version. A revised subject
  outside the topical set withdraws the projection but not the history.
* A listing that no longer overlaps the previous window records
  `coverage_gap: true`, appends to a permanent `coverage_gaps` chain and
  restarts `continuous_since_run` at that run; documents that scrolled out
  unseen are not claimed. Collection resumes from the visible window.
* The listing window is the portal's first page, not an archive:
  `archive_complete: false` is carried in every report.

## Out of scope / still held

Production attachment retrieval, text extraction, translation, model screening
of document text, machine-labelled explanations, public PDFs and OCR remain
held. The owner's bounded local assessment below does not activate these uses.

## Production acceptance — 23 October 2026

PR [#863](https://github.com/VSSpowerlifting/IndoPacificRecord/pull/863),
head `6fe9e11c7341cef0aaf2d05b6e10ebf893aaf775`, merged as
`328ee95af58daeb10448e2d7a2c3ebf5a0adc896`. The final production code revision
`3e5b3f6fafa0812aef0e510d3fea24cb80596d86` includes two test repairs: expect
the admitted ninth source, and distinguish independent database insertion
clocks from signed handoff provenance while retaining replay idempotency.

Shared [Daily run 40023459779](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/40023459779)
passed 7,945 offline tests (15 skipped), tracked-database preservation,
55 reconciliation tests and output validation (10 governed warnings).
Collection receipt `40023459779-1`, observed `2026-10-23T21:19:15Z`, records
four new topical references, five filtered documents, zero held, 11 requests,
zero model calls and no coverage gap. The first-page boundary remains explicit;
this is not a complete archive.

Production commit `86658b851322e34e68eb47e900fa4099ba18ec5a` changed only
the shared official-link projection, immutable metadata versions and collection
run tables, plus generated output. Existing article rows, other official links
and existing Archive index records are unchanged. Pages commit
`a16d84f372247aef70d9ed070ef8b71dd8e77202` deployed in successful
[Pages run 40025995816](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/40025995816).
Vietnam HTML, Archive HTML and research-index HTTPS responses were byte-identical
to both main and gh-pages. Browser verification found all four references,
working official links, the correct acceptance metadata, Archive search results
and no horizontal overflow at 375 pixels.

* [10790/VPCP-CN — Vietnam Desk](https://indopacificrecord.org/vietnam.html#vpcp-vi-220077),
  issued 2026-10-22, Văn phòng Chính phủ, signatory Đặng Xuân Phong.
* [545/TB-VPCP — Vietnam Desk](https://indopacificrecord.org/vietnam.html#vpcp-vi-220078),
  issued 2026-10-22, Văn phòng Chính phủ, signatory Nguyễn Danh Huy.
* [Live Archive search](https://indopacificrecord.org/archive.html?scope=published&record_type=official_link&q=10790%2FVPCP-CN).

`VIETNAM_VPCP_METADATA_ENABLED=true` and the existing Daily workflow is active.
Its unchanged UTC retry windows are 12:23, 12:53, 13:23, 13:53 and 14:23,
subject to the normal shared Daily scheduling guard. The acceptance dispatch
used `vpcp_metadata_only=true`, skipped other collection/model paths and the
full-Daily success marker. The next natural scheduled cycle has not yet been
observed; no scheduled success is inferred from this manual acceptance.

## Bounded local PDF access assessment — after metadata release

The owner separately authorized a bounded technical assessment using official
links and direct extraction, while retaining separate control over external
model processing. This assessment did not change the production policy JSON,
collector, source-use permission or shared Daily architecture.

At `2026-10-23T21:23:47Z`, the attachment host's robots response was HTTP 403,
271 bytes, an XML object-store `AccessDenied` naming the bucket `robots.txt`.
It was not a robots rules file. [RFC 9309 §2.3.1.3](https://www.rfc-editor.org/rfc/rfc9309.html#section-2.3.1.3)
permits resource access when robots is unavailable with a 4xx response; that
protocol behavior is not a copyright licence or external-model authorization.
For this one-off assessment, the two exact publisher-linked PDF objects were
requested with the existing honest collector identity, verified TLS, no
redirects, cookies, proxies or retries, two-second spacing, finite timeouts,
a five-megabyte/file ceiling and a 40-page extraction ceiling. Any actual PDF
denial or challenge would have stopped the probe. Both objects returned 200;
no access restriction or production transport guard was circumvented or changed.

| Official linked PDF | Bytes | Local extraction | SHA-256 |
|---|---:|---|---|
| [10790/VPCP-CN](https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/10/10790_vpcp-cn_22102026_1-signed.signed.pdf) | 288,630 | 4/4 pages with text, 9,977 normalized characters | `b4ed9b383d46331baff568eaf30d191d8fae302fb9bb99f3aa9e3f675184e2df` |
| [545/TB-VPCP](https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/10/545_tb-vpcp_22102026_1-signed.signed.pdf) | 1,009,619 | 5/5 pages with text, 12,947 normalized characters | `f37efe49b108798c500389c7ea2dad7715f38f416c68add853ed94fe41b940ea` |

Both responses had `application/pdf` MIME and `%PDF-` signatures; neither was
encrypted and neither had extraction page failures. Local checks found the
formal issuer and expected signatory in both. The full `10790/VPCP-CN`
identifier matched; `545/TB-VPCP` did not match even with whitespace tolerance.
Text on every page does not establish visual or semantic completeness, and
cryptographic signatures were not verified. Complete full-document verification,
translation and analysis are therefore **not claimed**.

Firecrawl retrieved only the official HTML bibliographic page for docid 220077
(HTTP 200, basic proxy, live fetch, cache storage disabled) and independently
returned the same PDF link. It did not fetch or parse either PDF. Extraction
ran locally; no original text or page image entered a model, public database,
site output or hosted parser. Private task-temp files and measurement receipts
remain outside the repository with restricted filesystem permissions. Public
metadata records continue to describe their production metadata-only evidence.

The remaining authorization for a future full-document production lane is a
source-specific decision covering model transmission, permitted public output
and bounded spend; successful HTTP access does not supply it. The existing
metadata fallback remains active in the meantime. Concurrent unfinished
full-text code was preserved separately and was not included in this release.
