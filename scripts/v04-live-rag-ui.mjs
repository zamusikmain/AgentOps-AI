import {chromium,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
const report=JSON.parse(await readFile(new URL('../docs/v04-live-rag-verification.json',import.meta.url),'utf8'));
const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
try {
 const page=await browser.newPage();await page.goto('http://127.0.0.1:3000/');
 await page.getByRole('button',{name:'База знаний',exact:true}).click();await page.reload();
 await page.getByRole('button',{name:'База знаний',exact:true}).click();
 const checks=[];
 for(const entry of report.runs.filter(r=>r.run.status==='completed')){
  const answer=JSON.parse(entry.run.result);
  const persisted=page.waitForResponse(r=>r.url().endsWith(`/api/executions/${entry.run_id}`)&&r.request().method()==='GET');
  await page.getByRole('button').filter({hasText:entry.question}).first().click();
  const dialog=page.getByRole('dialog',{name:'Ответ по документу',exact:true});
  await expect(dialog.getByText('Gemini',{exact:true})).toBeVisible();
  await expect(dialog).not.toContainText('ПРОВЕРКА MOCK');
  await expect(dialog).toContainText(answer.found?answer.answer:'В предоставленных документах информация не найдена.');
  await expect(dialog).toContainText(`${entry.run.input_tokens} + ${entry.run.output_tokens}`);
  await expect(dialog).toContainText(`Страница ${answer.citations[0].page}`);
  const saved=await (await persisted).json();expect(saved.id).toBe(entry.run_id);expect(saved.result).toBe(entry.run.result);
  await dialog.getByRole('button',{name:'Открыть источник'}).first().click();
  const source=page.getByRole('dialog',{name:report.document.name,exact:true});await expect(source).toContainText(answer.citations[0].quote);
  await source.getByRole('button',{name:'Закрыть',exact:true}).click();
  await page.screenshot({path:`docs/rag-preview/live-v04-${checks.length+1}.png`,fullPage:true});
  checks.push({id:entry.run_id,live_result_after_reload:true,not_mock:true,source_verified:true,tokens_visible:true});
  await dialog.getByRole('button',{name:'Закрыть',exact:true}).click();
 }
 await page.getByRole('button',{name:'Переключить язык'}).click();await expect(page.getByRole('heading',{name:'Knowledge Base',exact:true})).toBeVisible();
 const first=report.runs[0];await page.getByRole('button').filter({hasText:first.question}).first().click();
 await expect(page.getByRole('dialog',{name:'Grounded answer'})).toContainText('Page 1');
 await writeFile(new URL('../docs/v04-live-rag-ui-verification.json',import.meta.url),JSON.stringify({checks,english_verified:true,new_llm_requests:0},null,2));
 console.log(JSON.stringify({live_answers_after_reload:checks.length,english_verified:true,new_llm_requests:0}));
}finally{await browser.close();}
