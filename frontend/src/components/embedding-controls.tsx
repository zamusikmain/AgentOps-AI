'use client';
import {useState} from 'react';
import {api} from '@/lib/types';
import type {KnowledgeDocument} from '@/lib/knowledge';
import {translate} from '@/lib/i18n';
export function EmbeddingControls({document:d,locale}:{document:KnowledgeDocument;locale:'ru'|'en'}){
 const ru=locale==='ru';const [busy,setBusy]=useState(false);const [message,setMessage]=useState('');
 const statuses:Record<string,string>=ru?{ready:'Готов',not_indexed:'Нет индекса',indexing:'Индексируется',failed:'Ошибка',needs_consent:'Нужно согласие'}:{ready:'Ready',not_indexed:'Not indexed',indexing:'Indexing',failed:'Failed',needs_consent:'Consent required'};
 async function reindex(){setBusy(true);setMessage('');try{const plan=await api<{external:boolean;external_enabled:boolean;model:string;chunks:number;expected_requests:number}>(`knowledge/documents/${d.id}/embedding-plan`);if(plan.external){if(!plan.external_enabled)throw new Error(ru?'Внешние embeddings отключены настройками.':'External embeddings are disabled.');if(!confirm(`${ru?'Отправить текст PDF внешнему провайдеру?':'Send PDF text to the external provider?'} ${plan.model}, ${plan.chunks} ${ru?'фрагментов':'chunks'}, ${plan.expected_requests} ${ru?'запросов':'requests'}.`))return;}const result=await api<{skipped?:boolean}>(`knowledge/documents/${d.id}/reindex`,'POST',{external_consent:plan.external});setMessage(result.skipped?(ru?'Индекс не изменился.':'Index unchanged.'):(ru?'Проверка индекса запущена.':'Index check started.'));}catch(e){setMessage((e as Error).message);}finally{setBusy(false);}}
 return <div><small>{ru?'Векторы':'Vectors'}: {statuses[d.embedding_status]||d.embedding_status} · {d.embedded_chunks}/{d.chunks}</small>{d.embedding_error&&<p role="alert">{translate(locale,d.embedding_error)}</p>}<button type="button" className="secondary" disabled={busy||d.status!=='ready'||d.embedding_status==='indexing'} onClick={()=>void reindex()}>{ru?'Переиндексировать':'Reindex'}</button>{message&&<p role="status">{/^[a-z_]+$/.test(message)?translate(locale,message):message}</p>}</div>;
}
