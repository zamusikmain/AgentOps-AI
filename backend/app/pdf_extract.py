import json,sys
from pypdf import PdfReader
try:
    reader=PdfReader(sys.argv[1])
    if reader.is_encrypted:raise ValueError('pdf_encrypted')
    if len(reader.pages)>100:raise ValueError('pdf_page_limit')
    pages=[];total=0
    for page in reader.pages:
        text=page.extract_text() or '';total+=len(text)
        if total>500000:raise ValueError('pdf_text_limit')
        pages.append(text)
    if not any(p.strip() for p in pages):raise ValueError('pdf_no_text')
    result={'pages':pages}
except Exception as exc:
    result={'error':str(exc) if str(exc) in ('pdf_encrypted','pdf_page_limit','pdf_text_limit','pdf_no_text') else 'pdf_extraction_failed'}
sys.stdout.buffer.write(json.dumps(result,ensure_ascii=False).encode('utf8'))
