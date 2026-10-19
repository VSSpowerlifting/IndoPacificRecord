# Vietnam ministry integration — October 18, 2026

**Classification: Blocked.** The shared-index admission candidate and independent
family recovery are implemented. A real MPS source-window failure, missing
public metadata review/release authority and incomplete protected-custody
cutover prevent an operational claim. No production database or site changed.

## Observed source and publication state

Authenticated GitHub readback, native Git replay and independent SQLite queries
were performed against public main `e21d10e679d6399b398c311fa69c185951bada8b`.
These are current observed branch heads, not assumed October 14 constants:

| Family | Current source commit | Originals | Public admitted links | Latest successful logical date |
| --- | --- | ---: | ---: | --- |
| `vn_mps_foreign_affairs_vi` | `cb607582eda7bd8760663540c33de2f73da411ff` | 11 | 0 | 2026-10-14 |
| `vn_moit_energy_vi` | `5d25d68ee5bd3d1e8e5c7759db880a30d172491a` | 2 | 0 | 2026-10-14 |
| `vn_moit_foundational_industry_vi` | `75035550a2f9db4f7a1cac57925141961b390d60` | 1 | 0 | 2026-10-14 |

All three latest source receipts identify scheduled run
[38642138299, attempt 1](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/38642138299),
collector `6c5a9bce2324e684572e3e808fb0622b99f326c3`. MPS inserted one record;
both MOIT families recorded healthy zero-publication results, each retaining
the independent `robots_content_type` warning. All 14 current original versions
were re-extracted from their SHA-verified captured HTML and matched to stored
content hashes. Every version's first-seen run/attempt and collector SHA were
also checked against GitHub. This is machine evidence, not Vietnamese review.
The prior [October 14 proof run](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/38687940316)
also remains successful.

The next four **scheduled attempts failed**, rather than being missing or quiet:

| Logical date | Actions run / attempt | Observed outcome |
| --- | --- | --- |
| Oct 15 | `38809387069-1` | MPS RSS window unprovable; MOIT not attempted |
| Oct 16 | `38967228796-1` | Same |
| Oct 17 | `39067453204-1` | Same |
| Oct 18 | `39164567807-1` | Same |

All four retained artifacts were inspected. The October 18 captured government
RSS has ten items dated October 15–17, none in the preserved 11-record corpus;
its oldest item is newer than the required October 12 window start. Those
listing entries are **not captured originals**. The collector correctly refuses
coverage, then the old serial batch starves both independent MOIT sources.
Do not interpret MOIT's lack of an attempt as current publisher health.
Direct web readback of the ministry listing later timed out; no access challenge
was bypassed and no additional source endpoint was collected.

October 18 listing payload SHA-256:
`088d3925d442437a27ecc6c8c61d63e8ec14ebe553f2f46da24d8cf8b5ca2d0a`.
Retained artifact `12150192474` has provider ZIP digest
`a4cebc16d7bee7f3f3b09489a36f7bdb5560424215ca0a7ed8f895c6ef149bfc`.
The extracted listing bytes were independently hashed; this is not a claim
that an independent backup of the complete ZIP was restored.

Bootstrap `37656171920-1` remains failed and `37656171920-2` remains successful.
Scheduled logical October 12 completed October 13 UTC; it is not a missing day.

## Implemented boundary

- The existing 18:17 UTC workflow, six-day lookback, 40-record cap and shared
  MOIT host gate remain. A publisher failure no longer prevents sibling attempts.
  Only independently validated successful families enter the state-push list;
  integrity corruption stops the batch. Any failure still fails the Actions run.
  Complete attempt artifacts and 90-day retention remain, with the small success
  list also preserved. No second collector or schedule was activated.
- The attestor uses the actual renamed repository rather than rejecting GitHub's
  legacy-name redirect. It binds the ledger collector SHA to Actions. A healthy
  source in a failed sibling batch additionally requires authenticated successful
  preservation and publication steps; it never relabels the batch successful.
- `prepare_vietnam_official_links.py` builds held metadata from immutable source
  Git, replays captured HTML and retains independent Vietnamese publication date,
  RSS instant, original-version/capture hashes and attempt identities. It exports
  no original titles, bodies, images, translations or model text.
- MPS admission additionally requires the existing regional HMAC review envelope
  with a distinct public-link purpose, exact candidate digest, individual selected
  identities, named review, source-use basis/reference, custody attestation and
  explicit production release. A private-model seal is not a public release.
  No genuine public-link decision or publication key was invented or provisioned.
- Admission reuses the existing regional SQLite transaction, duplicate/legacy-URL
  protections and index. Migration 0013 preserves existing rows and adds only the
  three Vietnam family constraints. It inserts nothing. Replayed unchanged
  identities are no-ops; original-version changes fail closed.
- Both MOIT families retain unconditional separate admission/render holds.
  Their schema capacity is present; actual permission and anomaly disposition
  must precede a reviewed change to those holds.
- The production renderer can show **actually admitted** Vietnam rows through
  the same regional rail and independent readback as other regional desks.
  No registry promotion, corpus/source count inflation or generated output change
  is included. The CLI permits only external scratch admission; it does not
  activate a production publisher or an unattended private-to-public bridge.

Reproduce the real MPS held candidate without government requests:

```sh
.venv/bin/python scripts/prepare_vietnam_official_links.py \
  --source vn_mps_foreign_affairs_vi \
  --state-repo /absolute/external/clone-of-shadow-vietnam-mps-foreign-affairs \
  --state-commit cb607582eda7bd8760663540c33de2f73da411ff \
  --out /absolute/external/new-held-candidates.json
```

Candidate digest: `93224b092f9a4e2eaa12247e224a4c3c06f2ae559b21a1185e398d749136201a`.
For example, `mps-vi:1791971146`, publisher date October 14, has content hash
`bd9cf870ce1e95e8b0e55f37f1ef070c8d8446776838d0b8f0c4fee21e7b07df`
and original HTML capture
`6e684e939bd29fccfd43eb01ff037fa7faa70a807949a172408ae4378949ae93`.
No synthetic approval was applied to this real record.

## Research, custody and actual public readback

Brief #18, *What Is Being Built in Laos?*, is **already** featured by the current
renderer and [live Vietnam page](https://indopacificrecord.org/vietnam.html).
The [published Brief](https://indopacificrecord.org/briefs/what-is-being-built-in-laos.html)
was independently read. Closed PR #651 is superseded by current public-editorial
catalog integration; no manuscript or duplicate feature was necessary.

The current preserved MPS queue joined successfully with the two authorized
October 11–17 synopsis notes through the existing editorial feeder. The real
source hashes in PR #597 remain unchanged. No new model call, translation,
email or editorial publication occurred. Private research, model use, Dylan
distribution and public editorial approval remain distinct permissions.

Authenticated private-repository readback confirms all three `archive/vietnam-*`
heads equal the public source heads above. This is native-history mirroring,
not private-first custody or erasure of public exposure. Private PRs #2 and #3
record native-ref and opaque ZIP inventories; their stated exclusions and private
issue #1 leave independent off-GitHub backup/restore and release/cutover unresolved.
No private repository, public history, artifact or retention setting was changed.

At readback, `main:output/vietnam.html` and `gh-pages:vietnam.html` both had Git
blob `9a7e08714d821494503e6f16be261cdb1ae80a59`. Live HTTPS showed Brief #18 and
no individually admitted ministry references. Read-only SQLite confirmed zero
Vietnam corpus and official-link rows. Thus the real chain currently stops
**before authorized SQLite admission**; there is no new production commit,
Pages release or HTTPS record from this work.

## Verification and remaining owner actions

Focused source/admission/readback tests, existing private editorial boundary
tests, real 14-original replay, authenticated provider readback, production-mode
private rendering and 1280/375 Chromium checks were run. Preview preserves Brief
#18, contains zero unapproved rows and has no horizontal overflow. Tracked DB
and output remain unchanged; the output validator passes with 10 governed
warnings. Full-suite/PR results are recorded in the implementation PR.

The next action is owner review of this one implementation PR and these exact
blocked source treatments:

1. **MPS access/coverage:** approve a published official discovery route capable
   of establishing the six-day boundary, or explicitly amend the collection scope.
   Do not dispatch the same unprovable historical window or silently reduce it.
   The October 15–18 gap must remain disclosed until genuine recovery is possible.
2. **MPS public metadata/custody:** named Vietnamese source/version review and
   owner authorization selecting exact candidate identities for identity, official
   URL, publisher date and ministry attribution only. Separately establish the
   scoped protected-custody/restore decision before private-first cutover and
   credential configuration. Bodies, headlines, media, translations, model use
   and email are excluded. Only after that decision should the existing serialized
   publisher be connected, merged/released under explicit authority, and checked
   through production SQLite → generated HTML → committed output → Pages → HTTPS.
3. **MOIT, separately per family:** resolve the written-consent requirement in
   issue #196 and the robots MIME anomaly, including whether the intended neutral
   link treatment is permissible. No external-model transmission or public
   original/metadata release is inferred from collection success.

No calendar streak is a launch prerequisite. The actual source and permission
failures above are the blockers; the three-family contract is not complete.
