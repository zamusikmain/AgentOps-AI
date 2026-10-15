import {ArrowDown,CornerUpLeft,Bot} from 'lucide-react';
import {translate} from '@/lib/i18n';
import type {WorkflowNode,WorkflowRun,WorkflowStep} from '@/lib/workflows';

export function WorkflowGraph({nodes,retryFrom,locale,run,steps=[]}:{nodes:WorkflowNode[];retryFrom:number;locale:'ru'|'en';run?:WorkflowRun;steps?:WorkflowStep[]}){
  const t=(key:string)=>translate(locale,key);
  return <div className="multi-graph" aria-label={t('workflowSequence')}>{nodes.map((node,index)=>{
    const attempt=steps.filter(s=>s.stage_index===index).at(-1);
    const status=attempt?.status||'pending';
    return <div className="multi-graph-stage" key={`${node.agent_id}-${index}`}><div className={`multi-graph-node ${status} ${run?.status==='running'&&run.current_stage===index?'current':''}`}>
      <Bot size={18}/><div><strong>{index+1}. {node.name}</strong><small>{t(node.role)}</small></div>
      {run&&<span className={`badge ${status}`}>{t(status)}</span>}
    </div>{index<nodes.length-1&&<ArrowDown size={18}/>}</div>;
  })}<div className="retry-edge"><CornerUpLeft size={18}/>{t('retryEdge')} {retryFrom+1} · {nodes[retryFrom]?.name}</div></div>;
}
