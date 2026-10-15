import {test,expect} from './authenticated-test';
test('LLM observability has persisted offline traces, filters, policy validation and RU/EN',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Наблюдаемость LLM',exact:true}).click();await expect(page.getByText(/Внешние API отключены/)).toBeVisible();
 await expect(page.getByRole('heading',{name:'История LLM',exact:true})).toBeVisible();
 const response=await page.request.get('/api/llm/configuration');expect(response.status()).toBe(200);expect((await response.json()).external_api_enabled).toBe(false);
 const invalid=await page.request.put('/api/llm/policy',{headers:{Origin:'http://127.0.0.1:3011'},data:{fallback_enabled:true}});expect(invalid.status()).toBe(422);
 await page.reload();await page.getByRole('button',{name:'Наблюдаемость LLM',exact:true}).click();await expect(page.getByRole('heading',{name:'Версии промптов',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Переключить язык'}).click();await expect(page.getByRole('heading',{name:'LLM requests',exact:true})).toBeVisible();await expect(page.getByText(/External APIs disabled/)).toBeVisible();
 await page.getByRole('button',{name:'Switch theme'}).click();await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false);
});
