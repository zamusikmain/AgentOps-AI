"""Back up local SQLite before additive migration; preserve existing run data."""
import sqlite3,json,hashlib,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parents[1];path=root/'backend/data/agentops.db'
db=sqlite3.connect(path)
tables=['agents','tasks','executions','execution_events','workflows','workflow_runs','workflow_steps','workflow_events','tool_calls']
before={t:db.execute('select count(*) from '+t).fetchone()[0] for t in tables}
assert sum(db.execute('select count(*) from '+t+" where status in ('queued','running')").fetchone()[0] for t in ('executions','workflow_runs'))==0,'Active runs; migration stopped'
live='722f6cc4-2ab5-4653-9664-a302cd9582a7'
live_before=db.execute('select status,result,input_tokens,output_tokens from workflow_runs where id=?',(live,)).fetchone()
backup=root/'backend/data/backups'/('pre-rag-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'.db');backup.parent.mkdir(exist_ok=True)
with sqlite3.connect(backup) as destination:db.backup(destination)
db.close()
subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=root/'backend',check=True)
with sqlite3.connect(path) as db:
    after={t:db.execute('select count(*) from '+t).fetchone()[0] for t in tables};assert before==after
    assert live_before==db.execute('select status,result,input_tokens,output_tokens from workflow_runs where id=?',(live,)).fetchone()
    report={'migration':db.execute('select version_num from alembic_version').fetchone()[0],'backup':str(backup),'preserved_counts':after,'previous_live_run_preserved':bool(live_before)}
(root/'docs/rag-migration.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
