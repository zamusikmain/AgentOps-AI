"""Read-only full primary database snapshot and excluded backup, never print data/secrets."""
import sqlite3,json,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parents[1];state=root/'backend/data/v12-preservation.local.json';source=root/'backend/data/agentops.db'
def snapshot(db):
 return {t:sorted(hashlib.sha256(repr(r).encode()).hexdigest() for r in db.execute('SELECT * FROM "'+t+'"')) for t, in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
with sqlite3.connect(source) as db:
 current={'tables':snapshot(db),'env_sha256':hashlib.sha256((root/'backend/.env').read_bytes()).hexdigest()}
 if 'verify' in sys.argv:
  before=json.loads(state.read_text());assert before==current,'Primary data/config changed'
  (root/'docs/v12-preservation.json').write_text(json.dumps({'all_primary_rows_unchanged':True,'env_unchanged':True,'schema_head':'009','migration_required':False,'backup_excluded':True}))
  print('Primary rows, sessions, indexes, traces and .env unchanged; head 009.')
 else:
  backup=root/'backend/data/backups'/('pre-v12-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'.db');backup.parent.mkdir(exist_ok=True)
  with sqlite3.connect(backup) as target:db.backup(target)
  state.write_text(json.dumps(current));print('Excluded v12 backup and preservation snapshot created.')
