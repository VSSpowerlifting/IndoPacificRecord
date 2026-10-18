# Korea DAPA — October 15 owner-captured original to signed metadata (2026-10-18)

**Scope:** one already captured, original-source verified DAPA article, `korea-dapa-policy:156785254`, dated 2026-10-15. This is a production integration, not a substitute for ongoing DAPA source automation. No new Korean government access is needed. Source originality, permissions, private custody and all publication gates remain explicit.

## Verified original custody

The owner completed offline document replay against IPR source code commit `7a1367102c3cc00d61282350130fb85940c54221`, then uploaded the exact original source inventory into the restricted `VSSpowerlifting/ipr-source-evidence-private` archive branch. Independent private clone/readback verified commit `5791fc9594d5f44184bd07c5b2353ee941a4b937` with exactly six introduced files: three robots/listing/article HTTP capture responses, original HWPX, unchanged failed original ledger, and private manifest. The HWPX SHA-256 is `dc832374f7709dfc14a08baf4fad526bf8b519114f0cebdca9793a49a64dd8a8`; the existing failed ledger SHA-256 is `4a7b3ad9b814a50b6b5ac1d378a717adf830420b5c876fdabf6830e136b70c99`.

The original October 17 owner attempt remains an **extraction_failure / health=fail**. Offline replay proved the preserved source can now be parsed correctly. It does **not** retroactively create a successful unattended collection run.

## One coherent import path

1. Merge the exact-head public historical bridge change after its offline CI and negative controls. Normal automatic DAPA packets (future capture dates `>= 2026-10-16`) retain their original checks. The sole historical packet uses a distinct `ipr-korea-dapa-signed-owner-historical-metadata/1` schema; exact article ID/date, original hashes, failed-ledger hash, original private source commit, independently committed source DB digest and independent review receipt are all bound to the HMAC.
2. Merge the corresponding private-vault historical handoff workflow. Its **prepare_private_db** manual operation (one time) reopens the existing private captures, checks the real DAPA HTML and HWPX using the production parser, creates only `state/historical_owner_imports/dapa-2026-10-15-156785254/historical_source.db`, pushes exactly that file to the private source archive, and independently clones and checks the new Git commit/SQLite. This step **does not approve any rights or publish**.
3. For this **official-link-only** release, independently review the issuing institution, publication date, exact government URL and permission to publish neutral link metadata. Do **not** add HWPX reading-order or full Korean-text semantic approval as a prerequisite to publishing only a link; those reviews are required separately before any English translation, text quotation or analysis. A separately authenticated human decision is necessary. Record a **real**, independently approved *official-link metadata only* decision at `state/historical_owner_imports/dapa-2026-10-15-156785254/review_official_link.json`, schema:
   ```json
   {
     "schema": "ipr-dapa-historical-official-link-review/1",
     "source_identity": "korea-dapa-policy:156785254",
     "source_commit": "5791fc9594d5f44184bd07c5b2353ee941a4b937",
     "reviewer": "<actual reviewer name or authenticated ID>",
     "issuer_and_date_verified": true,
     "official_link_metadata_rights_approved": true,
     "metadata_only_release_approved": true,
     "original_text_media_reuse_approved": false,
     "translation_analysis_reuse_approved": false
   }
   ```
   **Template only:** do not commit filled `true` values until that review genuinely happened. Preserve the original manifest with its historical review flags `false`. Do not put original Korean text, document bytes, model prompts or private credentials in a public PR.
4. Only after the real private readback and human decision, configure the same `DAPA_BRIDGE_KEY` (minimum 32 characters) separately in public and private GitHub Actions secrets, plus a narrowly scoped `IPR_PUBLIC_BRIDGE_TOKEN` (Actions workflow-dispatch permission on **public** IPR only) as a **private** secret. Deliberately enable `DAPA_METADATA_BRIDGE_ENABLED=true` in *both* repos. Never post secret values in issues, PRs, Actions logs or chat.
5. Owner-dispatch **dispatch_reviewed_metadata** in the private historical handoff workflow with explicit confirmation. It authenticates the exact Git checkout, unchanged original captures/ledger, real private SQLite and review, replays the actual Korean article/HWPX locally, then emits **one HMAC-signed sanitized metadata packet** to the **existing** Korea verified-official-links publisher. A GitHub 204 dispatch acknowledgment is not publication proof; separately inspect the destination Actions run.
6. Check in order: same DAPA source identity and canonical government URL in committed `main:pla_watch.db`; correct `output/korea.html` and `gh-pages:korea.html` bytes; exact live HTTPS link and separation of 5 original plus 9 fixed MND bibliography links. Verify production history did not overwrite unrelated desk data or publish original Korean title/text/HWPX/media/translation/analysis. Check a retry yields zero duplicate source rows. Return **HOLD**, not success, on any source drift, review disagreement, failed workflow, race guard or Pages discrepancy.

## Operational desk completion continues

This historical record proves an actual older source can move through a governed metadata-only admission after its review; it does **not** prove a later DAPA *new* government release reaches production automatically. Bring ordinary DAPA private collection and verified link-only dispatch into a separately approved daily schedule with genuine failure alerts and retry, while also addressing the demonstrated MND robots/listing transport timeouts. Establish source-grounded bilingual editorial drafting/review for both sources; never count metadata links as original analysis. Seven-/30-day operational histories are **measurements**, not fixed launch wait periods. Do not call the full Korea Desk complete until the agreed collection, editorial, publication and recovery workflow is actually operating.

### Offline checks

```bash
python -m unittest tests.test_korea_dapa_historical_owner tests.test_korea_dapa_private_to_production -v
python -m py_compile core/korea_dapa_historical_owner.py scripts/stage_korea_dapa_historical_source_db.py
```

No archive originals or secret material may be committed into the public source repository.
