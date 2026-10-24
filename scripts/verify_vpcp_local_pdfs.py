"""Read existing private acceptance PDFs; print measurements, never source text."""
import argparse
import hashlib
import json
from pathlib import Path
from core.collection.vietnam_government_documents import INDEX,parse_document
from processing.vpcp_document import inspect_pdf
EXPECTED={'220077':'b4ed9b383d46331baff568eaf30d191d8fae302fb9bb99f3aa9e3f675184e2df',
          '220078':'f37efe49b108798c500389c7ea2dad7715f38f416c68add853ed94fe41b940ea'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    if root==a.directory.resolve() or root in a.directory.resolve().parents:
        raise ValueError('private_pdf_directory_required')
    results=[]
    for ident,sha in EXPECTED.items():
        m=parse_document((root/'tests/fixtures/vietnam_government_documents'/('doc'+ident+'.html')).read_text(),INDEX+'?pageid=27160&docid='+ident)
        data=(a.directory/(ident+'.pdf')).read_bytes();v=inspect_pdf(data,m,expected_sha256=sha)
        results.append({'identity':ident,'pdf_sha256':sha,'content_sha256':v['content_sha256'],
            'pages':len(v['pages']),'identity_checks':v['identity_checks'],'content_labels':v['content_labels']})
    print(json.dumps({'scope':'local cached bytes only; no models or publication','results':results},ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
