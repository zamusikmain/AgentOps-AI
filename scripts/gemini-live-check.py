"""User-authorized single-generation check through the running FastAPI backend.

The durable marker intentionally prevents rerunning this script or resubmitting
after an ambiguous network outcome. No secrets or raw provider errors are printed.
"""
import hashlib
import json
import sys
import time
from pathlib import Path
import httpx

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
from app.config import Settings
from app.db import Execution, ExecutionEvent, database
from sqlalchemy import select

path = root / 'docs/gemini-live-check.json'
if path.exists():
    print('Single-request marker exists. Refusing another generation request.')
    raise SystemExit(1)
preflight = json.loads((root / 'docs/gemini-model-check.json').read_text(encoding='utf-8'))
if preflight.get('http_status') != 200 or not preflight.get('available'):
    print('Model preflight failed. No generation request made.')
    raise SystemExit(1)
model = preflight['model']
env_path = root / 'backend/.env'
env_before = hashlib.sha256(env_path.read_bytes()).digest()
report = {'model': model, 'model_metadata_http_status': 200, 'run_submission_attempts': 0,
          'project_tier': 'Free Tier, confirmed by user', 'ui_after_reload_verified': False}

def save():
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')

token = (root / 'backend/.local-token').read_text(encoding='utf-8').strip()
with httpx.Client(base_url='http://127.0.0.1:8000',headers={'Authorization': f'Bearer {token}'},timeout=15) as client:
    agent_response = client.post('/api/agents',json={'name':'Gemini Free Tier check', 'role':'executor',
        'instructions':'Return only the requested short confirmation. Do not call tools.',
        'model':model,'tools':[],'max_steps':1,'max_tokens':256,'status':'active'})
    report['agent_create_http_status'] = agent_response.status_code
    if agent_response.status_code != 201:
        save();print(json.dumps(report));raise SystemExit(1)
    agent_id = agent_response.json()['id']
    report['agent_id'] = agent_id
    task_response = client.post('/api/tasks',json={'title':'Gemini API — Free Tier verification',
        'prompt':'Reply with exactly: AgentOps AI Gemini check OK', 'agent_id':agent_id})
    report['task_create_http_status'] = task_response.status_code
    if task_response.status_code != 201:
        save();print(json.dumps(report));raise SystemExit(1)
    task_id = task_response.json()['id']
    report['task_id'] = task_id
    report['run_submission_attempts'] = 1
    save()  # Durable guard BEFORE submission. Never resubmit on timeout.
    response = client.post(f'/api/tasks/{task_id}/run')
    report['run_http_status'] = response.status_code
    if response.status_code != 202:
        report['backend_error'] = response.json().get('error', {}).get('code', 'unknown')
        save();print(json.dumps(report));raise SystemExit(1)
    eid = response.json()['id']
    report['execution_id'] = eid
    save()
    print(json.dumps({'stage':'submitted_once','execution_id':eid}),flush=True)
    for _ in range(190):
        execution = client.get(f'/api/executions/{eid}').json()
        if execution['status'] not in ('queued','running'):
            break
        time.sleep(1)
    events = client.get(f'/api/executions/{eid}/events').json()['items']
    report.update(status=execution['status'],result=execution['result'],error=execution['error'],
                  input_tokens=execution['input_tokens'],output_tokens=execution['output_tokens'],
                  total_tokens=execution['input_tokens']+execution['output_tokens'],duration_ms=execution['duration_ms'],
                  model_request_events=sum(e['kind']=='model_requested' for e in events),
                  events=[{'kind':e['kind'],'payload':e['payload']} for e in events])
    report['provider_http_status'] = next((e['payload']['provider_http_status'] for e in events if 'provider_http_status' in e['payload']), None)
    settings = Settings()
    engine,sessions = database(settings.database_url)
    with sessions() as db:
        stored = db.get(Execution,eid)
        report['sqlite_verified'] = bool(stored and stored.result == execution['result'] and stored.status == execution['status'])
        report['sqlite_event_count'] = len(list(db.scalars(select(ExecutionEvent).where(ExecutionEvent.execution_id==eid))))
    engine.dispose()
    report['env_unchanged'] = hashlib.sha256(env_path.read_bytes()).digest() == env_before
    save()
    print(json.dumps(report,ensure_ascii=False),flush=True)
