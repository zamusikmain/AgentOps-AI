import {chromium,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
const report=JSON.parse(await readFile(new URL('../docs/rag-verification.json',import.meta.url),'utf8'));
const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
try {
 const page=await browser.newPage();await page.goto('http://127.0.0.1:3000/');
 await page.getByRole('button',{name:'База знаний',exact:true}).click();
 await expect(page.getByRole('heading',{name:report.document.name,exact:true})).toBeVisible();
 await page.reload();await page.getByRole('button',{name:'База знаний',exact:true}).click();
 const checks=[];
 for(const run of report.runs){
  await page.getByRole('button').filter({hasText:run.answer.question}).click();
  const dialog=page.getByRole('dialog');await expect(dialog).toContainText('ПРОВЕРКА MOCK');
  await expect(dialog).toContainText(`Страница ${run.answer.citations[0].page}`);
  await expect(dialog).toContainText(run.answer.found?run.answer.citations[0].quote:'В предоставленных документах информация не найдена.');
  await expect(dialog).toContainText(`${run.input_tokens_mock_estimate} + ${run.output_tokens_mock_estimate}`);
  await page.screenshot({path:`docs/rag-preview/ui-${checks.length+1}.png`,fullPage:true});
  checks.push({id:run.id,answer_visible_after_reload:true,source_page_visible:true,mock_label_visible:true,tokens_visible:true});
  await dialog.getByRole('button',{name:'Закрыть',exact:true}).click();
 }
 await page.getByRole('button',{name:'Переключить язык'}).click();await expect(page.getByRole('heading',{name:'Knowledge Base',exact:true})).toBeVisible();
 await writeFile(new URL('../docs/rag-ui-verification.json',import.meta.url),JSON.stringify({base_url:'http://127.0.0.1:3000',real_llm_requests:0,checks,english_screen_verified:true},null,2));
 console.log(JSON.stringify({saved_answers_verified:checks.length,real_llm_requests:0,english_screen_verified:true}));
} finally {await browser.close();}
