import {test,expect} from './authenticated-test';

test('create agent, edit, run task, reopen persisted result, switch RU/EN and theme',async({page})=>{
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Ваши процессы под контролем.'})).toBeVisible();
  await expect(page.getByText('ТЕСТОВЫЙ РЕЖИМ MOCK — ответы являются тестовыми данными.')).toBeVisible();
  await page.getByRole('button',{name:'Создать агента',exact:true}).first().click();
  await page.getByLabel('Название',{exact:true}).fill('E2E Planner');
  await page.getByLabel('Системные инструкции').fill('Create a concise project plan.');
  await page.getByRole('button',{name:'Сохранить',exact:true}).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await page.getByRole('button',{name:'Агенты',exact:false}).first().click();
  await expect(page.getByRole('heading',{name:'E2E Planner'})).toBeVisible();
  await page.locator('article').filter({has:page.getByRole('heading',{name:'E2E Planner',exact:true})}).getByRole('button',{name:'Изменить',exact:true}).click();
  await page.getByLabel('Название',{exact:true}).fill('E2E Updated Planner');
  await page.getByRole('button',{name:'Сохранить',exact:true}).click();
  await expect(page.getByRole('heading',{name:'E2E Updated Planner'})).toBeVisible();
  await page.getByRole('button',{name:'Задачи',exact:true}).click();
  await page.getByRole('button',{name:'Создать задачу',exact:true}).first().click();
  await page.getByLabel('Заголовок').fill('E2E Business task');
  await page.getByLabel('Инструкции задачи').fill('Make a launch checklist.');
  const agentOption=await page.getByRole('option',{name:/E2E Updated Planner/}).getAttribute('value');
  await page.getByRole('dialog').getByRole('combobox',{name:'Агент',exact:true}).selectOption(agentOption!);
  await page.getByRole('button',{name:'Сохранить',exact:true}).click();
  await page.locator('.task-row').filter({hasText:'E2E Business task'}).getByRole('button',{name:'Запустить',exact:true}).click();
  const detail=page.getByRole('dialog');
  await expect(detail.getByText('[MOCK] Offline test response',{exact:true})).toBeVisible();
  await expect(detail.getByText('Ответ модели',{exact:true})).toBeVisible();
  await expect(detail.getByText('12',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Закрыть',exact:true}).click();
  await page.reload();
  await page.getByRole('button',{name:'Запуски',exact:true}).click();
  await page.getByRole('button').filter({hasText:'E2E Business task'}).click();
  await expect(page.getByRole('dialog').getByText('[MOCK] Offline test response',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Закрыть',exact:true}).click();
  await page.getByRole('button',{name:'Переключить язык'}).click();
  await expect(page.getByRole('heading',{name:'Executions',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Switch theme'}).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme','light');
  await page.screenshot({path:'test-results/workspace-light.png',fullPage:true});
  await page.getByRole('button',{name:'Overview',exact:true}).click();
  await page.getByRole('button',{name:'Switch theme'}).click();
  await page.screenshot({path:'test-results/workspace-dark.png',fullPage:true});
});

test('mobile workflow navigation',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await page.getByRole('button',{name:'Открыть навигацию'}).click();
  await page.getByRole('button',{name:'Процессы',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Процессы',exact:true}).first()).toBeVisible();
  await expect(page.getByText(/Агенты последовательно передают/)).toBeVisible();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({path:'test-results/workspace-mobile.png',fullPage:true});
});

test('proxy denies cross-origin mutation and exposes no secrets',async({request})=>{
  const forbidden=await request.post('/api/agents',{headers:{Origin:'https://untrusted.example'},data:{}});
  expect(forbidden.status()).toBe(403);
  const providers=await request.get('/api/providers');
  expect(providers.status()).toBe(200);
  const payload=await providers.text();
  expect(payload).not.toContain('e2e-test-token');
  expect(payload).not.toContain('GEMINI_API_KEY');
});
