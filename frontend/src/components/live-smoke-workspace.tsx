'use client';
import {useEffect,useState} from 'react';
import {api} from '@/lib/types';
import {smokeStrings} from '@/lib/live-smoke-i18n';
import {translate} from '@/lib/i18n';
type Case={case_id:string;result:{question:string;expected_behavior:string;expected_sources:unknown;verification:Record<string,unknown>;actual_answer?:Record<string,unknown>;retrieved_evidence?:unknown;answer_correct:boolean}};
type Run={id:string;mode:string;status:string;result:Record<string,unknown>;cases:Case[];human_reviews:unknown[]};
export function LiveSmokeWorkspace({locale}:{locale:'en'|'ru'}){
 const t=Object.fromEntries(Object.keys(smokeStrings.en).map(key=>[key,translate(locale,'smoke_'+key)])) as typeof smokeStrings.en;const [status,setStatus]=useState<Record<string,unknown>|null>(null);const [runs,setRuns]=useState<Run[]>([]);const [selected,setSelected]=useState<Run|null>(null);const [caseId,setCaseId]=useState('');const [notes,setNotes]=useState('');const [verdict,setVerdict]=useState('correct');const [model,setModel]=useState('');const [busy,setBusy]=useState(false);const [error,setError]=useState('');
 async function load(){try{const [s,r]=await Promise.all([api<Record<string,unknown>>('validation/smoke/status'),api<{items:Run[]}>('validation/smoke/runs')]);setStatus(s);setRuns(r.items);setSelected(old=>r.items.find(r=>r.id===old?.id)||r.items[0]||null);}catch{setError(t.error);}}
 useEffect(()=>{void load();const timer=setInterval(()=>void load(),3000);return()=>clearInterval(timer);},[locale]);
 async function action(fn:()=>Promise<unknown>){setBusy(true);setError('');try{await fn();await load();}catch(e){setError(`${t.error}: ${(e as Error).message}`);}finally{setBusy(false);}}
 const c=selected?.cases?.find(c=>c.case_id===caseId)||selected?.cases?.[0];
 const json=(label:string,value:unknown)=><section><h3>{label}</h3><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(value??null,null,2)}</pre></section>;
 return <section className="panel settings-panel" data-testid="live-smoke"><h2>{t.title}</h2><p className="notice">{t.notice}</p><p>{t.comparison}</p><p>{t.budget}</p>{error&&<p role="alert">{error}</p>}
 <label>{t.model}<input value={model} placeholder="UNVERIFIED" onChange={e=>setModel(e.target.value)}/></label>
 <button className="secondary" disabled={busy} onClick={()=>void action(()=>api('validation/smoke/prepare','POST'))}>{t.prepare}</button>
 <button className="secondary" disabled={busy} onClick={()=>void action(async()=>setStatus(await api('validation/smoke/readiness','POST',{model:model||null})))}>{t.readiness}</button>
 <button className="secondary" disabled={busy} onClick={()=>void action(async()=>setSelected(await api<Run>('validation/smoke/runs','POST',{mode:'REAL_DRY_RUN',model:model||null})))}>{t.dry}</button>
 <button className="primary" disabled={busy||!status?.prepared} onClick={()=>void action(async()=>setSelected(await api<Run>('validation/smoke/runs','POST',{})))}>{t.start}</button>
 {json(t.limits,status)}<h3>{t.history}</h3>{runs.map(r=><button className="execution-row" key={r.id} onClick={()=>{setSelected(r);setCaseId('');}}><span>{r.mode} · {r.status} · {r.id.slice(0,8)}</span></button>)}
 {selected&&<>{json(selected.mode==='MOCK_ONLY'?t.mock:t.live,selected.result)}{['queued','running'].includes(selected.status)&&<button className="secondary" onClick={()=>void action(()=>api(`validation/smoke/runs/${selected.id}/cancel`,'POST'))}>{t.stop}</button>}
 <h3>{t.review}</h3><label>{t.question}<select value={c?.case_id||''} onChange={e=>setCaseId(e.target.value)}>{selected.cases?.map(c=><option value={c.case_id} key={c.case_id}>{c.case_id} · {c.result.question}</option>)}</select></label>
 {c?<><p>{c.result.question}</p>{json(t.answer,c.result.actual_answer||c.result.verification.safe_answer)}{json(t.evidence,c.result.retrieved_evidence)}{json(t.citations,c.result.actual_answer?.citations)}{json(t.expected,{behavior:c.result.expected_behavior,sources:c.result.expected_sources})}{json(t.automatic,{correct:c.result.answer_correct,verification:c.result.verification})}<label>{t.verdict}<select value={verdict} onChange={e=>setVerdict(e.target.value)}>{(['correct','partially_correct','incorrect','unsupported','correct_abstention','false_abstention'] as const).map(v=><option value={v} key={v}>{t[v]}</option>)}</select></label><label>{t.notes}<textarea value={notes} onChange={e=>setNotes(e.target.value)} maxLength={2000}/></label><button className="secondary" disabled={busy||['queued','running'].includes(selected.status)} onClick={()=>void action(()=>api(`validation/smoke/runs/${selected.id}/reviews`,'POST',{case_id:c.case_id,verdict,notes}))}>{t.save}</button></>:<p>{t.noCases}</p>}{json(t.reviews,selected.human_reviews)}</>}
 </section>;
}
