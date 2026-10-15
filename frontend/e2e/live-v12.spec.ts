import {test,expect} from './authenticated-test';
import {resolve} from 'node:path';
test('v12 dry run, budget, locked live and RU EN without external AI',async({page})=>{
 await page.goto('/ai');await page.getByLabel('Название пространства',{exact:true}).fill('v12 controlled local check');await page.getByRole('button',{name:'Создать workspace',exact:true}).click();
 await expect(page.getByLabel('Выбрать workspace').locator('option:checked')).toHaveText('v12 controlled local check');
 await expect(page.getByLabel('Загрузить PDF в workspace')).toBeEnabled();
 await page.getByLabel('Загрузить PDF в workspace').setInputFiles(resolve('../docs/fixtures/AgentOps_RAG_Test_Corporate_Policy.pdf'));
 await expect(page.getByText(/Проиндексирован · 3/)).toBeVisible({timeout:40000});
 const controls=page.getByTestId('live-controls');await controls.getByLabel('Режим выполнения').selectOption('REAL_DRY_RUN');
 await controls.getByLabel('Максимум вызовов',{exact:true}).fill('1');
 await controls.getByRole('button',{name:'Проверить Dry Run',exact:true}).click();await expect(controls.getByRole('status')).toContainText('budget_exceeded');await expect(controls.getByRole('status')).toContainText('внешних вызовов: 0');
 await controls.getByLabel('Режим выполнения').selectOption('REAL_EXECUTION');await expect(controls.getByRole('heading',{name:'LIVE BLOCKED'})).toBeVisible();
 await controls.getByLabel('ID отдельного разрешения Live').fill('00000000-0000-0000-0000-000000000000');
 await page.getByLabel('Вопрос по документам',{exact:true}).fill('What is the incident response policy?');await page.getByRole('button',{name:'Спросить Gemini',exact:true}).click();await expect(page.getByTestId('ai-workspace').getByRole('alert').first()).toBeVisible();
 await page.getByRole('button',{name:'Переключить язык',exact:true}).click();await expect(controls.getByLabel('Execution mode')).toBeVisible();await expect(controls).toContainText('An API key is not consent');
 await controls.getByLabel('Execution mode').selectOption('MOCK_ONLY');await expect(controls.getByRole('heading',{name:'MOCK',exact:true})).toBeVisible();
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false);
});
