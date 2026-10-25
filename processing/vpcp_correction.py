"""Owner's single manual 10744 correction; never an unattended retry policy."""
import os

DECISION = 'DECISION_LOG.md#2026-10-25--owner-one-manual-10744-attribution-correction'
IDENTITY = 'vpcp-vi:220065'
CONTENT = '842585a4cc35857bf6301e55228c7662d03adc3eeb1bed3a3872cfd3916db56e'
PDF = '121670635f065b0ecb1ef38641c5236d634fc5777dc3aa1cc0330caf7580f575'
METADATA = '4bf6537753bfdbed85f39359a596b4de6ce17eb6a3c7d3aad9ee76d4f2a7d695'
GENERATION_RUN = '40189202615-1'
REJECTED_RUN = '40197695872-1'
MAX_RESERVED = 0.15


def manual_context():
    return (os.environ.get('GITHUB_REPOSITORY') == 'VSSpowerlifting/ipr-source-evidence-private'
            and os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'
            and os.environ.get('MODE') == 'daily-bridge'
            and os.environ.get('GITHUB_RUN_ATTEMPT') == '1')


def eligible(identity, prior, version):
    """Exact rejected source and manual context, before any model dispatch."""
    qa = prior.get('qa') or {}
    second_pass = qa.get('second_pass') if isinstance(qa,dict) else None
    return bool(manual_context() and identity == IDENTITY and version
        and prior.get('content_sha256') == version.get('content_sha256') == CONTENT
        and version.get('pdf_sha256') == PDF and version.get('metadata_sha256') == METADATA
        and all(version.get('identity_checks', {}).get(k) == 'match' for k in ('number','date','issuer'))
        and prior.get('run_id') == REJECTED_RUN and prior.get('outcome') == 'held_review'
        and prior.get('failures') == ['E_SECOND_PASS']
        and isinstance(second_pass,dict) and second_pass.get('ok') is False
        and not prior.get('manual_correction'))


def generate(analyzer, title, body, profile):
    """One shared analysis call; reuse the recorded .65 relevance decision."""
    from config import ANALYSIS_MODEL
    fields = analyzer._desk_analysis_fields(title, body, profile)
    return dict(passed_relevance=True, relevance_score=0.65,
        relevance_reasoning='Reusing the verified source relevance screen from '+GENERATION_RUN+'.',
        requires_translation=False, model_id=ANALYSIS_MODEL,
        prompt_version=profile.prompt_version+'+'+profile.analysis_prompt_version+'+manual-10744-correction-1',
        document_facts=fields.get('facts'), title_english=fields.get('headline'), text_english=None,
        summary_english=fields['summary'], categories=fields['categories'],
        is_significant=fields['flag'], significance_reasoning=fields['flag_reason'])
