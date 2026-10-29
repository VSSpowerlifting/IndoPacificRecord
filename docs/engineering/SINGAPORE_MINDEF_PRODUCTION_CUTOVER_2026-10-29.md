# Singapore MINDEF rights-aware cutover candidate — 29 October 2026

Review candidate for PR #913. No merge, deployment, new collection, model
processing, publisher contact, history rewriting or evidence deletion is authorized.
The two exact hyperlinks in `core/mindef_permissions.py` are the entire written
link grant. Private storage is not a reproduction or model-input licence.

## Actual dependencies and implementation

| Existing path | Candidate behavior |
| --- | --- |
| `pipeline.py` → registry/adapter → public SQLite | MINDEF returns `skipped_disabled` before adapter construction. MINDEF backlog IDs are held before model dispatch; other Singapore publishers do not inherit this hold. China and other desks retain their paths. |
| Public `singapore_shadow.yml` → public shadow ref/artifact | Job explicitly held. No replacement collector or new schedule is activated. Existing evidence is retained privately. |
| `stage_mindef_public_projection.py` → SQLite | Stages a full-fidelity private copy, strips expression from the candidate, installs write guards, vacuums, verifies all unrelated tables and checks physical bytes. |
| Private authenticated Git readback → `verify_mindef_custody.py` | Independent gzip restore, byte SHA-256, every source identity/provenance/expression hash, all unrelated table digests, integrity and foreign keys. No original text is logged. |
| `install_candidate()` / `--install` | Requires matching custody recovery and staging receipts plus restored bytes. Refuses changed baselines and SQLite sidecars; copies safe bytes then atomically renames. Same-candidate retry is a no-op. |
| `site/render.py` → shared preview renderer → `output/` | MINDEF gets an explicitly described metadata label, dates, institutional identity and historical provenance. No original title/body, translation, summary or reasoning. Only the exact approved URLs become links. |
| Brief/Dossier loaders | Hold entire affected works. Canonical manuscripts, bylines, reference lists, approvals and fingerprints are unchanged. No substitute editorial approval is asserted. |
| Existing deploy validator | A projected DB triggers the MINDEF surface audit, including after normal Daily rebase/render. Restricted fields or links block deployment. |

SQLite guards reject expression insert/update, MINDEF machine-record writes,
and source-identity reassignment/deletion. They survive reopening and do not
depend on the scraper. The new `mindef_private_record_bindings` table contains
only original content/title/body hashes keyed to existing IDs. It lets editorial
reconciliation check historical version bindings without exposing source text;
it does not grant publication authority. Unknown migration tables/columns hold
projection for explicit schema review.

## Verified real custody

Baseline: public main `94146acd8751d6333dff18a7482a1d95e65a9834`, 98 records,
97 nonempty original bodies, 76 nonempty summaries. IDs, URLs, original content
hashes, source/run IDs, publication dates and collection timestamps match.

Three separate private payload refs were pushed without force to the existing
owner-selected `VSSpowerlifting/ipr-source-evidence-private` repository:

- `archive/singapore-production-20261029`: commit
  `636596266f760e9f5309c4a24eb8c609e82a9e66`; complete SQLite evidence snapshot
  plus 98 per-record provenance/expression-hash bindings. Restored SQLite SHA-256:
  `403734e312efd26f8df55f18164c8f43a38bc7b74f846e20add0e6028b9eda73`.
- `archive/singapore-shadow-frozen-20261029`: authentic public collector tip
  `2187b81051a804f1afdca1a2de99cad84ab43eff`; all 386 reachable native Git objects
  independently fetched from private GitHub and compared; `git fsck` passed.
- `archive/singapore-actions-20261029`: all 70 retained Singapore Actions ZIPs
  discovered by a complete paginated artifact inventory, 1,759,748 bytes.
  All 70 provider SHA-256 digests, independent private readbacks and ZIP CRCs
  verified. No original public artifact was deleted or had retention shortened.

Private visibility, the owner as sole listed collaborator and absence of a
private Pages site were checked. This is authenticated GitHub-only recovery,
not an independent-provider backup. The October 15 storage decision accepts
that limitation. Private payload branches must never be merged into public
main or uploaded in public CI/artifacts. Hash-only receipts are in
`docs/evidence/singapore-mindef-cutover-2026-10-29/verification.json`.

## Public and editorial verification

The candidate retains all 98 records. The seven original/translated/machine
expression fields and additional free-text processing/claim fields are NULL.
All unrelated table rows match the restored baseline; 1,277 unrelated rendered
record evidence containers also match. The physical DB has no freelist pages or
WAL/SHM/journal sidecars. A private scan checks 9,441 original-expression probes
against the rebuilt DB and 2,484 delivered textual files (35,731,377 bytes),
without logging probes. Shared generic model-disposition fragments on unrelated
records are excluded from the probes and those records are preserved.

The actual output audit finds zero source-body containers, zero unapproved
outbound MINDEF links and zero potential unapproved JSON URL occurrences.
Four HTML link occurrences use the exact approved URLs. Validation passes with
the existing 10 governed warnings. The focused regression ran 199 tests; the
normal Daily simulation collects a new unrelated record once across retries,
holds Singapore before acquisition, makes no model call, and preserves history.
A final 24-test boundary run and Chromium previews at 1280/375 px also pass.
Full exact-head CI is a separate mandatory release gate, recorded on PR #913.

Affected whole works held by the public loaders (reference IDs, not rewrites):

- `briefs/maritime-cooperation-2026.json`: records 4472, 4466.
- `briefs/trident-resolve-regional-scale-specific-chinese-tasks.json`: record 4935.
- `briefs/xiangshan-security-frames-defense-ties.json`: record 4426.
- `dossiers/maritime-cooperation-2026.json`: records 4466, 4472.
- `dossiers/china-singapore-naval-cooperation.json`: records 4452, 4454, 4466,
  4472, 4849, 4911 and external references x1–x7.

Brief No. 20 and Dylan Tanzi's authorship are unchanged. Issue #914 remains the
separate human decision for its proposed two-reference update. Component/browser
tests use explicit synthetic rights authority; they do not clear these real works.

## Historical exposure decision

Confirmed: the public main baseline carries the original DB/source expression;
the current `gh-pages` tip `7dba36012008d20f07b826d0e1c91ad9357ce0e4` contains
98 MINDEF record pages with 97 nonempty source-body containers. The public source
shadow ref remains available. The inventory found 880 public branches, no tags,
no releases and zero GitHub-reported forks. The 70 retained ZIPs remain public
repository artifacts subject to GitHub access controls. Earlier expired/deleted
artifacts, private clones, external caches, screenshots/media, and every blob in
all 880 branch histories are not independently exhaustively accounted for.
Existing canonical editorial source files and old replay fixtures also remain
in Git; this candidate makes no repository-wide erasure claim.

| Remedy | Assessment |
| --- | --- |
| A. Sanitize current tree | Lowest operational risk and preserves URLs; this PR contains DB/site exposure but leaves historical objects, old refs/artifacts and canonical editorial/replay files available. Interim containment only. |
| B. Coordinated history/reference cleanup | Recommended durable remedy while retaining the IPR repository/domain and citation routes. Requires a complete private mirror first, a reviewed source-path/blob inventory, coordinated writer freeze, rewrite/ref replacement, artifact disposition, collaborator reclones, and GitHub cache/PR-reference review. Commit links, signatures and old PR diffs can break. |
| C. Clean public repository/publication migration | Cleaner new object graph but larger workflow, credentials, branch-protection, Pages/domain and citation-continuity risk. Does not remove exposure from the old repository or external copies. Not recommended as the first choice. |

Approve A as an explicit interim release only if its remaining exposure is
accepted; approve B separately after the complete private mirror and precise
rewrite/removal plan are reviewed. No force-push, ref/artifact deletion, repository
visibility/identity change or external contact has been performed. GitHub's
[removal guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
describes fork/cache/reference coordination and limits Support's sensitive-data
removal service; availability of that service for copyright material is not
established. No procedure recalls copies already downloaded by others.

## Serialized release procedure — requires explicit final approval

1. Review exact-head full CI and the public/private PRs. Approve the bounded
   current-tree release, whole-work holds, Singapore collection/model hold and
   explicitly accepted historical exposure. Decide B separately.
2. Serialize with all DB/Pages writers; cancel old Singapore/Daily jobs before
   any fresh source access. Re-fetch main and compare its DB SHA-256 with the
   custody baseline `2ea891ff77ea17f60d58926cdc8091d6a8d84039d6d38df8196d804c38470638`.
   If it changed, preserve/read back the new snapshot and restage against current
   main, including new records. Never overwrite a newer Daily database.
3. For restaging, run the existing staging CLI outside the public checkout;
   push/read back the private evidence, restore it with `verify_mindef_custody.py`
   and run the staging CLI with `--install --source-db pla_watch.db
   --public-candidate PRIVATE_CANDIDATE --receipt STAGING_RECEIPT
   --custody-restored-db PRIVATE_RESTORE --custody-restore-receipt RESTORE_RECEIPT`.
   This is the same migration path, not a new ingestion system.
4. Render through `site/render.py`, run `validate_output.py` and
   `audit_mindef_public_surfaces.py --enforce`, review the full generated diff,
   and pass required CI at the final revision. Merge/deploy only as approved.
5. After authorized deployment, bind the main/Pages revisions and compare
   record/4466, all 98 record pages, Singapore/source/archive/search/home/feed
   bytes and held-route absence against the candidate. Check HTTPS content,
   both approved outbound URLs, no unapproved MINDEF links, no source-body
   containers, no stale held pages and no public evidence artifact upload.
   Observe the next ordinary Daily's skip/retry behavior and unchanged other
   desks. These post-release readbacks have not been performed.

The next owner action is review/approval of the bounded cutover after exact-head
CI; broader Singapore collection or model processing needs a distinct source-use
decision and is not activated by this remediation.
