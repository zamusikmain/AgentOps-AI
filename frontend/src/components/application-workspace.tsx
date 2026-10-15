'use client';
import {useCallback, useEffect, useRef, useState, type FormEvent} from 'react';
import {Activity, ArrowDown, ArrowRight, Bot, Check, ChevronLeft, ChevronRight, CirclePlay, Clock3, GitBranch, LayoutDashboard, ListTodo, Menu, Moon, Plus, Settings2, ShieldCheck, Sparkles, Sun, Wrench, X} from 'lucide-react';
import {useAuth} from '@/components/authentication';
import {translate, type Key} from '@/lib/i18n';
import {api, type Agent, type Dashboard, type Event, type Execution, type Page, type Provider, type Section, type Task, type ToolDefinition} from '@/lib/types';
import {KnowledgeWorkspace} from '@/components/knowledge-workspace';
import {ValidationWorkspace} from '@/components/validation-workspace';
import {ObservabilityWorkspace} from '@/components/observability-workspace';
import {EvaluationWorkspace} from '@/components/evaluation-workspace';
import type {KnowledgeDocument} from '@/lib/knowledge';
import {ToolHistory} from '@/components/tool-history';
import {ToolCatalog} from '@/components/tool-catalog';
import {WorkflowWorkspace} from '@/components/workflow-workspace';

const sections:Section[]=['dashboard','agents','tasks','executions','workflows','tools','knowledge','evaluation','observability','validation','settings'];
const icons={dashboard:LayoutDashboard,agents:Bot,tasks:ListTodo,executions:Activity,workflows:GitBranch,tools:Wrench,knowledge:ListTodo,evaluation:Activity,observability:Activity,validation:ShieldCheck,settings:Settings2};
const roles=['planner','researcher','executor','reviewer'];
type AgentForm=Omit<Agent,'id'|'created_at'>;
type TaskForm=Pick<Task,'title'|'prompt'|'agent_id'>;
const freshAgent:AgentForm={name:'',role:'planner',instructions:'',model:'',tools:[],document_ids:[],max_steps:4,max_tokens:2048,status:'active'};
const freshTask:TaskForm={title:'',prompt:'',agent_id:''};

export default function Home(){
  const {locale,setLocale,theme,setTheme}=useAuth();
  const [section,setSection]=useState<Section>('dashboard');
  const [mobile,setMobile]=useState(false);
  const [smallScreen,setSmallScreen]=useState(false);
  const [documents,setDocuments]=useState<KnowledgeDocument[]>([]);
  const [toolCatalog,setToolCatalog]=useState<ToolDefinition[]>([]);
  const [agents,setAgents]=useState<Agent[]>([]);
  const [agentTotal,setAgentTotal]=useState(0);
  const [tasks,setTasks]=useState<Task[]>([]);
  const [taskTotal,setTaskTotal]=useState(0);
  const [executions,setExecutions]=useState<Execution[]>([]);
  const [executionTotal,setExecutionTotal]=useState(0);
  const [dashboard,setDashboard]=useState<Dashboard|null>(null);
  const [provider,setProvider]=useState<Provider|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [offset,setOffset]=useState(0);
  const [modal,setModal]=useState<'agent'|'task'|null>(null);
  const [editing,setEditing]=useState<string|null>(null);
  const [agentForm,setAgentForm]=useState<AgentForm>(freshAgent);
  const [taskForm,setTaskForm]=useState<TaskForm>(freshTask);
  const [selected,setSelected]=useState<Execution|null>(null);
  const [events,setEvents]=useState<Event[]>([]);
  const [models,setModels]=useState<string[]>([]);
  const [historyAgent,setHistoryAgent]=useState<string|null>(null);
  const t=(key:string)=>translate(locale,key);
  const dialog=useRef<HTMLDialogElement>(null);
  const detailDialog=useRef<HTMLDialogElement>(null);
  const previousFocus=useRef<HTMLElement|null>(null);
  const activeRequest=useRef(0);


  useEffect(()=>{const query=window.matchMedia('(max-width:760px)');const update=()=>setSmallScreen(query.matches);update();query.addEventListener('change',update);return()=>query.removeEventListener('change',update);},[]);
  useEffect(()=>{document.documentElement.dataset.theme=theme;document.documentElement.lang=locale;localStorage.setItem('theme',theme);localStorage.setItem('locale',locale);},[theme,locale]);
  const load=useCallback(async(quiet=false)=>{
    const version=++activeRequest.current;
    if(!quiet)setLoading(true);
    try{
      const [a,ta,e,d,p,tools,kb]=await Promise.all([
        api<Page<Agent>>(`agents?offset=${section==='agents'?offset:0}&limit=50`),
        api<Page<Task>>(`tasks?offset=${section==='tasks'?offset:0}&limit=50`),
        api<Page<Execution>>(`executions?offset=${section==='executions'?offset:0}&limit=50${historyAgent?`&agent_id=${historyAgent}`:''}`),
        api<Dashboard>('dashboard'),api<Provider>('providers'),api<{items:ToolDefinition[]}>('tools'),api<Page<KnowledgeDocument>>('knowledge/documents?limit=100')]);
      if(version!==activeRequest.current)return;
      setAgents(a.items);setAgentTotal(a.total);setTasks(ta.items);setTaskTotal(ta.total);setExecutions(e.items);setExecutionTotal(e.total);setDashboard(d);setProvider(p);setError('');
      setToolCatalog(tools.items);setDocuments(kb.items);
    }catch(err){if(version===activeRequest.current)setError((err as Error).message);}
    finally{if(version===activeRequest.current)setLoading(false);}
  },[section,offset,historyAgent]);
  useEffect(()=>{void load();const interval=setInterval(()=>void load(true),4000);return()=>clearInterval(interval);},[load]);
  useEffect(()=>{
    if(!selected)return;
    let alive=true;
    async function refresh(){try{const [e,ev]=await Promise.all([api<Execution>(`executions/${selected!.id}`),api<Page<Event>>(`executions/${selected!.id}/events`)]);if(alive){setSelected(e);setEvents(ev.items);}}catch(err){if(alive)setError((err as Error).message);}}
    void refresh();const interval=setInterval(()=>void refresh(),2000);return()=>{alive=false;clearInterval(interval);};
  },[selected?.id]); // Refresh detail without resetting focus.
  useEffect(()=>{
    if(modal){previousFocus.current=document.activeElement as HTMLElement;dialog.current?.showModal();}
    else{dialog.current?.close();previousFocus.current?.focus();}
  },[modal]);
  useEffect(()=>{if(selected)detailDialog.current?.showModal();else detailDialog.current?.close();},[selected?.id]);

  function navigate(s:Section){setSection(s);setOffset(0);setHistoryAgent(null);setMobile(false);}
  function openAgent(agent?:Agent){setEditing(agent?.id||null);setAgentForm(agent?{name:agent.name,role:agent.role,instructions:agent.instructions,model:agent.model,tools:agent.tools,document_ids:agent.document_ids,max_steps:agent.max_steps,max_tokens:agent.max_tokens,status:agent.status}:{...freshAgent,model:provider?.model||''});setModal('agent');}
  function openTask(task?:Task){setEditing(task?.id||null);setTaskForm(task?{title:task.title,prompt:task.prompt,agent_id:task.agent_id}:{...freshTask,agent_id:agents[0]?.id||''});setModal('task');}
  async function mutate(operation:()=>Promise<unknown>){setBusy(true);setError('');try{await operation();await load(true);}catch(err){setError((err as Error).message);}finally{setBusy(false);}}
  async function save(event:FormEvent){event.preventDefault();await mutate(async()=>{await api(`${modal==='agent'?'agents':'tasks'}${editing?`/${editing}`:''}`,editing?'PUT':'POST',modal==='agent'?agentForm:taskForm);setModal(null);});}
  function agentName(id:string){return agents.find(a=>a.id===id)?.name||id.slice(0,8);}
  function taskName(id:string){return tasks.find(a=>a.id===id)?.title||id.slice(0,8);}
  function date(value:string){return new Date(value).toLocaleString(locale==='ru'?'ru-RU':'en-GB',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});}
  function badge(status:string){return <span className={`badge ${status}`}><i/>{t(status)}</span>;}
  function empty(key:Key,action?:()=>void,actionKey?:Key){return <div className="empty"><div className="empty-icon"><Sparkles size={30}/></div><h3>{t('empty')}</h3><p>{t(key)}</p>{action&&<button className="primary" onClick={action}><Plus size={16}/>{t(actionKey||'newAgent')}</button>}</div>;}
  function executionList(rows:Execution[]){return <div className="execution-list">{rows.map(e=><button className="execution-row" key={e.id} onClick={()=>{setEvents([]);setSelected(e);}}><span className="row-symbol"><Activity size={19}/></span><span className="row-info"><strong>{taskName(e.task_id)}</strong><small>{agentName(e.agent_id)} · {date(e.created_at)}</small></span>{badge(e.status)}<span className="row-tokens">{e.input_tokens+e.output_tokens} <small>{t('tokens')}</small></span><ChevronRight size={16}/></button>)}</div>;}
  const total=section==='agents'?agentTotal:section==='tasks'?taskTotal:executionTotal;

  return <div className="app-shell">
    <a className="skip" href="#main">{t('skip')}</a>
    {mobile&&<button className="overlay" aria-label={t('close')} onClick={()=>setMobile(false)}/>}
    <aside className={mobile?'sidebar opened':'sidebar'} inert={smallScreen&&!mobile}>
      <a className="brand" href="/" onClick={e=>{e.preventDefault();navigate('dashboard');}}><span className="brand-mark"><GitBranch size={22}/></span><span>{t('brand')}<em>{t('brandAi')}</em></span></a>
      <div className="workspace-label">{t('workspace')}</div>
      <nav aria-label={t('platform')}>{sections.map(s=>{const Icon=icons[s];return <button key={s} className={section===s?'nav-item selected':'nav-item'} aria-current={section===s?'page':undefined} onClick={()=>navigate(s)}><Icon size={19}/><span>{t(s)}</span>{s==='agents'&&agentTotal>0&&<small>{agentTotal}</small>}</button>;})}</nav>
      <div className="sidebar-bottom"><ShieldCheck size={19}/><div><strong>{t('localAccess')}</strong><small>{t('security')}</small></div></div>
    </aside>
    <div className="workspace">
      <header className="topbar"><div className="topbar-title"><button className="icon-button mobile-menu" onClick={()=>setMobile(true)} aria-label={t('menu')}><Menu size={20}/></button><span>{t('platform')}</span><ChevronRight size={14}/><strong>{t(section)}</strong></div><div className="topbar-actions"><span className="local-dot"><i/>{t('localAccess')}</span><button className="language" aria-label={t('language')} onClick={()=>setLocale(locale==='ru'?'en':'ru')}>{locale.toUpperCase()}</button><button className="icon-button" aria-label={t('theme')} onClick={()=>setTheme(theme==='dark'?'light':'dark')}>{theme==='dark'?<Sun size={18}/>:<Moon size={18}/>}</button></div></header>
      <main id="main">
        <div className="page-heading"><div><div className="eyebrow">{t('workspace')}</div><h1>{section==='dashboard'?t('tagline'):t(section)}</h1><p>{t(`${section}Description`)}</p></div>{(section==='dashboard'||section==='agents')&&<button className="primary" onClick={()=>openAgent()}><Plus size={17}/>{t('newAgent')}</button>}{section==='tasks'&&<button className="primary" onClick={()=>openTask()} disabled={!agents.length}><Plus size={17}/>{t('newTask')}</button>}</div>
        {provider?.provider==='mock'&&<div className="notice">{t('mockNotice')}</div>}
        {error&&<div className="error" role="alert"><span>{t(error)}</span><button onClick={()=>void load()}>{t('retry')}</button></div>}
        {loading?<div className="loading" role="status"><span className="spinner"/>{t('loading')}</div>:<>
          {section==='dashboard'&&dashboard&&<>
            <div className="metrics">{(['totalAgents','totalTasks','totalExecutions','tokens'] as Key[]).map((label,index)=>{const key=['agents','tasks','executions','tokens'][index];const Icon=[Bot,ListTodo,Activity,Sparkles][index];return <div className="metric" key={key}><div><span>{t(label)}</span><Icon size={18}/></div><strong>{dashboard.counts[key]||0}</strong><small>{index===2?`${dashboard.counts.completed} ${t('success')} · ${dashboard.counts.running} ${t('inFlight')}`:t('workspace')}</small></div>;})}</div>
            {!agentTotal&&<div className="welcome"><div className="welcome-art"><GitBranch size={68}/><span className="orbit one"><Bot size={21}/></span><span className="orbit two"><Check size={20}/></span></div><div><span className="eyebrow">{t('ready')}</span><h2>{t('createFirst')}</h2><p>{t('readyDescription')}</p><button className="secondary" onClick={()=>openAgent()}>{t('newAgent')}<ArrowRight size={17}/></button></div></div>}
            <section className="panel"><div className="panel-heading"><h2>{t('singleHistory')}</h2><button className="text-button" onClick={()=>navigate('executions')}>{t('all')}<ArrowRight size={15}/></button></div>{dashboard.recent.length?executionList(dashboard.recent):empty('noActivity')}</section>
          </>}
          {section==='agents'&&(agents.length?<div className="agent-grid">{agents.map(a=><article className="agent-card" key={a.id}><div className="card-top"><span className={`agent-icon ${a.role}`}><Bot size={25}/></span>{badge(a.status)}</div><h2>{a.name}</h2><span className="role-label">{t(a.role)}</span><p className="instructions-preview">{a.instructions}</p><div className="card-meta"><span>{a.model}</span><span>{a.max_steps} · {t('step')}</span></div><div className="card-actions"><button onClick={()=>openAgent(a)}>{t('edit')}</button><button onClick={()=>{setHistoryAgent(a.id);setSection('executions');setOffset(0);}}>{t('viewHistory')}</button><button disabled={busy} onClick={()=>{if(confirm(t('confirmDelete')))void mutate(()=>api(`agents/${a.id}`,'DELETE'));}}>{t('delete')}</button></div></article>)}</div>:empty('emptyAgents',()=>openAgent(),'newAgent'))}
          {section==='tasks'&&(tasks.length?<section className="panel task-list">{tasks.map(task=><article className="task-row" key={task.id}><span className="row-symbol"><ListTodo size={20}/></span><div className="task-info"><h3>{task.title}</h3><p>{task.prompt}</p><small>{agentName(task.agent_id)} · {date(task.created_at)}</small></div>{badge(task.status)}<div className="task-actions"><button className="secondary" disabled={busy||task.status==='running'} onClick={()=>{if(provider?.provider==='mock'||confirm(t('confirmRun')))void mutate(async()=>{const e=await api<Execution>(`tasks/${task.id}/run`,'POST');setEvents([]);setSelected(e);});}}><CirclePlay size={16}/>{t('run')}</button><button disabled={task.status==='running'} onClick={()=>openTask(task)}>{t('edit')}</button><button disabled={busy} onClick={()=>{if(confirm(t('confirmDelete')))void mutate(()=>api(`tasks/${task.id}`,'DELETE'));}}>{t('delete')}</button></div></article>)}</section>:empty('emptyTasks',()=>openTask(),'newTask'))}
          {section==='executions'&&<>{historyAgent&&<div className="notice">{t('history')}: {agentName(historyAgent)}<button onClick={()=>setHistoryAgent(null)}>{t('all')}</button></div>}{executions.length?<section className="panel">{executionList(executions)}</section>:empty('emptyExecutions')}</>}
          {section==='workflows'&&<WorkflowWorkspace locale={locale} provider={provider}/>}
          {section==='knowledge'&&<KnowledgeWorkspace locale={locale}/>}
          {section==='evaluation'&&<EvaluationWorkspace locale={locale}/>}
          {section==='observability'&&<ObservabilityWorkspace locale={locale}/>}
          {section==='validation'&&<ValidationWorkspace locale={locale}/>}
          {section==='tools'&&<ToolCatalog tools={toolCatalog} agents={agents} locale={locale}/>}
          {section==='settings'&&provider&&<div className="settings-grid"><section className="panel settings-panel"><h2>{t('provider')}</h2><dl><div><dt>{t('provider')}</dt><dd>{provider.provider}</dd></div><div><dt>{t('status')}</dt><dd>{badge(provider.configured?'active':'disabled')} {t(provider.configured?'configured':'notConfigured')}</dd></div><div><dt>{t('defaultModel')}</dt><dd>{provider.model}</dd></div><div><dt>{t('timeout')}</dt><dd>{provider.timeout_seconds} {t('seconds')}</dd></div></dl><p>{t('unverified')}</p><button className="secondary" disabled={busy} onClick={()=>void mutate(async()=>{const result=await api<{items:string[]}>('models/discover','POST');setModels(result.items);})}>{t('discover')}</button>{models.length>0&&<ul className="model-list">{models.map(m=><li key={m}>{m}</li>)}</ul>}<p>{t('priceNote')}</p></section><section className="panel settings-panel"><ShieldCheck size={30}/><h2>{t('localAccess')}</h2><p>{t('localAccessDescription')}</p><div className="notice">{t('roadmap')}</div></section></div>}
          {['agents','tasks','executions'].includes(section)&&total>50&&<div className="pagination"><button disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-50))}><ChevronLeft size={16}/>{t('previous')}</button><span>{t('page')} {Math.floor(offset/50)+1} · {t('total')} {total}</span><button disabled={offset+50>=total} onClick={()=>setOffset(offset+50)}>{t('next')}<ChevronRight size={16}/></button></div>}
        </>}
        <footer>{t('copyright')}<span><ShieldCheck size={13}/>{t('security')}</span></footer>
      </main>
    </div>
    <dialog ref={dialog} onCancel={()=>setModal(null)} onClose={()=>setModal(null)}><div className="dialog-heading"><h2>{t(editing?'edit':modal==='agent'?'newAgent':'newTask')}</h2><button className="icon-button" aria-label={t('close')} onClick={()=>setModal(null)}><X size={20}/></button></div><form onSubmit={save}>
      {modal==='agent'?<>
        <label>{t('name')}<input required maxLength={120} value={agentForm.name} onChange={e=>setAgentForm({...agentForm,name:e.target.value})}/></label>
        <div className="form-grid"><label>{t('role')}<select value={agentForm.role} onChange={e=>setAgentForm({...agentForm,role:e.target.value})}>{roles.map(r=><option key={r} value={r}>{t(r)}</option>)}</select></label><label>{t('status')}<select value={agentForm.status} onChange={e=>setAgentForm({...agentForm,status:e.target.value})}>{['active','disabled'].map(s=><option key={s} value={s}>{t(s)}</option>)}</select></label></div>
        {agentForm.role==='researcher'&&<p className="notice">{t('researcherNote')}</p>}
        <label>{t('instructions')}<textarea required maxLength={16000} rows={5} value={agentForm.instructions} onChange={e=>setAgentForm({...agentForm,instructions:e.target.value})}/></label>
        <label>{t('model')}<input required pattern="[a-zA-Z0-9._/\-]+" maxLength={120} value={agentForm.model} onChange={e=>setAgentForm({...agentForm,model:e.target.value})}/></label>
        <div className="form-grid"><label>{t('maxSteps')}<input type="number" min={1} max={12} required value={agentForm.max_steps} onChange={e=>setAgentForm({...agentForm,max_steps:Number(e.target.value)})}/></label><label>{t('maxTokens')}<input type="number" min={128} max={16384} required value={agentForm.max_tokens} onChange={e=>setAgentForm({...agentForm,max_tokens:Number(e.target.value)})}/></label></div>
        <fieldset><legend>{t('documentPermissions')}</legend><p>{t('documentScopeNotice')}</p>{documents.filter(d=>d.status==='ready').map(d=><label className="checkbox" key={d.id}><input type="checkbox" checked={agentForm.document_ids.includes(d.id)} onChange={e=>setAgentForm({...agentForm,document_ids:e.target.checked?[...agentForm.document_ids,d.id]:agentForm.document_ids.filter(id=>id!==d.id)})}/>{d.name}</label>)}</fieldset>
        <fieldset><legend>{t('permissions')}</legend>{toolCatalog.map(({name:tool})=><label className="checkbox" key={tool}><input type="checkbox" checked={agentForm.tools.includes(tool)} onChange={e=>setAgentForm({...agentForm,tools:e.target.checked?[...agentForm.tools,tool]:agentForm.tools.filter(x=>x!==tool)})}/>{t(tool)}</label>)}</fieldset>
      </>:<><label>{t('title')}<input required maxLength={200} value={taskForm.title} onChange={e=>setTaskForm({...taskForm,title:e.target.value})}/></label><label>{t('agent')}<select required value={taskForm.agent_id} onChange={e=>setTaskForm({...taskForm,agent_id:e.target.value})}><option value="">{t('agent')}</option>{agents.map(a=><option key={a.id} value={a.id}>{a.name} · {t(a.role)}</option>)}</select></label><label>{t('prompt')}<textarea required maxLength={32000} rows={7} value={taskForm.prompt} onChange={e=>setTaskForm({...taskForm,prompt:e.target.value})}/></label></>}
      {error&&<div className="error" role="alert">{t(error)}</div>}
      <div className="dialog-actions"><button type="button" className="secondary" onClick={()=>setModal(null)}>{t('cancel')}</button><button className="primary" type="submit" disabled={busy||(!agents.length&&modal==='task')}>{t('save')}</button></div>
    </form></dialog>
    <dialog ref={detailDialog} className="detail-dialog" onCancel={()=>setSelected(null)} onClose={()=>setSelected(null)}>{selected&&<><div className="dialog-heading"><div><span className="eyebrow">{t('executions')}</span><h2>{taskName(selected.task_id)}</h2></div><button className="icon-button" aria-label={t('close')} onClick={()=>setSelected(null)}><X size={20}/></button></div><div className="detail-meta">{badge(selected.status)}<small>{selected.id}</small>{['running','queued'].includes(selected.status)&&<button className="secondary" disabled={busy} onClick={()=>void mutate(()=>api(`executions/${selected.id}/cancel`,'POST'))}>{t('cancel')}</button>}</div><div className="detail-metrics">{[['inputTokens',selected.input_tokens],['outputTokens',selected.output_tokens],['duration',selected.duration_ms===null?t('unknown'):`${(selected.duration_ms/1000).toFixed(2)} ${t('seconds')}`],['cost',selected.estimated_cost_usd===null?t('unknown'):`$${selected.estimated_cost_usd.toFixed(6)}`]].map(([key,value])=><div key={key}><small>{t(String(key))}</small><strong>{value}</strong></div>)}</div>{selected.error&&<div className="error" role="alert">{t(selected.error)}</div>}<h3>{t('result')}</h3><pre className="result">{selected.result||(['queued','running'].includes(selected.status)?t('loading'):t('unknown'))}</pre><ToolHistory runId={selected.id} kind="single" locale={locale}/><h3>{t('trace')}</h3><ol className="trace">{events.map(e=><li key={e.id}><span className="trace-dot"/><div><strong>{t(e.kind)}</strong><small>{date(e.created_at)}{typeof e.payload.step==='number'?` · ${t('step')} ${e.payload.step}`:''}{typeof e.payload.name==='string'?` · ${t(e.payload.name)}`:''}</small></div></li>)}</ol></>}</dialog>
  </div>;
}
