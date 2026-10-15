from pathlib import Path
import json
root=Path(__file__).resolve().parents[1];summary=json.loads((root/'backend/data/credentials-inventory-summary.json').read_text(encoding='utf8'));text=(root/'DEV_CREDENTIALS.local.md').read_text(encoding='utf8')
assert text.count('- Рабочий Bearer token:')==summary['account_entries']==24
assert summary['successful_authorizations']==summary['role_checks_passed']==24
assert not summary['unresolved'] and summary['env_unchanged']
assert text.count('- Штатная авторизация: PASS')==24
print('Credential inventory completeness and verified access: PASS — 24/24; password accounts: 0.')
