// 첫 화면 '예제로 체험하기' E2E(실제 앱, AI 키 없이). 누르기만으로 프로젝트·AI 작업이 생기지 않는지, 예제 파일 내려받기,
// 완성 예시 1회 생성, 예제 C(가상 업체 문서 4종) 업로드 → 검토 실행 결과를 확인한다.
// 실행: 서버를 띄운 뒤 `E2E_PASSWORD=... node e2e/examples.cjs` (기본 주소 http://127.0.0.1:8000)
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const PW = process.env.E2E_PASSWORD;
const OUT = path.join(__dirname, "output");
fs.mkdirSync(OUT, { recursive: true });

function check(cond, msg) {
  if (!cond) throw new Error("확인 실패: " + msg);
  console.log("  ✓", msg);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ acceptDownloads: true, viewport: { width: 1400, height: 900 } });
  page.on("dialog", (d) => d.accept());
  const aiCalls = [];
  page.on("request", (r) => { if (/\/ai\/|\/analyze$|\/review\/run$/.test(r.url()) && r.method() === "POST") aiCalls.push(r.url()); });
  const projects = async () => (await (await page.request.get(BASE + "/api/projects")).json()).length;
  try {
    await page.goto(BASE + "/");
    await page.locator('input[type="password"]').fill(PW);
    await page.getByRole("button", { name: "로그인" }).click();
    await page.getByText("무엇을 하시겠어요?").waitFor();
    const n0 = await projects();

    // 예제 영역은 접혀 있고(시작 카드보다 덜 강조), 열면 세 예제가 보인다
    const ex = page.locator("details.examples");
    check(!(await ex.evaluate((e) => e.open)), "예제 영역 기본 접힘");
    await ex.locator("summary").click();
    for (const t of ["01 구상", "02 참고문서", "03 검토"]) check(await ex.getByText(t).isVisible(), `예제 ${t} 표시`);

    // A: 예제 값으로 시작 → 만들기 창만 채움(프로젝트 생성·AI 호출 없음)
    await ex.getByRole("button", { name: "예제 값으로 시작" }).click();
    const dlg = page.getByRole("dialog");
    check((await dlg.getByLabel("사업(프로젝트) 이름").inputValue()).startsWith("[예제]"), "A: 만들기 창에 예제 이름 채움");
    check((await dlg.getByLabel("목표 금액(원)").inputValue()) === "80,000,000", "A: 목표예산 예시 채움");
    await dlg.getByRole("button", { name: "닫기" }).last().click();
    check((await projects()) === n0 && aiCalls.length === 0, "A: 누르기만으로 프로젝트·AI 작업 없음");

    // 예제 파일 내려받기(같은 원본) — A·B·C
    for (const [name, needle] of [["입력 예시 받기", "교육과정 등록"], ["가상 타 기관 과업지시서 받기", "SFR-007"], ["기대 확인 목록", "탐지하지 못하는 것"]]) {
      const [d] = await Promise.all([page.waitForEvent("download"), ex.getByRole("link", { name }).click()]);
      const txt = fs.readFileSync(await d.path(), "utf-8");
      check(txt.includes(needle), `내려받기 '${name}' (${d.suggestedFilename()})`);
    }
    const [fpd] = await Promise.all([page.waitForEvent("download"), ex.getByRole("link", { name: "FP 산정표" }).click()]);
    check(fpd.suggestedFilename() === "vendor_fp.xlsx" && fs.statSync(await fpd.path()).size > 1000, "C: FP 산정표 엑셀 내려받기");

    // 완성 예시: 두 번 빨리 눌러도 1개만 생성(처리 중 비활성화), AI 호출 없음
    const sample = ex.getByRole("button", { name: "교육 신청·관리" });
    await Promise.all([sample.click(), sample.click({ trial: false }).catch(() => {})]);
    await page.waitForURL(/#\/p\/\w+\/overview/);
    check((await projects()) === n0 + 1, "완성 예시: 새 프로젝트 1개만 생성");
    await page.getByRole("heading", { name: /\[샘플\] 직원 교육 신청·관리 시스템/ }).waitFor();
    check(true, "완성 예시: 샘플 이름 표시");
    await page.reload();
    await page.getByText("STEP 1 / 7").waitFor();
    check((await projects()) === n0 + 1, "새로고침해도 샘플이 다시 생기지 않음");
    check(aiCalls.length === 0, "완성 예시 열기에서 AI·분석 요청 없음");

    // C: 기존 문서 검토하기 → 2 자료·질문에서 종류별 업로드 → 6 검토·추천 검토 실행
    await page.goto(BASE + "/#/");
    await page.getByRole("button", { name: /기존 문서 검토하기/ }).click();
    await page.getByLabel("사업(프로젝트) 이름").fill("[예제] 기존 문서 검토");
    await page.getByRole("button", { name: "만들기" }).click();
    await page.waitForURL(/#\/p\/\w+\/review/);
    const pid = page.url().match(/#\/p\/(\w+)/)[1];
    await page.getByRole("link", { name: "2 자료·질문" }).click();
    const files = [["vendor_task.txt", "vendor_task"], ["vendor_design.txt", "vendor_design"], ["vendor_fp.xlsx", "vendor_fp"], ["vendor_cost.txt", "vendor_cost"]];
    for (const [f, kind] of files) {
      const r = await page.request.get(`${BASE}/api/examples/C-review/${f}`);
      await page.getByLabel("문서 종류").selectOption(kind);
      await page.locator('input[type="file"]').first().setInputFiles({ name: f, mimeType: r.headers()["content-type"].split(";")[0], buffer: await r.body() });
      await page.getByText(f).first().waitFor();
    }
    check(true, "C: 가상 업체 문서 4종 종류별 업로드");
    await page.getByRole("link", { name: "6 검토·추천" }).click();
    await page.getByRole("button", { name: "검토 실행" }).click();
    await page.getByText("SFR-005").first().waitFor();
    const body = await page.locator("main").innerText();
    for (const t of ["요구사항 누락", "FP 가중치", "FP 중복", "FP 합계", "부가세", "범위 불명확"]) check(body.includes(t), `C: 검토 결과 '${t}'`);
    const proj = await (await page.request.get(`${BASE}/api/projects/${pid}`)).json();
    check(proj.project.documents.every((d) => ["vendor_task", "vendor_design", "vendor_fp", "vendor_cost"].includes(d.kind)), "C: 문서 종류 보존");
    await page.screenshot({ path: path.join(OUT, "examples-review.png"), fullPage: true });

    // 모바일 폭에서 예제 영역이 가로로 넘치지 않음
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto(BASE + "/#/");
    await page.locator("details.examples summary").click();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    check(!overflow, "모바일(390px)에서 가로 넘침 없음");
    await page.locator("details.examples summary").focus();
    check(await page.evaluate(() => document.activeElement?.tagName === "SUMMARY"), "키보드로 예제 영역에 접근");
    console.log("예제 E2E 통과");
  } catch (e) {
    await page.screenshot({ path: path.join(OUT, "examples-fail.png"), fullPage: true }).catch(() => {});
    console.error(e);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
