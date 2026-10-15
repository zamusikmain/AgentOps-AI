import {test,expect} from './authenticated-test';
import {resolve} from 'node:path';
test('v11 full offline workspace RAG, citations, reload, modes, readiness and isolation',async({page,request})=>{
 await page.goto('/ai');await page.getByLabel('Название пространства',{exact:true}).fill('Offline E2E workspace');await page.getByRole('button',{name:'Создать workspace',exact:true}).click();
 await page.getByLabel('Загрузить PDF в workspace').setInputFiles(resolve('../docs/fixtures/AgentOps_RAG_Test_Corporate_Policy.pdf'));
 await expect(page.getByText(/Проиндексирован · 3/)).toBeVisible({timeout:40000});
 await page.getByLabel('Вопрос по документам',{exact:true}).fill('Какой внутренний код проекта Aurora Portal?');await page.getByRole('button',{name:'Спросить Mock агента',exact:true}).click();
 const answer=page.getByRole('region',{name:'Answer'});await expect(answer).toContainText('POLARIS-7429',{timeout:30000});await expect(answer).toContainText('Mock');await expect(answer).toContainText('Страница 1');
 await answer.getByRole('button',{name:'Открыть источник'}).first().click();await expect(page.getByRole('region',{name:'Source'})).toContainText('POLARIS-7429');await page.getByRole('button',{name:'Закрыть источник'}).click();
 await page.getByRole('button',{name:'Готовность Live'}).click();await expect(page.getByRole('heading',{name:'Live заблокирован · Gemini UNVERIFIED'})).toBeVisible();
 const original=await page.getByLabel('Выбрать workspace').inputValue();const list=(await (await request.get(`/api/workspaces/${original}/knowledge/documents`)).json()).items;const doc=list[0];
 const foreign={Authorization:'Bearer e2e-v11-foreign-fixture'};
 expect((await request.get(`/api/workspaces/${original}/knowledge/documents/${doc.id}/chunks`,{headers:foreign})).status()).toBe(404);
 expect((await request.get(`/api/workspaces/${original}/knowledge/runs`,{headers:foreign})).status()).toBe(404);
 expect((await (await request.get('/api/workspaces',{headers:foreign})).json()).items).toEqual([]);
 expect((await request.post(`/api/workspaces/${original}/live`,{data:{}})).status()).toBe(403);
 await page.reload();await expect(page.getByLabel('Выбрать workspace')).toHaveValue(original);await page.getByRole('button').filter({hasText:'RAG: Какой внутренний код'}).click();await expect(answer).toContainText('POLARIS-7429');
 for(const marker of ['[FIXTURE_UNAVAILABLE]','[FIXTURE_TOKEN_OVERRUN]']){
  await page.getByLabel('Вопрос по документам').fill('Какой код проекта Aurora Portal? '+marker);await page.getByRole('button',{name:'Спросить Mock агента',exact:true}).click();await expect(answer.getByRole('alert')).toBeVisible({timeout:30000});
 }
 await page.getByLabel('Вопрос по документам').fill('Какой код проекта Aurora Portal? [FIXTURE_SLOW]');
 const launched=page.waitForResponse(r=>r.url().endsWith('/knowledge/ask')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Спросить Mock агента',exact:true}).click();const slow=await (await launched).json();
 const cancelled=page.waitForResponse(r=>r.url().endsWith(`/executions/${slow.id}/cancel`));
 await answer.getByRole('button',{name:'Отменить',exact:true}).click();expect((await cancelled).status()).toBe(200);await expect(answer).toContainText('Отменён',{timeout:15000});
 await page.getByLabel('Название пространства').fill('Second isolated workspace');await page.getByRole('button',{name:'Создать workspace',exact:true}).click();await expect(page.getByLabel('Выбрать workspace')).not.toHaveValue(original);const other=await page.getByLabel('Выбрать workspace').inputValue();expect((await request.get(`/api/workspaces/${other}/knowledge/documents/${doc.id}/chunks`)).status()).toBe(404);
 await expect(page.getByText('Запросов пока нет.')).toBeVisible();
 await page.getByLabel('Загрузить PDF в workspace').setInputFiles({name:'bad.pdf',mimeType:'application/pdf',buffer:Buffer.from('invalid PDF')});await expect(page.getByTestId('ai-workspace').getByRole('alert')).toContainText('invalid_pdf');
 await page.getByRole('button',{name:'Переключить язык',exact:true}).click();await expect(page.getByLabel('Select workspace')).toBeVisible();await page.getByRole('button',{name:'Switch theme',exact:true}).click();await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false);
 await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(page.getByRole('heading',{name:'Sign in',exact:true})).toBeVisible();expect((await page.request.get(`/api/workspaces/${original}/knowledge/runs`)).status()).toBe(401);
});
