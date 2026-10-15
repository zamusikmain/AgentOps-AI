"""Online backup, additive migration, exact preservation of all pre-existing rows."""
import sqlite3,json,hashlib,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parents[1];path=root/'backend/data/agentops.db'
def snapshot(db,tables,columns):
    out={}
    for t in tables:
        rows=db.execute('select '+','.join('"'+c+'"' for c in columns[t])+' from "'+t+'"').fetchall()
        data=sorted((repr(r) for r in rows))
        out[t]={'count':len(rows),'sha256':hashlib.sha256('\n'.join(data).encode()).hexdigest()}
    return out
with sqlite3.connect(path) as db:
    tables=[r[0] for r in db.execute("select name from sqlite_master where type='table' and name not in ('alembic_version','sqlite_sequence')")]
    columns={t:[r[1] for r in db.execute('pragma table_info("'+t+'")')] for t in tables}
    assert sum(db.execute('select count(*) from '+t+" where status in ('queued','running')").fetchone()[0] for t in ('executions','workflow_runs'))==0,'Active runs; stopped'
    before=snapshot(db,tables,columns)
    backup=root/'backend/data/backups'/('pre-v06-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'.db');backup.parent.mkdir(exist_ok=True)
    with sqlite3.connect(backup) as dest:db.backup(dest)
subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root/'backend',check=True)
with sqlite3.connect(path) as db:
    after=snapshot(db,tables,columns);assert before==after,'Pre-existing data changed'
    report={'migration':db.execute('select version_num from alembic_version').fetchone()[0],'backup':str(backup),'all_existing_rows_preserved':True,'tables':after}
(root/'docs/v06-migration.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('Migration',report['migration'],'all existing rows preserved; backup excluded by backend/data and *.db.')
