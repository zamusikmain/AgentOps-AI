"""Read-only restart guard for the native main app's known SQLite namespaces."""
import sqlite3,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];data=root/'backend/data'
paths=[data/'agentops.db',*list((data/'ai-workspaces-v11').rglob('offline.db')),*list((data/'ai-workspaces-v11').rglob('google.db')),*list((data/'live-smoke').rglob('benchmark.db'))]
active=0
for path in paths:
    if not path.exists():continue
    assert path.resolve().is_relative_to(data.resolve())
    with sqlite3.connect('file:'+path.resolve().as_posix()+'?mode=ro',uri=True,timeout=3) as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ('executions','workflow_runs','evaluation_runs','validation_runs','llm_executions'):
            if table in tables:active+=db.execute(f'SELECT count(*) FROM {table} WHERE status IN (\'queued\',\'running\')').fetchone()[0]
        if 'knowledge_documents' in tables:active+=db.execute("SELECT count(*) FROM knowledge_documents WHERE status='indexing' OR embedding_status='indexing'").fetchone()[0]
        if 'llm_configurations' in tables:active+=db.execute("SELECT count(*) FROM llm_configurations WHERE kind='workspace_smoke' AND json_extract(body,'$.status') IN ('queued','running')").fetchone()[0]
print(json.dumps({'active_native_operations':active,'safe_to_restart':active==0,'databases_checked':sum(p.exists() for p in paths)}))
raise SystemExit(0 if active==0 else 2)
