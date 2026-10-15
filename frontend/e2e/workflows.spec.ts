import {test,expect} from './authenticated-test';

test('four agents exchange structured results, graph and history survive reload in RU/EN',async({page,request})=>{
  const ids:string[]=[];
  for(const role of ['planner','researcher','executor','reviewer']){
    const response=await request.post('/api/agents',{headers:{Origin:'http://127.0.0.1:3011'},data:{
      name:`Mock ${role}`,role,instructions:`Perform ${role} duties using supplied context.`,model:'gemini-3.5-flash-lite',tools:[],max_steps:2,max_tokens:2048
    }});
    expect(response.status()).toBe(201);ids.push((await response.json()).id);
  }
  await page.goto('/');
  await page.getByRole('button',{name:'Процессы',exact:true}).click();
  await page.getByRole('button',{name:'Создать процесс',exact:true}).click();
  await page.getByLabel('Название',{exact:true}).fill('Mock portal workflow');
  for(let i=0;i<4;i++)await page.getByRole('combobox',{name:`Шаг ${i+1}`,exact:true}).selectOption(ids[i]);
  await page.getByRole('button',{name:'Сохранить',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Mock portal workflow'})).toBeVisible();
  await page.getByRole('button',{name:'Запустить',exact:true}).click();
  await page.getByRole('dialog').getByLabel('Заголовок',{exact:true}).fill('Mock portal launch');
  await page.getByRole('dialog').getByLabel('Инструкции задачи',{exact:true}).fill('Prepare a release checklist from supplied context.');
  await page.getByRole('dialog').getByRole('button',{name:'Запустить',exact:true}).click();
  const dialog=page.getByRole('dialog');
  await expect(dialog.getByRole('heading',{name:'Итоговый результат процесса',exact:true})).toBeVisible();
  await expect(dialog.getByText('4 / 12',{exact:true})).toBeVisible();
  await expect(dialog.getByText('110 + 160',{exact:true})).toBeVisible();
  const details=dialog.locator('details');
  await expect(details).toHaveCount(4);
  await details.nth(1).locator('summary').click();
  await expect(details.nth(1).getByRole('heading',{name:'Структурированный вход'})).toBeVisible();
  await expect(details.nth(1).locator('pre').first()).toContainText('planner');
  await page.screenshot({path:'test-results/workflow-result-ru.png',fullPage:true});
  await page.getByRole('button',{name:'Закрыть',exact:true}).click();
  await page.reload();
  await page.getByRole('button',{name:'Процессы',exact:true}).click();
  await page.getByRole('button').filter({hasText:'Mock portal launch'}).click();
  await expect(page.getByRole('dialog').getByText('110 + 160',{exact:true})).toBeVisible();
  await expect(page.getByRole('dialog').locator('details')).toHaveCount(4);
  await page.getByRole('button',{name:'Закрыть',exact:true}).click();
  await page.getByRole('button',{name:'Переключить язык'}).click();
  await expect(page.getByRole('heading',{name:'Workflow executions'})).toBeVisible();
  await page.getByRole('button').filter({hasText:'Mock portal launch'}).click();
  await expect(page.getByRole('heading',{name:'Final workflow result'})).toBeVisible();
  await page.screenshot({path:'test-results/workflow-result-en.png',fullPage:true});
});
