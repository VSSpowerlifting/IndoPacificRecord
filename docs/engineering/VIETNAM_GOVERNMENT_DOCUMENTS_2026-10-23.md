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
detection). It makes at most 17 requests per run: robots, listing, and at most
15 candidate detail pages. A heavy week caps the candidates (newest first) and
reports `candidates_skipped_by_budget`; it never holds the source.

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
2. **No attachment download.** The PDF host returned 403 for `robots.txt`, no
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
  `coverage_gap: true` once and resumes from the visible window.
* The listing window is the portal's first page, not an archive:
  `archive_complete: false` is carried in every report.

## Out of scope / still held

Attachment retrieval, text extraction, translation, model screening of
document text, machine-labelled explanations, public PDFs, OCR. Each needs a
separate source-use decision for this family; none is implied here.
