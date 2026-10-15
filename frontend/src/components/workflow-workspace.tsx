'use client';
import {useCallback,useEffect,useRef,useState,type FormEvent} from 'react';
import {Plus,X,ArrowUp,ArrowDown,CirclePlay,GitBranch} from 'lucide-react';
import {api,type Agent,type Page,type Provider,type Event} from '@/lib/types';
import {translate} from '@/lib/i18n';
import type {Workflow,WorkflowForm,WorkflowRun,WorkflowStep,WorkflowNode} from '@/lib/workflows';
import {ToolHistory} from './tool-history';
import {WorkflowGraph} from './workflow-graph';

const fresh:WorkflowForm={name:'',agent_ids:['','','',''],retry_from:2,max_revisions:1,max_calls:12,max_total_tokens:32768,timeout_seconds:180,status:'active'};
export function WorkflowWorkspace({locale,provider}:{locale:'ru'|'en';provider:Provider|null}){
  const t=(key:string)=>translate(locale,key);
  const [agents,setAgents]=useState<Agent[]>([]);
  const [workflows,setWorkflows]=useState<Workflow[]>([]);
  const [runs,setRuns]=useState<WorkflowRun[]>([]);
  const [total,setTotal]=useState(0);
  const [workflowTotal,setWorkflowTotal]=useState(0);
  const [workflowOffset,setWorkflowOffset]=useState(0);
  const [offset,setOffset]=useState(0);
  const [filter,setFilter]=useState('');
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [editing,setEditing]=useState<Workflow|null>(null);
  const [form,setForm]=useState<WorkflowForm>(fresh);
  const [composer,setComposer]=useState(false);
  const [target,setTarget]=useState<Workflow|null>(null);
  const [task,setTask]=useState({title:'',prompt:''});
  const [selected,setSelected]=useState<WorkflowRun|null>(null);
  const [steps,setSteps]=useState<WorkflowStep[]>([]);
  const [events,setEvents]=useState<Event[]>([]);
  const createDialog=useRef<HTMLDialogElement>(null);
  const taskDialog=useRef<HTMLDialogElement>(null);
  const detailDialog=useRef<HTMLDialogElement>(null);
  const requestVersion=useRef(0);
  const selectedId=selected?.id;
  const load=useCallback(async(quiet=false)=>{
    const version=++requestVersion.current;
    if(!quiet)setLoading(true);
    try{
      const [w,r,a]=await Promise.all([api<Page<Workflow>>(`workflows?offset=${workflowOffset}`),api<Page<WorkflowRun>>(`workflow-runs?offset=${offset}${filter?`&workflow_id=${filter}`:''}`),api<Page<Agent>>('agents?limit=100')]);
      const allAgents=[...a.items];
      for(let start=100;start<a.total;start+=100)allAgents.push(...(await api<Page<Agent>>(`agents?offset=${start}&limit=100`)).items);
      if(version!==requestVersion.current)return;
      setWorkflows(w.items);setWorkflowTotal(w.total);setRuns(r.items);setTotal(r.total);setAgents(allAgents);setError('');
    }catch(err){if(version===requestVersion.current)setError((err as Error).message);}finally{if(version===requestVersion.current)setLoading(false);}
  },[offset,filter,workflowOffset]);
  useEffect(()=>{void load();const timer=setInterval(()=>void load(true),4000);return()=>{clearInterval(timer);requestVersion.current++;};},[load]);
  useEffect(()=>{if(composer)createDialog.current?.showModal();else createDialog.current?.close();},[composer]);
  useEffect(()=>{if(target)taskDialog.current?.showModal();else taskDialog.current?.close();},[target]);
  useEffect(()=>{if(selectedId)detailDialog.current?.showModal();else detailDialog.current?.close();},[selectedId]);
  useEffect(()=>{
    if(!selectedId)return;
    let alive=true;
    async function refresh(){try{
      const [run,s]=await Promise.all([api<WorkflowRun>(`workflow-runs/${selectedId}`),api<Page<WorkflowStep>>(`workflow-runs/${selectedId}/steps`)]);
      const first=await api<Page<Event>>(`workflow-runs/${selectedId}/events?limit=100`);
      const all=[...first.items];for(let start=100;start<first.total;start+=100)all.push(...(await api<Page<Event>>(`workflow-runs/${selectedId}/events?offset=${start}&limit=100`)).items);
      if(alive){setSelected(run);setSteps(s.items);setEvents(all);}
    }catch(err){if(alive)setError((err as Error).message);}}
    void refresh();const timer=setInterval(()=>void refresh(),1500);return()=>{alive=false;clearInterval(timer);};
  },[selectedId]);
  async function mutate(action:()=>Promise<unknown>){setBusy(true);setError('');try{await action();await load(true);}catch(err){setError((err as Error).message);}finally{setBusy(false);}}
  function openForm(w?:Workflow){setEditing(w||null);setForm(w?{name:w.name,agent_ids:[...w.agent_ids],retry_from:w.retry_from,max_revisions:w.max_revisions,max_calls:w.max_calls,max_total_tokens:w.max_total_tokens,timeout_seconds:w.timeout_seconds,status:w.status}:{...fresh,agent_ids:['planner','researcher','executor','reviewer'].map(role=>agents.find(a=>a.role===role)?.id||'')});setComposer(true);}
  function nodes(w:Workflow):WorkflowNode[]{return w.agent_ids.map(id=>{const a=agents.find(a=>a.id===id);return {agent_id:id,name:a?.name||id.slice(0,8),role:a?.role||'pending'};});}
  function changeStage(index:number,value:string){const ids=[...form.agent_ids];ids[index]=value;setForm({...form,agent_ids:ids});}
  function move(index:number,direction:number){const to=index+direction;if(to<0||to>=form.agent_ids.length)return;const ids=[...form.agent_ids];[ids[index],ids[to]]=[ids[to],ids[index]];setForm({...form,agent_ids:ids});}
  function remove(index:number){setForm({...form,agent_ids:form.agent_ids.filter((_,i)=>i!==index),retry_from:Math.min(form.retry_from,form.agent_ids.length-3)});}
  async function save(event:FormEvent){event.preventDefault();await mutate(async()=>{await api(`workflows${editing?`/${editing.id}`:''}`,editing?'PUT':'POST',form);setComposer(false);});}
  async function run(event:FormEvent){event.preventDefault();if(!target)return;if(provider?.provider!=='mock'&&!confirm(t('workflowConfirmRun')))return;await mutate(async()=>{const r=await api<WorkflowRun>(`workflows/${target.id}/run`,'POST',task);setTarget(null);setSteps([]);setEvents([]);setSelected(r);});}
  function openRun(r:WorkflowRun){setSteps([]);setEvents([]);setSelected(r);}
  const badge=(status:string)=><span className={`badge ${status}`}><i/>{t(status)}</span>;
  const date=(value:string)=>new Date(value).toLocaleString(locale==='ru'?'ru-RU':'en-GB');

  return <div className="workflow-workspace">
    <div className="notice">{t('workflowDescription')}<p>{t('workflowSafety')}</p></div>
    <div className="panel-heading workflow-toolbar"><h2>{t('workflows')}</h2><button className="primary" onClick={()=>openForm()} disabled={agents.length<2}><Plus size={16}/>{t('newWorkflow')}</button></div>
    {agents.length<2&&<p className="notice">{t('workflowAgentsRequired')}</p>}
    {error&&<div className="error" role="alert">{t(error)}<button onClick={()=>void load()}>{t('retry')}</button></div>}
    {loading?<div className="loading" role="status">{t('loading')}</div>:<>
      {workflows.length?<div className="agent-grid">{workflows.map(w=><article className="agent-card" key={w.id}><div className="card-top"><GitBranch size={24}/>{badge(w.status)}</div><h2>{w.name}</h2><WorkflowGraph nodes={nodes(w)} retryFrom={w.retry_from} locale={locale}/><div className="card-meta"><span>{t('calls')}: {w.max_calls}</span><span>{t('maxRevisions')}: {w.max_revisions}</span></div><div className="card-actions"><button className="secondary" disabled={busy||w.status!=='active'} onClick={()=>{setTask({title:'',prompt:''});setTarget(w);}}><CirclePlay size={15}/>{t('run')}</button><button onClick={()=>openForm(w)}>{t('edit')}</button><button disabled={busy} onClick={()=>{if(confirm(t('confirmDelete')))void mutate(()=>api(`workflows/${w.id}`,'DELETE'));}}>{t('delete')}</button></div></article>)}</div>:<div className="empty"><h3>{t('empty')}</h3><p>{t('emptyWorkflows')}</p></div>}
      {workflowTotal>50&&<div className="pagination"><button disabled={!workflowOffset} onClick={()=>setWorkflowOffset(Math.max(0,workflowOffset-50))}>{t('previous')}</button><span>{t('page')} {workflowOffset/50+1}</span><button disabled={workflowOffset+50>=workflowTotal} onClick={()=>setWorkflowOffset(workflowOffset+50)}>{t('next')}</button></div>}
      <section className="panel workflow-history"><div className="panel-heading"><h2>{t('workflowRuns')}</h2><select aria-label={t('workflow')} value={filter} onChange={e=>{setFilter(e.target.value);setOffset(0);}}><option value="">{t('allWorkflows')}</option>{workflows.map(w=><option key={w.id} value={w.id}>{w.name}</option>)}</select></div>{runs.length?<div className="execution-list">{runs.map(r=><button className="execution-row" key={r.id} onClick={()=>openRun(r)}><span className="row-info"><strong>{r.title}</strong><small>{date(r.created_at)} · {t('calls')}: {r.calls} · {t('tokens')}: {r.input_tokens+r.output_tokens}</small></span>{badge(r.status)}</button>)}</div>:<div className="empty"><p>{t('workflowNoRuns')}</p></div>}</section>
      {total>50&&<div className="pagination"><button disabled={!offset} onClick={()=>setOffset(Math.max(0,offset-50))}>{t('previous')}</button><span>{t('page')} {offset/50+1} · {t('total')} {total}</span><button disabled={offset+50>=total} onClick={()=>setOffset(offset+50)}>{t('next')}</button></div>}
    </>}
    <dialog ref={createDialog} onCancel={()=>setComposer(false)} onClose={()=>setComposer(false)}><div className="dialog-heading"><h2>{t(editing?'editWorkflow':'newWorkflow')}</h2><button className="icon-button" aria-label={t('close')} onClick={()=>setComposer(false)}><X size={20}/></button></div><form onSubmit={save}>
      <label>{t('name')}<input required maxLength={120} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>
      <fieldset><legend>{t('workflowSequence')}</legend>{form.agent_ids.map((id,index)=><div className="stage-editor" key={index}><label>{t('step')} {index+1}<select required value={id} onChange={e=>changeStage(index,e.target.value)}><option value="">{t('selectAgent')}</option>{agents.map(a=><option key={a.id} value={a.id} disabled={form.agent_ids.includes(a.id)&&a.id!==id}>{a.name} · {t(a.role)}</option>)}</select></label><button type="button" aria-label={`${t('moveUp')} ${index+1}`} disabled={index===0} onClick={()=>move(index,-1)}><ArrowUp size={16}/></button><button type="button" aria-label={`${t('moveDown')} ${index+1}`} disabled={index===form.agent_ids.length-1} onClick={()=>move(index,1)}><ArrowDown size={16}/></button><button type="button" aria-label={`${t('removeStage')} ${index+1}`} disabled={form.agent_ids.length<=2} onClick={()=>remove(index)}><X size={16}/></button></div>)}<button type="button" className="secondary" disabled={form.agent_ids.length>=8} onClick={()=>setForm({...form,agent_ids:[...form.agent_ids.slice(0,-1),'',form.agent_ids.at(-1)||'']})}><Plus size={15}/>{t('addStage')}</button><p>{t('reviewerLast')}</p></fieldset>
      <label>{t('retryFrom')}<select value={form.retry_from} onChange={e=>setForm({...form,retry_from:Number(e.target.value)})}>{form.agent_ids.slice(0,-1).map((id,index)=><option key={index} value={index}>{index+1} · {agents.find(a=>a.id===id)?.name||t('selectAgent')}</option>)}</select></label>
      <div className="form-grid">{(['max_revisions','max_calls','max_total_tokens','timeout_seconds'] as const).map((key,index)=><label key={key}>{t(['maxRevisions','maxCalls','maxTotalTokens','workflowTimeout'][index])}<input type="number" required min={[0,form.agent_ids.length,1024,1][index]} max={[3,64,262144,600][index]} value={form[key]} onChange={e=>setForm({...form,[key]:Number(e.target.value)})}/></label>)}</div>
      <label>{t('status')}<select value={form.status} onChange={e=>setForm({...form,status:e.target.value})}><option value="active">{t('active')}</option><option value="disabled">{t('disabled')}</option></select></label><p className="notice">{t('totalBudgetNotice')}</p>{error&&<div className="error" role="alert">{t(error)}</div>}<div className="dialog-actions"><button type="button" className="secondary" onClick={()=>setComposer(false)}>{t('cancel')}</button><button className="primary" disabled={busy}>{t('save')}</button></div>
    </form></dialog>
    <dialog ref={taskDialog} onCancel={()=>setTarget(null)} onClose={()=>setTarget(null)}><div className="dialog-heading"><h2>{t('workflowTask')}</h2><button className="icon-button" aria-label={t('close')} onClick={()=>setTarget(null)}><X size={20}/></button></div><form onSubmit={run}><label>{t('title')}<input required maxLength={200} value={task.title} onChange={e=>setTask({...task,title:e.target.value})}/></label><label>{t('prompt')}<textarea required rows={6} maxLength={32000} value={task.prompt} onChange={e=>setTask({...task,prompt:e.target.value})}/></label>{error&&<div className="error" role="alert">{t(error)}</div>}<div className="dialog-actions"><button className="primary" disabled={busy}>{t('run')}</button></div></form></dialog>
    <dialog ref={detailDialog} className="detail-dialog" onCancel={()=>setSelected(null)} onClose={()=>setSelected(null)}>{selected&&<><div className="dialog-heading"><div><span className="eyebrow">{t('workflowRuns')}</span><h2>{selected.title}</h2></div><button className="icon-button" aria-label={t('close')} onClick={()=>setSelected(null)}><X size={20}/></button></div><div className="detail-meta">{badge(selected.status)}{['running','queued'].includes(selected.status)&&<button className="secondary" disabled={busy} onClick={()=>void mutate(()=>api(`workflow-runs/${selected.id}/cancel`,'POST'))}>{t('cancel')}</button>}</div>
      <div className="detail-metrics">{[['currentAgent',selected.current_stage===null?t('pending'):selected.graph[selected.current_stage]?.name],['currentStage',selected.current_stage===null?t('pending'):selected.current_stage+1],['duration',selected.duration_ms===null?t('pending'):`${(selected.duration_ms/1000).toFixed(2)} ${t('seconds')}`],['tokens',`${selected.input_tokens} + ${selected.output_tokens}`],['calls',`${selected.calls} / ${selected.limits.max_calls}`],['revisions',`${selected.revisions} / ${selected.limits.max_revisions}`]].map(([label,value])=><div key={label}><small>{t(String(label))}</small><strong>{value}</strong></div>)}</div>
      {selected.error&&<div className="error" role="alert">{t(selected.error)}</div>}<WorkflowGraph nodes={selected.graph} retryFrom={selected.retry_from} locale={locale} run={selected} steps={steps}/>
      {selected.result&&<><h3>{t('workflowResult')}</h3><pre className="result">{JSON.stringify(selected.result,null,2)}</pre></>}
      <h3>{t('workflowHistory')}</h3><div className="workflow-step-history">{steps.map(s=><details key={s.id} className="stage-detail"><summary><strong>{s.stage_index+1}. {s.agent_name}</strong>{badge(s.status)}<small>{t('attempt')} {s.attempt} · {t('tokens')}: {s.input_tokens} + {s.output_tokens} · {s.duration_ms===null?t('pending'):`${(s.duration_ms/1000).toFixed(2)} ${t('seconds')}`}</small></summary>{s.error&&<div className="error">{t(s.error)}</div>}<h3>{t('structuredInput')}</h3><pre className="result">{JSON.stringify(s.input,null,2)}</pre><h3>{t('structuredOutput')}</h3><pre className="result">{s.output?JSON.stringify(s.output,null,2):s.raw_output||t('pending')}</pre>{s.output?.decision&&<p>{t('reviewDecision')}: {t(s.output.decision)} {s.output.feedback}</p>}</details>)}</div>
      <ToolHistory runId={selected.id} kind="workflow" locale={locale}/><h3>{t('trace')}</h3><ol className="trace">{events.map(e=><li key={e.id}><span className="trace-dot"/><div><strong>{t(e.kind)}</strong><small>{date(e.created_at)}{typeof e.payload.stage_index==='number'?` · ${t('step')} ${e.payload.stage_index+1}`:''}</small></div></li>)}</ol><p className="notice">{t('workflowSnapshots')}</p>
    </>}</dialog>
  </div>;
}
