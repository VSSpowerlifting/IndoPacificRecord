# Machine explanation specificity — offline review, 26 October 2026

Review base: `origin/main` `71beedb3ba59279948719e5bc091f854d5e3390e`.
This change improves the Philippines prompt; it does not reprocess records or
authorize model spending, release, source use or changes to Briefs.

## Compact rubric

- Identify the actor, action, institution's role and actual status. An
  announcement reports a statement; a proposal seeks action; an instruction
  assigns action; a planned exercise is not an exercise conducted; neither
  proves operational readiness or completed implementation.
- Select useful supported details: activity, participants, place, scope,
  quantity or deadline. Include only what the cited evidence supports.
- Attribute official assertions to their source. Keep publisher, host, issuer,
  speaker, instruction-giver and implementing authority distinct.
- Write natural, independently worded English. Use the available word budget
  for concrete information, avoiding repetitive openings and ceremonial filler.
- Invent no novelty, intent, capability change or strategic importance. Do not
  require a “why it matters” sentence when evidence supports only the event.

## Binding policy and implementation choices

The October 20 AFP and NSC decisions in `DECISION_LOG.md` require attributed,
independently worded machine output, no originals or substantial excerpts, source
evidence and at most **90 combined summary/flag words**. NSC website hosting is
not proof of authorship. Rights, custody, source-version checks and spending
limits remain binding. Editorial doctrine §§2/4/6 separates evidence from
inference and requires concrete, readable prose.

`ph-analysis-v12` added exactly two sentences of 8–11 words, both beginning
“AFP reports” or “NSC reports”, and a 33-word target. Those are implementation
choices, not owner requirements. The 11-word ceiling was a shortcut to avoid
copied 12-word spans; independently written longer sentences can pass that
same overlap check. `v13` removes these length/opening restrictions, retaining
two sentences and the current JSON/fact mapping. It asks for complementary
facts, correct institutional roles and status, with no forced significance.

The actual gate is `processing.daily_intake.quality_check`: 2–3 literal private
evidence spans, exact fact-to-summary coverage, attribution in every sentence,
proper-name/number/modality checks, prohibited copied sentences and 12-word
sequences, topic support, 90 combined words and version provenance. Analyzer
resolves passage IDs against unchanged originals before that gate. Public
`validate_output` separately validates the signed permitted projection.
Both version allowlists now accept `v13`, retaining `v10`–`v12`; no quality check
is relaxed. These deterministic checks cannot establish arbitrary paraphrase
accuracy or correctly infer an institution's role by themselves.

Vietnam's `processing.vpcp_document.output_failures` retains its different
page/evidence/status mapping and **8-word** copying check. Shared Vietnam QA
and its already mandatory independent document review remain unchanged.
October 25's issuer/responsibility correction is already implemented in prompt
`vn-vpcp-document-analysis-v5` and `core.vietnam_corpus_bridge.model_second_pass`.
The additional regressions exercise that path rather than adding another QA
engine. China prompts and all model/flag/schema/retry/spending settings stay as
they were.

## Small source-grounded before/after review

“Before” below means recorded database output or a documented prior rejection.
**Illustrative rewrites are editorial examples, not generated `v13` outputs,
not QA-approved public candidates and not a model evaluation.** All database
reads used `scripts.reconcile_db.read_only`; no original AFP/NSC or Vietnamese
body is added to this repository.

### Philippines: concrete action versus generic importance

`afp:1409` (`v10`) says the Chief of Staff visited Cyber Command to assess
facilities/capabilities, then says the visit “underscored the importance of
strengthening cyber defense”. The second sentence repeats official importance
language while omitting the visitor's name and event date.

Illustrative rewrite: **According to AFP, Chief of Staff General Antonio G.
Nafarrete visited AFP Cyber Command on October 13. AFP says his assessment
covered the command's facilities, operational capabilities and readiness for
cyber challenges.** This reports an assessment, not improved readiness.

Evidence inspected: the [official AFP article](https://www.afp.mil.ph/news/afp-chief-visits-cyber-command-assesses-operational-capabilities),
read through its first-party JSON backend on October 26 with the adapter's
identifiable user agent (robots 404, article 200, identity `1409`). This was a
current source read, not a hash-parity verification against the private capture.

`afp:1410` (`v10`) is a useful accepted comparison: it identifies Philippine
and US forces, a maritime activity in the West Philippine Sea, passing honors
and photography practice. The [official source](https://www.afp.mil.ph/news/afp-us-forces-successfully-conduct-16th-bilateral-maritime-cooperative-activity)
(same access method, identity `1410`, 200) additionally identifies the October
14 event date and participating vessels. This record already has concrete
activity detail; there is no reason to rewrite it or reconsider its flag.

### NSC: preserve the assertion and identify the issuing role

`nsc:3108` (`v12`) says China launched an unarmed ballistic missile from a
submarine, then says the Philippines marks the 2016 award anniversary. The
sentences are disconnected and omit what the statement actually calls for.

Illustrative rewrite: **According to the NSC website, the National Security
Council expressed concern about China's reported submarine missile launch into
the South Pacific. The NSC statement calls for greater transparency and steps
to reduce regional miscalculation.** The launch remains an attributed report;
the call is a statement, not an implemented regional measure.

Evidence inspected: the [July 8 statement](https://nsc.gov.ph/2026/07/08/statement-of-the-national-security-adviser-secretary-eduardo-sl-oban-jr/)
names the National Security Adviser in its heading, identifies the Council in
the statement and gives the concern and transparency call. NSC's website
byline alone would not justify assigning every hosted statement to the Council.
No private-capture parity or independent verification of the launch is claimed.

### China: retain detail, avoid needless expansion of this change

Article **5642**, [PLA Daily night-flight report](http://www.81.cn/bz_208549/16495923.html),
names the Eastern Theater Command naval aviation context, night flying,
reconnaissance/early warning and sea searches. Its preserved Chinese body
supports those details. The recorded summary then adds a long “its value is
as a baseline record” sentence. Article **5640**, the [hydration column](http://www.81.cn/yw_208727/16495983.html),
also has concrete source-supported guidance but ends with similar baseline
commentary. These are readability issues, not evidence that all China outputs
need a new prompt. No China prompt or published text changes here.

Illustrative shorter 5642: **PLA Daily reports that an unnamed Eastern Theater
Command naval aviation unit practiced night flying, reconnaissance, early
warning and sea searches. The report describes reliance on instruments and
ground guidance in low visibility, without identifying the unit, aircraft type
or location.** This uses the preserved original, not a new source retrieval.

### Vietnam: role errors already corrected; retain their regression coverage

The existing [release receipt](VIETNAM_GOVERNMENT_DOCUMENT_RELEASE_2026-10-25.md)
records rejection of `10790/VPCP-CN` for assigning a ministry responsibility to
provincial chairpersons, and the initial `10744/VPCP-CN` issuer/decision-maker
error. Those are recorded failure descriptions, not quotations of the drafts.
The accepted **recorded model output**, article **5646**, distinguishes the
Government Office's transmission, Prime Minister's instructions, ministry
review/coordination and October 25 reporting, and provincial audits/licence
revocations with October 30 reporting. No further rewrite is proposed.

Its original PDF stays private and was not re-inspected in this task. Source
grounding here is limited to the existing hash-pinned release/independent-review
receipt and the permitted public result. Offline English synthetic fixtures
exercise the same issuer-versus-instructor and ministry-versus-province patterns,
including a correctly attributed accepted case. Scripted reviewer verdicts prove
prompt/context routing and hold/pass preservation, not semantic model quality.
No held document or consumed correction/retry route is reopened.

## Verification and remaining live validation

Focused tests cover longer evidence-mapped sentences, varied attribution,
NSC-host/issuer wording, copying and unsupported-completion holds, old-version
acceptance, new-version signing/public validation, and Vietnam role patterns.
The final PR head must also run the repository's mandatory full Actions check
(suite, browser, isolated render, validator and DB/output preservation).

No model call, output regeneration, published-record reprocessing, schedule
change or new evaluation service is part of this change. Future authorized
first-pass results need source-grounded review to establish whether `v13`
improves live quality and whether longer prose increases existing QA holds.
Offline fixtures and illustrative prose cannot settle that question.
