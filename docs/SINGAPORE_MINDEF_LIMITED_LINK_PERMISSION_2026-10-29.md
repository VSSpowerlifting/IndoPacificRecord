# Singapore MINDEF: narrowly scoped hyperlink permission (29 October 2026)

## Evidence and scope

- **Request sent:** 26 October 2026, from IPR's founder, concerning two official releases and hyperlinking for a human-authored analytical Brief.
- **Permission received:** 29 October 2026 from Singapore MINDEF Public and Digital Communications Directorate, Media Relations.
- **Permission granted:** the *limited linking request* to these exact URLs:
  - https://www.mindef.gov.sg/news-and-events/latest-releases/23oct26-nr2/
  - https://www.mindef.gov.sg/news-and-events/latest-releases/31may25_nr3/
- **Private evidence custody:** correspondence retained in the publisher-contact Gmail account under label `IPR/Source Permissions`. Do **not** copy the email, contacts, personal data, signature or attachments into this public repository.

The original request explicitly stated that the Brief uses independent commentary and factual paraphrase, **not** MINDEF photographs or article text, and does not imply MINDEF endorsement. The reply agreed to the limited linking request. It **does not** authorize reproduction of full text, images, long excerpts, other URLs, dataset distribution, model processing or expansion of unattended collection. MINDEF [Terms of Use](https://www.mindef.gov.sg/terms-of-use/) §§5–6 continue to apply.

## Implemented cutover candidate

PR #913 has been extended beyond its original local staging safeguard. The
reviewed permission scope above is unchanged. The refreshed main baseline has 102
records, 101 captured bodies and 80 populated summaries; the production snapshot,
current source-shadow history and all 70 retained Singapore Actions ZIPs now
have private GitHub custody and independent readback/restore proof.

The candidate rebuilds the public SQLite file, retains identity/provenance and
hash bindings, blocks restricted writes, holds public acquisition/model
processing, regenerates shared reader surfaces and withholds affected human
works without altering their signed manuscripts. Record-page withholding alone
was insufficient; the full candidate and exact release procedure are documented
in [the production cutover receipt](engineering/SINGAPORE_MINDEF_PRODUCTION_CUTOVER_2026-10-29.md).

Current-tree audit success does not clear historical Git/Pages/artifact exposure,
canonical editorial source files or replay fixtures. No merge, live publication,
new source-use right, spending, history rewriting, evidence deletion or Brief
No. 20 editorial update is authorized. Issue #914 remains separately human-reviewed.
