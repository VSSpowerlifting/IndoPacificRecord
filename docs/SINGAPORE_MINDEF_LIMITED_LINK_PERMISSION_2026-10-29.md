# Singapore MINDEF: narrowly scoped hyperlink permission (29 October 2026)

## Evidence and scope

- **Request sent:** 26 October 2026, from IPR's founder, concerning two official releases and hyperlinking for a human-authored analytical Brief.
- **Permission received:** 29 October 2026 from Singapore MINDEF Public and Digital Communications Directorate, Media Relations.
- **Permission granted:** the *limited linking request* to these exact URLs:
  - https://www.mindef.gov.sg/news-and-events/latest-releases/23oct26-nr2/
  - https://www.mindef.gov.sg/news-and-events/latest-releases/31may25_nr3/
- **Private evidence custody:** correspondence retained in the publisher-contact Gmail account under label `IPR/Source Permissions`. Do **not** copy the email, contacts, personal data, signature or attachments into this public repository.

The original request explicitly stated that the Brief uses independent commentary and factual paraphrase, **not** MINDEF photographs or article text, and does not imply MINDEF endorsement. The reply agreed to the limited linking request. It **does not** authorize reproduction of full text, images, long excerpts, other URLs, dataset distribution, model processing or expansion of unattended collection. MINDEF [Terms of Use](https://www.mindef.gov.sg/terms-of-use/) §§5–6 continue to apply.

## Immediate code boundary

- `core/mindef_permissions.py` uses an exact two-URL allowlist for direct links from MINDEF source record pages.
- The public `record.html` branch for `sg_mindef_releases` withholds captured article bodies regardless of whether the record is one of the two approved hyperlinks.
- Captured corpus records, source hashes and private evidence are **not** edited. The public rendering decision must not rewrite the historical capture.
- On previously generated/deployed pages this mitigation does **not** take effect until the governed render/deploy cycle runs.
- Other reader surfaces (source pages, searchable cards, archive citations, historical HTML, feeds, link exports) must be audited for MINDEF URLs and reproduction before declaring site-wide compliance. The record-page fix by itself is not a complete audit.

## Critical repository-distribution blocker

The repository is public and tracks `pla_watch.db` and generated `output/`. The live renderer reads MINDEF captured bodies from the tracked SQLite file. **Withholding text in the HTML template does not remove public access to those archived originals through repository contents, earlier generated files, GitHub Pages deployments, or repository history.** These distinct distribution paths require a rights-aware storage and publishing migration. Do not rewrite provenance, corrupt source hashes, casually delete the DB, force-push history, or silently exclude records without an explicit validated migration and recovery plan. Verify the actual bytes and exposure before choosing a remediation.

This PR is a contained reader-page safeguard, **not** a claim of public-data rights compliance. It must remain draft/unmerged pending a broader source-use review and release plan.

## Brief source attribution boundary

The 25 October 2026 Bersama Lima Brief is bound to an exact reviewed editorial fingerprint, references and source-support matrix. This email removes the MINDEF hyperlink restriction **only for the two approved URLs**; it does not independently verify their factual content, alter the already-reviewed manuscript or substitute for editorial approval of revised references. Update the Brief through its existing editorial version/review mechanism, not by silently adding two unreviewed publisher references or bypassing its release checks.

**Stop condition:** a tested PR with no scope expansion; no automated merge, deploy, source-collector activation, or publisher-text migration is implied by this document.
