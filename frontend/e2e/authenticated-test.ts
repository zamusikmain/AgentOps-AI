import {test as base,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
export {expect};
export const test=base.extend<{authenticated:void}>({request:async({context,playwright,baseURL,authenticated},use)=>{void authenticated;const cookies=await context.cookies();const csrf=cookies.find(c=>c.name==='agentops_csrf')?.value||'';const request=await playwright.request.newContext({baseURL,storageState:await context.storageState(),extraHTTPHeaders:{Origin:baseURL||'http://127.0.0.1:3011','X-CSRF-Token':csrf}});await use(request);await request.dispose();},authenticated:[async({page,context},use)=>{
 const records=JSON.parse(readFileSync(resolve(process.cwd(),'../backend/data/auth-e2e-credentials.local.json'),'utf8'));const user=records[0];
 await page.goto('/login');await page.getByLabel('Email',{exact:true}).fill(user.email);await page.getByLabel('Пароль',{exact:true}).fill(user.password);await page.getByRole('button',{name:'Войти',exact:true}).click();await expect(page.getByRole('button',{name:'Выйти',exact:true})).toBeVisible();
 const csrf=(await context.cookies()).find(c=>c.name==='agentops_csrf')?.value;await context.setExtraHTTPHeaders({'X-CSRF-Token':csrf||''});
 await use();
 },{auto:true}]});
