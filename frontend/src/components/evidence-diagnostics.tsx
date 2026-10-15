'use client';
import {translate} from '@/lib/i18n';
export type ReliabilityMetric={correct_abstention_rate?:number|null;false_abstention_rate?:number|null;answer_repair_rate?:number|null;reretrieval_success_rate?:number|null;unsupported_answer_rate?:number|null;citation_validity_rate?:number|null;evidence_statuses?:Record<string,number>;latency_breakdown_ms?:Record<string,number>;repaired_answers?:number;reretrieval_successes?:number};
export function EvidenceMetrics({metric,locale}:{metric:ReliabilityMetric;locale:'ru'|'en'}){
 const t=(s:string)=>translate(locale,s);
 const rates=[['evidenceCAR',metric.correct_abstention_rate],['evidenceFAR',metric.false_abstention_rate],['evidenceRepairRate',metric.answer_repair_rate],['evidenceRetrievalRate',metric.reretrieval_success_rate],['evidenceUnsupportedRate',metric.unsupported_answer_rate],['evidenceCitationRate',metric.citation_validity_rate]] as const;
 return <details><summary>{t('evidenceDiagnostics')}</summary><dl className="evidence-metrics">{rates.map(([label,value])=><div key={label}><dt>{t(label)}</dt><dd>{value==null?'—':(value*100).toFixed(1)+'%'}</dd></div>)}</dl><p>{t('evidenceSufficiency')}: {Object.entries(metric.evidence_statuses||{}).map(([s,n])=>`${t(s)} ${n}`).join(' · ')}</p><p>{t('evidenceLatency')}: {Object.values(metric.latency_breakdown_ms||{}).map(n=>n.toFixed(1)+' ms').join(' / ')}</p></details>;
}
type Verification={status:string;sufficiency?:unknown;original_answer?:string;original_claims?:unknown;repair_attempts?:unknown[];retrieval_attempts?:unknown[];initial_evidence?:unknown;policy?:unknown};
export function EvidenceDiagnostics({verification:v,locale}:{verification:Verification;locale:'ru'|'en'}){
 const t=(s:string)=>translate(locale,s);
 const sections=[['evidenceSufficiency',v.sufficiency],['evidenceInitial',v.initial_evidence],['evidenceOriginal',v.original_answer],['evidenceClaimChecks',v.original_claims],['evidenceRetrieval',v.retrieval_attempts],['evidenceRepairs',v.repair_attempts],['evidencePolicy',v.policy]];
 return <section aria-label={t('evidenceDiagnostics')}><p className="badge">{t(v.status)}</p>{sections.map(([key,value])=>value!==undefined&&<details key={String(key)}><summary>{t(String(key))}</summary><pre className="result">{typeof value==='string'?value:JSON.stringify(value,null,2)}</pre></details>)}</section>;
}
