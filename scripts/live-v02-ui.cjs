const {chromium}=require('@playwright/test');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  await page.goto('http://127.0.0.1:3000/');
  await page.getByRole('button',{name:'Процессы',exact:true}).click();
  await page.getByRole('button').filter({hasText:'Технический план корпоративного портала'}).click();
  const dialog=page.getByRole('dialog');
  await dialog.getByRole('heading',{name:'Итоговый результат процесса',exact:true}).waitFor();
  await dialog.locator('details').nth(3).waitFor();
  await dialog.getByText('2646 + 1040',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Закрыть',exact:true}).click();
  await page.reload();
  await page.getByRole('button',{name:'Процессы',exact:true}).click();
  await page.getByRole('button').filter({hasText:'Технический план корпоративного портала'}).click();
  await dialog.getByRole('heading',{name:'Итоговый результат процесса',exact:true}).waitFor();
  await dialog.getByText('2646 + 1040',{exact:true}).waitFor();
  await dialog.locator('details').nth(3).waitFor();
  const content=await dialog.innerText();
  if(!content.includes('approve')||!content.includes('RBAC'))throw Error('Result not rendered');
  await page.screenshot({path:'docs/v02-live-ui.png'});
  const record=JSON.parse(fs.readFileSync('docs/v02-live-verification.json','utf8'));
  record.ui_after_reload={verified:true,steps:4,tokens:'2646 + 1040',result_visible:true};
  fs.writeFileSync('docs/v02-live-verification.json',JSON.stringify(record,null,2));
  console.log('UI PASS: final result, four persisted stages and tokens visible after reload; no launch clicked.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exit(1)});
