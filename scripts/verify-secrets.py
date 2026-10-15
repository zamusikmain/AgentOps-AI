"""Check built browser artifacts without ever printing or copying a secret."""
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from app.config import Settings

key=Settings().gemini_api_key.get_secret_value()
if not key:
    print('Secret check: key is not configured; cannot compare browser bundle.')
    raise SystemExit(1)
static=root/'frontend/.next/static'
files=[p for p in static.rglob('*') if p.is_file()]
if not files:
    print('Secret check: build frontend first.')
    raise SystemExit(1)
found=any(key.encode() in p.read_bytes() for p in files)
print('Browser bundle secret check:', 'FAILED' if found else 'PASS')
raise SystemExit(1 if found else 0)
