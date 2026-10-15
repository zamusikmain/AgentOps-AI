import {test,expect} from './authenticated-test';
test('v0.9.1 isolated smoke, human verdict, reload and RU/EN mobile',async({page})=>{
 test.setTimeout(90000);
 await page.goto('/');await page.getByRole('button',{name:'Проверка реальных LLM',exact:true}).click();const panel=page.getByTestId('live-smoke');await expect(panel.getByText(/Запросы Google заблокированы/)).toBeVisible();
 await panel.getByRole('button',{name:'Подготовить изолированный синтетический корпус',exact:true}).click();await expect(panel.getByRole('button',{name:'Запустить offline smoke',exact:true})).toBeEnabled({timeout:30000});
 const response=page.waitForResponse(r=>r.url().endsWith('/api/validation/smoke/runs')&&r.request().method()==='POST');await panel.getByRole('button',{name:'Запустить offline smoke',exact:true}).click();const id=(await (await response).json()).id;
 await expect.poll(async()=>{const r=await page.request.get('/api/validation/smoke/runs/'+id);return (await r.json()).status;},{timeout:60000}).toBe('completed');
 await expect(panel.getByRole('button',{name:'Сохранить ручную оценку'})).toBeEnabled();await panel.getByLabel('Заметки проверяющего').fill('E2E persisted verdict');await panel.getByRole('button',{name:'Сохранить ручную оценку'}).click();await expect(panel.getByText(/E2E persisted verdict/)).toBeVisible();
 await page.reload();await page.getByRole('button',{name:'Проверка реальных LLM',exact:true}).click();await expect(panel.getByText(/E2E persisted verdict/)).toBeVisible();
 await page.getByRole('button',{name:'Переключить язык'}).click();await expect(panel.getByRole('heading',{name:'Human evaluation',exact:true})).toBeVisible();await page.getByRole('button',{name:'Switch theme'}).click();await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false);
 const blocked=await page.request.post('/api/validation/smoke/runs',{data:{mode:'REAL_EXECUTION'}});expect(blocked.status()).toBe(403);
});
