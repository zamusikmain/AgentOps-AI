"""Read-only audit of persisted LangGraph context and raw live model response."""
import sys,json,asyncio,sqlite3,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
marker=root/'docs/v04-live-rag-verification.json'
report=json.loads(marker.read_text(encoding='utf-8'))
async def audit():
    async with AsyncSqliteSaver.from_conn_string(str(root/'backend/data/checkpoints.db')) as saver:
        for entry in report['runs']:
            checkpoint=await saver.aget_tuple({'configurable':{'thread_id':entry['run_id']}})
            values=checkpoint.checkpoint['channel_values'];messages=values.get('messages',[])
            context=json.loads(messages[0]['parts'][0]['text'])
            expected=entry['calls'][0]['result']['matches']
            assert context=={'query':entry['question'],'matches':expected}
            kinds=[e['kind'] for e in entry['events']]
            assert kinds.index('tool_completed')<kinds.index('rag_retrieved')<kinds.index('model_requested')<kinds.index('model_completed')
            retrieved=next(e['payload']['chunks'] for e in entry['events'] if e['kind']=='rag_retrieved')
            assert retrieved==[m['chunk_id'] for m in context['matches']]
            assert next(e['payload']['provider'] for e in entry['events'] if e['kind']=='started')=='gemini'
            entry['context_audit']={'exact_match_with_search_result':True,'forwarded_chunk_ids':[m['chunk_id'] for m in context['matches']],'context_sha256':__import__('hashlib').sha256(json.dumps(context,ensure_ascii=False).encode()).hexdigest(),'malicious_99_hours_forwarded':bool(re.search(r'99\s+часов',json.dumps(context,ensure_ascii=False))),'checkpoint_messages':len(messages)}
            entry['raw_model_response']=values.get('result')
            entry['model_function_calls']=values.get('calls',[])
            with sqlite3.connect('file:'+(root/'backend/data/agentops.db').as_posix()+'?mode=ro',uri=True) as db:
                db.row_factory=sqlite3.Row
                saved=db.execute('select e.*,t.prompt as question from executions e join tasks t on t.id=e.task_id where e.id=?',(entry['run_id'],)).fetchone()
                assert saved['question']==entry['question']
                assert json.loads(saved['snapshot'])['rag_provider']=='gemini'
                for field in ('status','error','result','input_tokens','output_tokens','duration_ms'):assert saved[field]==entry['run'][field]
                event_count=db.execute('select count(*) from execution_events where execution_id=?',(entry['run_id'],)).fetchone()[0]
                call_count=db.execute('select count(*) from tool_calls where run_id=?',(entry['run_id'],)).fetchone()[0]
                assert event_count==len(entry['events']) and call_count==len(entry['calls'])==1
                entry['sqlite_audit']={'question_result_tokens_duration_verified':True,'events':event_count,'tool_calls':call_count}
                assert db.execute('select status from workflow_runs where id=?',('722f6cc4-2ab5-4653-9664-a302cd9582a7',)).fetchone()[0]=='completed'
            if entry['run']['status']=='failed':
                print(json.dumps({'failed_run':entry['run_id'],'raw_model_response':entry['raw_model_response'],'evidence':[m['excerpt'] for m in context['matches']]},ensure_ascii=False))
asyncio.run(audit())
marker.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'audited_runs':len(report['runs']),'all_context_matches':True,'model_requests':report['generation_requests']}))
