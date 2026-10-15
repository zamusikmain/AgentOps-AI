export type Section = 'dashboard'|'agents'|'tasks'|'executions'|'workflows'|'tools'|'settings'|'knowledge'|'evaluation'|'observability'|'validation';
export type Agent = {id:string;name:string;role:string;instructions:string;model:string;tools:string[];document_ids:string[];max_steps:number;max_tokens:number;status:string;created_at:string};
export type Task = {id:string;title:string;prompt:string;agent_id:string;status:string;created_at:string};
export type Execution = {id:string;task_id:string;task_title?:string;agent_id:string;status:string;result:string|null;error:string|null;input_tokens:number;output_tokens:number;estimated_cost_usd:number|null;duration_ms:number|null;created_at:string};
export type Event = {id:number;kind:string;payload:Record<string, unknown>;created_at:string};
export type Page<T> = {items:T[];total:number;offset:number;limit:number};
export type Provider = {provider:string;configured:boolean;model:string;timeout_seconds:number;input_price_per_million:number|null;output_price_per_million:number|null};
export type Dashboard = {counts:Record<string,number>;recent:Execution[]};
export type ToolDefinition = {id:string;allowed_urls?:string[];access:string;timeout_seconds:number;max_calls:number;max_result_bytes:number;status:string;source:string;name:string;description:string;side_effects:boolean;parameters:Record<string,unknown>};
let csrfCookieName='agentops_csrf';
export async function api<T>(path:string, method='GET', body?:unknown):Promise<T> {
  const response = await fetch(`/api/${path}`, {method,headers:{'Content-Type':'application/json',...(!['GET','HEAD'].includes(method)&&typeof document!=='undefined'?{'X-CSRF-Token':decodeURIComponent(document.cookie.split('; ').find(c=>c.startsWith(csrfCookieName+'='))?.split('=').slice(1).join('=')||'')}: {})},body:body === undefined ? undefined : JSON.stringify(body)});
  if (!response.ok) {const payload=await response.json().catch(()=>({}));if(response.status===401&&typeof window!=='undefined'&&!path.startsWith('auth/login')&&(path!=='auth/me'||payload.error?.code==='session_expired'))window.dispatchEvent(new Event('auth-expired')); throw new Error(payload.error?.code || 'internal_error');}
  if(response.status===204)return undefined as T;const result=await response.json();if(typeof result.csrf_cookie_name==='string')csrfCookieName=result.csrf_cookie_name;return result as T;
}

export function csrfHeader(){return {'X-CSRF-Token':decodeURIComponent(document.cookie.split('; ').find(c=>c.startsWith(csrfCookieName+'='))?.split('=').slice(1).join('=')||'')};}
