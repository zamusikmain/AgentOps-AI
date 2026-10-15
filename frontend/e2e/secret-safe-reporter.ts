import type {Reporter,TestCase,TestResult} from '@playwright/test/reporter';
import {readFileSync,writeFileSync,readdirSync,existsSync} from 'node:fs';
import {resolve,join} from 'node:path';
export default class SecretSafeReporter implements Reporter{
 private secrets:string[]=[];
 constructor(){for(const name of ['auth-development-credentials.local.json','auth-e2e-credentials.local.json','auth-all-browser-credentials.local.json','api-identities.local.json']){const path=resolve(process.cwd(),'../backend/data',name);if(existsSync(path))for(const row of JSON.parse(readFileSync(path,'utf8')))for(const key of ['password','token'])if(typeof row[key]==='string'&&row[key].length>=12)this.secrets.push(row[key]);}this.secrets.push('V7!secure-test.Raven_984','Q9!different-test.Oak_761','R8!generated-E2E-Only_742','K3!changed-E2E-Only_918');this.secrets.sort((a,b)=>b.length-a.length);}
 private clean(text:string){for(const secret of this.secrets)text=text.split(secret).join('[REDACTED]');return text.replace(/Bearer\s+[A-Za-z0-9_-]+/g,'Bearer [REDACTED]').replace(/(agentops_(?:dev_)?(?:session|csrf))=[^;'"\s]+/g,'$1=[REDACTED]');}
 onTestEnd(_test:TestCase,result:TestResult){for(const error of result.errors){if(error.message)error.message=this.clean(error.message);if(error.stack)error.stack=this.clean(error.stack);if(error.snippet)error.snippet=this.clean(error.snippet);}}
 onEnd(){const walk=(folder:string)=>{if(!existsSync(folder))return;for(const entry of readdirSync(folder,{withFileTypes:true})){const path=join(folder,entry.name);if(entry.isDirectory())walk(path);else if(/\.(md|txt|json|html)$/.test(entry.name))writeFileSync(path,this.clean(readFileSync(path,'utf8')));}};walk(resolve(process.cwd(),'test-results'));}
}
