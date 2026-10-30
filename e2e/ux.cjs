// UI contracts on both builds; no server-side values or calculations are mocked.
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path'), assert = require('assert/strict');
const out = path.join(__dirname, 'output', 'ux'); fs.mkdirSync(out, { recursive:true });
const root = path.resolve(__dirname, '../frontend/dist-demo');
const server = http.createServer((req,res) => {
  const rel = decodeURIComponent(req.url.split('?')[0]).replace(/^\/cj-sw-design\//,'') || 'index.html';
  const file=path.resolve(root,rel); if(!file.startsWith(root+path.sep)||!fs.existsSync(file)||fs.statSync(file).isDirectory()) return res.writeHead(404).end();
  const type={'.js':'text/javascript','.css':'text/css','.json':'application/json','.html':'text/html'}[path.extname(file)] || 'application/octet-stream';
  res.writeHead(200,{'Content-Type':type});fs.createReadStream(file).pipe(res);
});
(async()=>{
 await new Promise(r=>server.listen(4175,'127.0.0.1',r));
 const browser=await chromium.launch();
 try {
  const page=await browser.newPage(); const errors=[], bad=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error') errors.push(m.text());});
  page.on('response',r=>{if(r.status()>=400)bad.push(r.url());});page.on('request',r=>requests.push(r.url()));
  const base='http://127.0.0.1:4175/cj-sw-design/';
  for(const width of [1400,820,390]) {
   await page.setViewportSize({width,height:900}); await page.goto(base);await page.getByText('샘플을 골라 둘러보세요').waitFor();
   await page.screenshot({path:path.join(out,`demo-home-${width}.png`),fullPage:true});
   for(const pid of ['sampleA','sampleB']) for(const step of ['overview','sources','requirements','design','fp','review','excel']) {
    await page.goto(`${base}#/p/${pid}/${step}`);await page.locator('.step-intro').waitFor();
    assert.equal(await page.locator('[aria-current="step"]').count(),1);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${pid}/${step} overflows ${width}`);
    if(step==='requirements') {
     const table=page.locator('.table-wrap').last(); const rows=await table.locator('tbody tr').count();
     await table.getByRole('button',{name:'확정',exact:true}).click();
     assert((await table.locator('tbody .badge-st-draft').count())===0);
     await table.getByRole('button',{name:'전체',exact:true}).click();assert.equal(await table.locator('tbody tr').count(),rows);
     const trigger=table.getByRole('button',{name:/상세 보기/}).first();await trigger.click();await page.getByRole('dialog').waitFor();
     await page.keyboard.press('Tab');assert(await page.evaluate(()=>!!document.activeElement.closest('dialog')));
     await page.screenshot({path:path.join(out,`detail-${pid}-${width}.png`)});
     await page.keyboard.press('Escape');assert.equal(await page.getByRole('dialog').count(),0);assert(await trigger.evaluate(e=>e===document.activeElement));
     await table.getByRole('textbox',{name:'표 검색'}).fill('no-matching-item-9283');await page.getByText(/검색 조건에 맞는 항목이 없습니다/).waitFor();
    }
    if(step==='fp')await page.screenshot({path:path.join(out,`${pid}-fp-${width}.png`),fullPage:true});
   }
  }
  assert.equal(errors.length,0,errors.join('\n'));assert.equal(bad.length,0,bad.join('\n'));
  assert(requests.every(u=>u.startsWith(base)||u.startsWith('data:')||u.startsWith('blob:')),'external or API request');
  // Actual loading and fetch error: delay a static result, then a failed project load with recovery.
  let release;const gate=new Promise(r=>release=r);
  await page.route('**/sampleA/project.json',async route=>{await gate;await route.continue();});
  await page.goto(`${base}#/p/sampleA/overview`);await page.getByRole('status',{name:'불러오는 중'}).waitFor();
  await page.screenshot({path:path.join(out,'loading.png')});release();await page.locator('.step-intro').waitFor();await page.unrouteAll();
  await page.route('**/sampleB/project.json',r=>r.abort());await page.goto(`${base}#/p/sampleB/overview`);await page.getByRole('button',{name:'다시 불러오기'}).waitFor();
  await page.screenshot({path:path.join(out,'error.png')});await page.unrouteAll();await page.getByRole('button',{name:'다시 불러오기'}).click();await page.locator('.step-intro').waitFor();
  console.log('Pages: A/B × 7 steps × 3 widths; filters, detail sheet, focus/Esc/return, empty/loading/error/retry, no unexpected requests/errors passed');
  const live=await browser.newPage();const liveErrors=[];live.on('pageerror',e=>liveErrors.push(e.message));
  const app=process.env.BASE_URL || 'http://127.0.0.1:8001';await live.goto(app);await live.getByLabel('비밀번호',{exact:true}).fill(process.env.E2E_PASSWORD);await live.getByRole('button',{name:'로그인',exact:true}).click();await live.getByText('무엇을 하시겠어요?').waitFor();
  for(const width of [1400,820,390]) {
   await live.setViewportSize({width,height:900});await live.screenshot({path:path.join(out,`app-home-${width}.png`),fullPage:true});
   const trigger=live.getByRole('button',{name:'구상으로 시작하기'});await trigger.click();await live.getByRole('dialog').waitFor();await live.keyboard.press('Escape');assert(await trigger.evaluate(e=>e===document.activeElement));
  }
  // 대화상자 안쪽 여백 클릭은 닫지 않고(입력 보존), 바깥(backdrop) 클릭만 닫는다(PR #5 리뷰 지적)
  await live.getByRole('button',{name:'구상으로 시작하기'}).click();const dlg=live.getByRole('dialog');await dlg.waitFor();
  await live.getByPlaceholder('예: 직원 교육 신청·관리 시스템 구축').fill('여백 클릭 보존');const box=await dlg.boundingBox();
  await live.mouse.click(box.x+6,box.y+box.height-6);assert(await dlg.isVisible(),'안쪽 여백 클릭에 대화상자가 닫힘');
  assert.equal(await live.getByPlaceholder('예: 직원 교육 신청·관리 시스템 구축').inputValue(),'여백 클릭 보존');
  await live.mouse.click(5,5);await dlg.waitFor({state:'hidden'});
  await live.getByRole('button',{name:'구상으로 시작하기'}).click();await live.getByPlaceholder('예: 직원 교육 신청·관리 시스템 구축').fill('반응형 긴 프로젝트 이름 '.repeat(8));await live.getByRole('button',{name:'만들기',exact:true}).click();await live.locator('.step-intro').waitFor();
  await live.getByRole('link',{name:/^1 개요/}).click();await live.getByPlaceholder('예: 교육관리시스템').fill('테스트 시스템');await live.getByText('저장하지 않은 변경이 있습니다.',{exact:false}).waitFor();
  await live.getByRole('button',{name:'저장',exact:true}).first().click();await live.getByText('저장했습니다.',{exact:false}).waitFor();
  await live.screenshot({path:path.join(out,'app-saved-mobile.png'),fullPage:true});await live.reload();await live.getByPlaceholder('예: 교육관리시스템').waitFor();assert.equal(await live.getByPlaceholder('예: 교육관리시스템').inputValue(),'테스트 시스템');
  await live.getByRole('link',{name:/^3 요구사항/}).click();await live.getByText('아직 항목이 없습니다.',{exact:false}).waitFor();
  assert(await live.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.equal(liveErrors.length,0,liveErrors.join('\n'));
  console.log('App: responsive home, creation dialog/Esc/focus, long title, unsaved warning, save feedback, reload, empty state passed');
 } finally {await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
