# Korea MND — 28 October 2026 listing/detail heading whitespace drift

## Authenticated observation

Private Actions attempt `40775675544-1` on `archive/korea-policy-briefing` was a scheduled, authenticated source collection. It retrieved the ministry-filtered listing and ten official detail responses with HTTP 200. Five detail headers differed from the matched listing headers by **one repeated ASCII space**, while the release identity, Korean words, issuer, and publisher dates matched. The five affected IDs were `156786944`, `156786943`, `156786942`, `156786938`, and `156786935`.

The extractor held those five records with `release metadata disagrees with listing`. The complete batch failed closed: 5 documents extracted, 5 extraction failures, zero insertions or updates. The private attempt ledger and associated captures were committed, independently read back, and left intact. Neither a successful HTTP status nor matching text alone confers new publication rights.

## Minimal comparison correction

In `KoreaPolicyAdapter.fetch`, fold only consecutive ASCII spaces (`r" {2,}"`) in the **two compared titles**. The actual publisher-supplied detail title is not rewritten. Canonical URL, official issuer, full non-space title characters, publication date, sole valid HWPX attachment, original text extraction, source-capture custody, all-or-nothing batch rule, and existing source-use permissions are unchanged.

Regression `tests/test_korea_mnd_title_spacing_parity.py` replays existing public synthetic/approved fixtures without network calls. Duplicate-space detail headings pass; modified substantive headings or dates fail before attachment retrieval.

## Follow-up acceptance

A passing offline PR does not prove live recovery. After reviewed merge, inspect the next **normal authorized scheduled** MND cycle and the matching private ledger. Verify that every listing/detail mismatch is either accurately resolved or held, no record is fabricated or silently skipped, original provenance is unchanged, and only independently permitted publications can advance. Do not automatically replay this failed attempt, fetch new source material on demand, or release any held analysis because of this comparison fix.
