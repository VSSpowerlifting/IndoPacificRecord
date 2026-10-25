"""Local PDF fidelity checks. No network, model, OCR service or public writes."""
from __future__ import annotations
import hashlib
import io
import re
import unicodedata
from datetime import date
from pypdf import PdfReader, PageObject
from pypdf.generic import NameObject
from core.collection.vietnam_government_documents import FAMILY, ISSUER, digest, identity
from core.collection.vietnam_sources import content_sha256
from processing.pdf_text import extract_pdf_text

HASH_RULE = 'vpcp-pdf-pages-v1'
MAX_BYTES, MAX_PAGES = 5_000_000, 40


def normalized(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', text).translate(
        str.maketrans({'–':'-', '—':'-', '‑':'-', '\u00ad':''}))).casefold()


def identity_header(reader, metadata):
    """Check printed fields; support numeric widget appearances in header slots.

    Do not use /V, the filename, a signature's timestamp, or expected metadata
    to supply missing values. Read the actual normal appearance stream, which
    the renderer paints. Unknown/multiple/hidden appearances hold the document.
    Coordinates are deliberately limited to the observed A4 header layout.
    """
    page = reader.pages[0]
    first = unicodedata.normalize('NFC', page.extract_text() or '')[:1100]
    number = re.search(r'Số\s*:\s*([^\n]+)', first)
    stamp = re.search(r'ngày\s*(\d*)\s*tháng\s*(\d*)\s*năm\s*(\d*)', first, re.I)
    if not number or not stamp or normalized(ISSUER) not in normalized(first[:400]):
        raise ValueError('document_header_missing')
    value = number.group(1).strip()
    fields = list(stamp.groups())
    basis = 'page_text'
    slots = {'number':[], 'day':[], 'month':[], 'year':[]}
    width, height = float(page.mediabox.width), float(page.mediabox.height)
    for ref in page.get('/Annots', []):
        a = ref.get_object()
        rect = a.get('/Rect', [])
        if len(rect) != 4 or a.get('/Subtype') != '/Widget':
            continue
        x, y, right, top = map(float, rect)
        # Do not use the portal operator's signature block above the header.
        if not (0.84*height <= y <= 0.90*height and top-y < 25):
            continue
        slot = ('number' if 0.17*width < x < 0.37*width else
                'day' if 0.64*width < x < 0.74*width else
                'month' if 0.74*width <= x < 0.82*width else
                'year' if 0.82*width <= x < 0.94*width else None)
        if slot is None:
            continue
        if int(a.get('/F',0)) & (1|2|32):
            raise ValueError('document_hidden_header_appearance')
        appearance = (a.get('/AP') or {}).get('/N')
        if appearance is None or not hasattr(appearance.get_object(), 'get_data'):
            raise ValueError('document_header_appearance_missing')
        form = appearance.get_object()
        fake = PageObject.create_blank_page(width=width, height=height)
        fake[NameObject('/Contents')] = form
        fake[NameObject('/Resources')] = form.get('/Resources', page['/Resources'])
        token = (fake.extract_text() or '').strip()
        if not re.fullmatch(r'\d{1,4}', token):
            raise ValueError('document_header_appearance_unsupported')
        slots[slot].append(token)
    if any(len(v)>1 for v in slots.values()):
        raise ValueError('document_header_appearance_ambiguous')
    for k, existing in [('number',re.match(r'\d+',value)), *zip(('day','month','year'),fields)]:
        token = slots[k][0] if slots[k] else None
        shown = existing.group() if hasattr(existing,'group') else existing
        if token and shown and int(token)!=int(shown):
            raise ValueError('document_header_appearance_conflict')
    if not re.match(r'\d',value):
        if not slots['number']:
            raise ValueError('document_number_missing')
        value = slots['number'][0] + value
        basis = 'page_text_and_widget_appearances'
    if normalized(value) != normalized(metadata['document_number']):
        raise ValueError('document_number_conflict')
    for i,key in enumerate(('day','month','year')):
        if not fields[i]:
            if not slots[key]:
                raise ValueError('document_date_missing')
            fields[i] = slots[key][0]
            basis = 'page_text_and_widget_appearances'
    if date(int(fields[2]),int(fields[1]),int(fields[0])).isoformat()!=metadata['issue_date']:
        raise ValueError('document_date_conflict')
    return {'number':'match','date':'match','issuer':'match','basis':basis}


def _inspect_pdf(data, metadata, *, expected_sha256=None):
    from processing.government_document_intake import validate
    validate(metadata)
    if metadata['document_type'] not in ('Công văn','Thông báo'):
        raise ValueError('document_class_individual_review_required')
    if not isinstance(data, bytes) or len(data)>MAX_BYTES or not data.startswith(b'%PDF-'):
        raise ValueError('document_bytes_invalid')
    sha=hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None and sha!=expected_sha256:
        raise ValueError('document_pdf_hash_conflict')
    reader=PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise ValueError('document_encrypted')
    extracted=extract_pdf_text(data,max_bytes=MAX_BYTES,max_pages=MAX_PAGES)
    if not extracted.ok or extracted.pages_failed or extracted.pages_with_text!=extracted.page_count:
        raise ValueError('document_page_coverage_failed')
    if [n for n,_ in extracted.pages]!=list(range(1,extracted.page_count+1)):
        raise ValueError('document_pages_lost')
    if any(len(re.findall(r'\w',text))<120 for _,text in extracted.pages):
        raise ValueError('document_page_text_too_sparse')
    if normalized(metadata['signatory']) not in normalized(extracted.text):
        raise ValueError('document_signatory_missing')
    # Multiple attachments or embedded/annex material need individual review.
    if len(metadata['attachments'])!=1 or reader.attachments or re.search(
            r'\b(?:PHỤ LỤC|BẢN QUYỀN|CONFIDENTIAL|TỐI MẬT|TUYỆT MẬT)\b',extracted.text,re.I):
        raise ValueError('document_attachment_or_restriction_review')
    header=identity_header(reader,metadata)
    blocks=[['page-%d'%n,t] for n,t in extracted.pages]
    lead=digest(metadata)+':'+sha
    content=content_sha256(HASH_RULE,metadata['subject'],lead,blocks)
    from processing.government_document_intake import topics
    # Same bounded topic vocabulary, now applied to document contents, not title.
    labels=topics({'subject':extracted.text})
    version={'title_original':metadata['subject'],'text_original':extracted.text,
        'lead_original':lead,'blocks_json':__import__('json').dumps(blocks,ensure_ascii=False),
        'content_hash_rule':HASH_RULE,'content_sha256':content,'body_status':'text',
        'pages':list(extracted.pages),'identity_checks':header,'content_labels':labels,
        'pdf_sha256':sha,'metadata_sha256':digest(metadata),
        'bibliographic':{k:metadata[k] for k in ('document_number','document_type','issuer','signatory','issue_date','official_url')}}
    return version


def output_failures(version,reading):
    """Page-pinned private support; conservative errors hold the entire output."""
    facts=reading.get('document_facts');summary=reading.get('summary_english','')
    if not isinstance(facts,list) or not 2<=len(facts)<=3 or reading.get('is_significant') is not False:
        return ['document_facts_missing']
    if any(not isinstance(f,dict) for f in facts):return ['document_facts_invalid']
    if len({f.get('sentence') for f in facts})!=len(facts):return ['document_duplicate_facts']
    if not isinstance(summary,str) or not summary.strip() or len(summary.split())>90:
        return ['document_summary_coverage']
    # Private evidence notes need not duplicate the shorter public paragraph.
    # Semantic coverage is checked by the mandatory independent factual review.
    if set(re.findall(r'\d+',summary))-set(re.findall(r'\d+',' '.join(str(f.get('evidence','')) for f in facts))):
        return ['document_numeric_evidence_mismatch']
    pages=dict(version['pages'])
    for fact in facts:
        if (set(fact)!={'sentence','page','evidence','status'} or type(fact['page']) is not int
            or fact['page'] not in pages or not isinstance(fact['evidence'],str)
            or not 20<=len(fact['evidence'])<=600 or fact['evidence'] not in pages[fact['page']]
            or fact['status'] not in ('instructed','proposed','conditional','reported','established')):
            return ['document_page_evidence_invalid']
        sentence=fact['sentence']
        if not isinstance(sentence,str) or not re.search(r'Government Office',sentence):
            return ['document_attribution_missing']
        # Private notes may add context from their cited page beyond the short
        # literal span. Public-summary numbers remain bound to cited spans above.
        if set(re.findall(r'\d+',sentence))-set(re.findall(r'\d+',pages[fact['page']])):
            return ['document_numeric_evidence_mismatch']
        if fact['status']=='proposed' and not re.search(r'propos|consider|draft',sentence,re.I):
            return ['document_modality_mismatch']
        if fact['status']=='conditional' and not re.search(r'\bif\b|subject to|conditional|would',sentence,re.I):
            return ['document_modality_mismatch']
        if fact['status']=='instructed' and not re.search(r'asked|instruct|direct|request|requir|calls for|task',sentence,re.I):
            return ['document_modality_mismatch']
        if fact['status'] in ('instructed','proposed','conditional') and re.search(
                r'\b(completed|implemented|commissioned|funded|operational)\b',sentence,re.I):
            return ['document_implementation_claim']
        # Never publish a long source passage, including across sentence boundaries.
    words=summary.casefold().split();original=version['text_original'].casefold()
    if any(' '.join(words[i:i+8]) in original for i in range(max(0,len(words)-7))):
        return ['document_source_reproduction']
    return []


def inspect_pdf(data, metadata, *, expected_sha256=None):
    try:
        return _inspect_pdf(data,metadata,expected_sha256=expected_sha256)
    except ValueError:
        raise
    except Exception:
        raise ValueError('document_parser_failed') from None


def retained_format_draft(item,version):
    """Complete an unexecuted QA stage; never regenerate a paid draft."""
    from config import ANALYSIS_MODEL,RELEVANCE_THRESHOLD
    review=item.get('private_document_review') or {}
    saved=review.get('reading')
    if (item.get('outcome')!='held_review' or review.get('failures')!=['document_summary_coverage']
        or not isinstance(saved,dict) or saved.get('model_id')!=ANALYSIS_MODEL
        or not isinstance(saved.get('prompt_version'),str)
        or type(saved.get('relevance_score')) not in (int,float)
        or not RELEVANCE_THRESHOLD<=saved['relevance_score']<=1):
        return None
    result=dict(saved)
    # Old receipts omitted classification fields. This one narrow fallback is
    # deterministic from verified administrative-letter metadata, not a model claim.
    if 'categories' not in result:
        if version.get('bibliographic',{}).get('document_type')!='Công văn':return None
        result['categories']=['policy_document']
    result.update(passed_relevance=True,requires_translation=False,is_significant=False,
        significance_reasoning=None,text_english=None)
    result.setdefault('relevance_reasoning','The retained source-specific relevance screen scored this verified Government Office administrative communication %.2f.'%saved['relevance_score'])
    return result if not output_failures(version,result) else None
