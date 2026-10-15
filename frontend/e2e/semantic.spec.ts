import {test,expect} from './authenticated-test';
import {resolve} from 'node:path';
test('v0.5 indexing, retrieval scores, mode persistence and RU/EN',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'База знаний',exact:true}).click();
 await page.getByLabel('Загрузить PDF').setInputFiles(resolve('../docs/fixtures/AgentOps_RAG_Test_Corporate_Policy.pdf'));
 const doc=page.locator('.task-row').filter({hasText:'AgentOps_RAG_Test_Corporate_Policy.pdf'});
 await expect(doc).toContainText('Векторы: Готов · 6/6',{timeout:20000});
 await doc.getByRole('button',{name:'Переиндексировать',exact:true}).click();await expect(doc).toContainText('Проверка индекса запущена.');
 await page.getByRole('navigation').getByRole('button',{name:/^Агенты(?: \d+)?$/}).click();await page.getByRole('button',{name:'Создать агента',exact:true}).first().click();
 await page.getByLabel('Название',{exact:true}).fill('Semantic E2E');await page.getByLabel('Системные инструкции').fill('Use permitted PDF data only.');
 await page.getByRole('dialog').getByLabel('Поиск знаний',{exact:true}).check();await page.getByRole('dialog').getByLabel('AgentOps_RAG_Test_Corporate_Policy.pdf',{exact:true}).check();await page.getByRole('button',{name:'Сохранить',exact:true}).click();
 await page.getByRole('button',{name:'База знаний',exact:true}).click();await page.getByLabel('Агент с доступом к документам').selectOption({label:'Semantic E2E'});
 await page.getByLabel('Вопрос по выбранным PDF',{exact:true}).fill('RPO RTO');
 for(const mode of ['lexical','semantic','hybrid']){await page.getByLabel('Режим поиска',{exact:true}).selectOption(mode);await page.getByRole('button',{name:'Проверить поиск',exact:true}).click();const results=page.getByRole('region',{name:'Результаты поиска'});await expect(results).toContainText('RPO');await expect(results).toContainText('Semantic:');await expect(results).toContainText(mode);}
 await page.screenshot({path:'test-results/v05-retrieval-ru.png',fullPage:true});
 await page.reload();await page.getByRole('button',{name:'База знаний',exact:true}).click();await expect(page.getByLabel('Режим поиска',{exact:true})).toHaveValue('hybrid');
 await page.getByRole('button',{name:'Переключить язык'}).click();await expect(page.getByLabel('Search mode',{exact:true})).toHaveValue('hybrid');await expect(doc).toContainText('Vectors: Ready · 6/6');
 await page.screenshot({path:'test-results/v05-retrieval-en.png',fullPage:true});
});
