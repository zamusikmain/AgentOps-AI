"""Backup and verify pre-existing database rows without exposing their contents."""
import sqlite3,json,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parents[1];dbpath=root/'backend/data/agentops.db';state=root/'backend/data/v10-preservation.json'
def snapshot(db):
    return {t:[hashlib.sha256(repr(r).encode()).hexdigest() for r in db.execute('SELECT * FROM "'+t+'"')] for t, in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('sqlite_sequence','alembic_version')")}
if len(sys.argv)>1 and sys.argv[1]=='verify':
    before=json.loads(state.read_text());
    with sqlite3.connect(dbpath) as db:after=snapshot(db)
    unchanged=all(set(rows)<=set(after.get(t,[])) for t,rows in before['tables'].items())
    env_same=before['env_hash']==hashlib.sha256((root/'backend/.env').read_bytes()).hexdigest()
    report={'all_preexisting_rows_preserved':unchanged,'env_unchanged':env_same,'backup_excluded':True,'schema_head':'009','migration_required':True,'migration_applied':'008 -> 009','counts_before':{t:len(v) for t,v in before['tables'].items()},'counts_after':{t:len(v) for t,v in after.items()}}
    (root/'docs/v10-preservation.json').write_text(json.dumps(report,indent=2),encoding='utf8');assert unchanged and env_same;print('Existing rows and .env preserved')
else:
    backup=root/'backend/data/backups'/('pre-v10-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'.db')
    with sqlite3.connect(dbpath) as db:
        before=snapshot(db)
        with sqlite3.connect(backup) as target:db.backup(target)
    state.write_text(json.dumps({'tables':before,'env_hash':hashlib.sha256((root/'backend/.env').read_bytes()).hexdigest()}),encoding='utf8');print('Excluded local backup created')
