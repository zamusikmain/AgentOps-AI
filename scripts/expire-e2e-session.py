"""Test-only TTL fixture, restricted to the active isolated Playwright database."""
import json,sqlite3,sys,time,re
from pathlib import Path
root=Path(__file__).resolve().parents[1];db=Path(json.loads((root/'backend/data/auth-e2e-runtime.local.json').read_text())['database']).resolve();allowed=(root/'backend/.pytest-work').resolve()
assert db.is_relative_to(allowed) and db.parent.name.startswith('e2e-') and db.name=='test.db' and db.exists()
identifier=sys.argv[1];assert re.fullmatch(r'[0-9a-f-]{36}',identifier)
with sqlite3.connect(db) as connection:
 count=connection.execute('UPDATE user_sessions SET expires_at=? WHERE id=?',(time.time()-1,identifier)).rowcount;assert count==1
print('Isolated E2E session TTL expired; no production data touched.')
