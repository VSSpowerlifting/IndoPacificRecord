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

## Verified public exposure inventory (29 October 2026)

The read-only inventory workflow on PR #913 inspected a genuine repository checkout
without logging or copying any source text:

- 98 Singapore MINDEF article rows in the publicly tracked SQLite database.
- 97 rows with nonempty captured original bodies; 97 generated record pages expose a source-text container.
- 98 original titles and 76 model summaries remain populated in the public SQLite snapshot.
- 384 unapproved outbound hyperlink occurrences in generated HTML, including other Brief and Dossier pages; 3 approved hyperlink occurrences.
- This is a **working-tree inventory**, not a historical Git, Pages branch, CDN or legal audit.
- Targeted baseline evidence: Actions run `40828896162`, 23 synthetic tests passed; the inventory's `release_eligible_from_this_scan` was `false`.

`scripts/audit_mindef_public_surfaces.py` exposes a safe JSON census;
`--enforce` returns nonzero if any checked exposure remains. Report-only
mode deliberately **does not** imply clearance.

## Non-destructive migration staging (not production)

`scripts/stage_mindef_public_projection.py` stages three files **outside**
the public checkout, refusing overwrites: a mode-0600 full-fidelity SQLite
custody copy, a mode-0600 candidate public SQLite copy with Singapore
MINDEF original/translated text, title and machine-reasoning fields set to
NULL, and a hash/count receipt. It verifies private originals against source,
unrelated article rows unchanged and SQLite integrity; the original input is
not mutated. The retained `content_hash` remains the historical original
fingerprint (not a hash of redacted display fields).

**The staged public DB is NOT ready for publication.** Before a release:
1. Transfer and independently verify the full-fidelity copy in durable
   authenticated *private* custody. An ephemeral staging path does not count.
2. Route Singapore collection/analysis writes to an authorized private store
   or hold them; a subsequent Daily run must not refill redacted public fields.
3. Audit dependent tables, renderer title/summary fallbacks, Archive/Desk,
   record cards, feeds, editorial Brief/Dossier links, and all generated data.
   Rerender from the public-safe projection and run the exposure audit in
   `--enforce` mode; every existing unapproved link must be dispositioned
   by the author/editor or removed from the public version, not relabeled as
   permission.
4. Require production schema, snapshot, source counts, citation identity and
   unrelated-desks regression checks on the candidate, exact-head CI and
   a controlled deploy/readback. Do not deploy a candidate that is merely
   a DB copy but has incompatible reader templates.
5. Handle previously public Git commits, gh-pages snapshots, external
   archives and caches as a separate disclosure/remediation problem. A
   current-tree cleanup cannot erase history; do not force-push without
   a deliberate preservation and legal review.

The existing Daily workflow publishes tracked `pla_watch.db` and `output/`
to `main`, then deploys to `gh-pages`. The migration must change that
boundary consistently; manually editing `output/` or deleting live records
is not an acceptable shortcut.

## Brief source attribution boundary

The 25 October 2026 Bersama Lima Brief is bound to an exact reviewed editorial fingerprint, references and source-support matrix. This email removes the MINDEF hyperlink restriction **only for the two approved URLs**; it does not independently verify their factual content, alter the already-reviewed manuscript or substitute for editorial approval of revised references. Update the Brief through its existing editorial version/review mechanism, not by silently adding two unreviewed publisher references or bypassing its release checks.

**Stop condition:** a tested PR with no scope expansion; no automated merge, deploy, source-collector activation, or publisher-text migration is implied by this document.
