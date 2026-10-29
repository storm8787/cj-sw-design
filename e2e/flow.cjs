// 실제 브라우저 E2E: 로그인 → 프로젝트 생성 → 질문 답변 → 요구사항 입력·편집 → 설계 → FP 확정 → 기준 산정·목표예산 → 저장 확인(새로고침) → 엑셀 다운로드.
// 실행: 서버를 띄운 뒤 `E2E_PASSWORD=... node e2e/flow.cjs` (기본 주소 http://127.0.0.1:8000)
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
  const shot = (n) => page.screenshot({ path: path.join(OUT, `${n}.png`), fullPage: true });
  try {
    // 1. 로그인(미로그인 상태 차단 확인 포함)
    await page.goto(BASE + "/");
    await page.getByText("관리자 비밀번호로 로그인하세요").waitFor();
    check(true, "미로그인 시 로그인 화면 표시");
    await page.locator('input[type="password"]').fill("wrong-password");
    await page.getByRole("button", { name: "로그인" }).click();
    await page.getByText("비밀번호가 맞지 않습니다").waitFor();
    await page.locator('input[type="password"]').fill(PW);
    await page.getByRole("button", { name: "로그인" }).click();
    await page.getByText("무엇을 하시겠어요?").waitFor();
    check(await page.getByText("샘플 모드(규칙 기반, AI 아님)").isVisible(), "샘플 모드 표시");
    await shot("01-home");

    // 2. 새 설계 프로젝트 생성
    await page.getByRole("button", { name: /새 설계/ }).click();
    await page.getByPlaceholder("예: 직원 교육 신청·관리 시스템 구축").fill("E2E 교육 신청·관리");
    await page.getByPlaceholder("예: 교육 신청·관리 프로그램이 필요하다").fill("교육 신청·관리 프로그램이 필요하다");
    await page.getByRole("button", { name: "만들기" }).click();
    await page.getByText("질문으로 구체화하기").waitFor();

    // 3. 질문 받기 → 답변(선택·모름)
    await page.getByRole("button", { name: "질문 받기" }).click();
    await page.locator(".question").first().waitFor();
    const nQ = await page.locator(".question").count();
    check(nQ >= 1 && nQ <= 5, `질문 ${nQ}개(소수씩)`);
    await page.locator(".question").first().getByRole("button", { name: /\(권장\)/ }).click();
    await page.waitForTimeout(400);
    await page.locator(".question").first().getByRole("button", { name: /모름/ }).click();
    await page.waitForTimeout(400);
    await shot("02-questions");

    // 4. 개요: 경계 지정
    await page.getByRole("link", { name: "1 개요" }).click();
    await page.getByPlaceholder("예: 교육관리시스템").fill("교육관리시스템");
    await page.getByRole("button", { name: "저장" }).first().click();
    await page.getByText("저장했습니다.").waitFor();

    // 5. 요구사항 입력 → 초안 → 적용
    await page.getByRole("link", { name: "3 요구사항" }).click();
    await page.getByLabel("기능 입력").fill("교육 신청: 직원이 신청기간 내 신청\n신청 취소\n신청 승인·반려\n대기자 자동 승계\n과정별 이수 통계");
    await page.getByRole("button", { name: "요구사항 초안 만들기" }).click();
    await page.locator(".proposal").first().waitFor();
    const applyBtns = page.getByRole("button", { name: /선택 \d+건 적용/ });
    while ((await applyBtns.count()) > 0) {
      await applyBtns.first().click();
      await page.waitForTimeout(500);
    }
    const reqRows = await page.locator("table.grid tbody tr").count();
    check(reqRows >= 5, `요구사항 ${reqRows}건 표시`);
    // 표 직접 수정
    await page.locator("table.grid tbody tr").first().getByRole("button", { name: "수정" }).click();
    await page.getByLabel("검수 기준").first().fill("신청 결과가 목록에 즉시 표시됨");
    await page.getByLabel("상태").first().selectOption("confirmed");
    await page.locator("tr.editing").getByRole("button", { name: "저장" }).click();
    await page.getByText("신청 결과가 목록에 즉시 표시됨").waitFor();
    check(true, "요구사항 표 직접 수정·확정");
    await shot("03-requirements");

    // 6. 설계 초안 → 적용
    await page.getByRole("link", { name: "4 설계" }).click();
    await page.getByRole("button", { name: "요구사항으로 설계 초안 만들기" }).click();
    await page.locator(".proposal").first().waitFor();
    await page.getByRole("button", { name: /선택 \d+건 적용/ }).first().click();
    await page.waitForTimeout(600);
    check((await page.locator("table.grid tbody tr").count()) >= 5, "기능설계 반영");
    await shot("04-design");

    // 7. FP 후보 → 적용 → 1건 확정(DET/FTR 입력)
    await page.getByRole("link", { name: "5 FP·개발비" }).click();
    await page.getByRole("button", { name: "기능·데이터로 FP 후보 만들기" }).click();
    await page.locator(".proposal").first().waitFor();
    await page.getByRole("button", { name: /선택 \d+건 적용/ }).first().click();
    await page.waitForTimeout(800);
    const fpTable = page.locator(".card", { hasText: "FP 항목 표" });
    const fpCount = await fpTable.locator("tbody tr").count();
    check(fpCount >= 3, `FP 후보 ${fpCount}건 적용(초안)`);
    for (let i = 0; i < Math.min(fpCount, 4); i++) {
      const row = fpTable.locator("tbody tr").nth(i);
      await row.getByRole("button", { name: "수정" }).click();
      const ed = fpTable.locator("tr.editing");
      const typeSel = ed.getByLabel("유형");
      if ((await typeSel.inputValue()) === "__null") await typeSel.selectOption("EI");
      await ed.getByLabel("FTR/RET").fill("1");
      await ed.getByLabel("DET").fill("10");
      await ed.getByLabel("상태").selectOption("confirmed");
      await ed.getByRole("button", { name: "저장" }).click();
      await page.waitForTimeout(500);
    }
    const kpi = await page.locator(".kpi").first().innerText();
    check(!/\b0 FP/.test(kpi), `확정 FP 집계: ${kpi.replace(/\n/g, " ")}`);

    // 8. 기준 산정 → 목표예산 시나리오
    await page.getByRole("button", { name: "기준 산정 실행·저장" }).click();
    await page.getByText("총액(부가세 포함)").first().waitFor();
    await page.getByLabel("목표 금액").fill("50000000");
    await page.getByRole("button", { name: "시나리오 만들기" }).click();
    await page.getByText("예산 조정 결과(참고, 공식 측정값 아님)").waitFor();
    check(await page.getByText("50,000,000원 · 목표액 일치").isVisible(), "목표예산 시나리오 목표액 일치");
    await shot("05-fp-cost");

    // 9. 새로고침 후에도 저장 유지
    await page.reload();
    await page.getByText("기준 산정(견적 버전)").waitFor();
    check(await page.getByText("EST-001").first().isVisible(), "새로고침 후 견적 버전 유지");

    // 10. 엑셀 미리보기·다운로드
    await page.getByRole("link", { name: "7 엑셀" }).click();
    await page.getByRole("button", { name: "개발비_기준" }).click();
    await page.getByRole("cell", { name: "총액(부가세 포함)", exact: true }).waitFor();
    await shot("06-excel");
    const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: /엑셀 내려받기/ }).click()]);
    const file = path.join(OUT, "e2e.xlsx");
    await dl.saveAs(file);
    const size = fs.statSync(file).size;
    check(size > 5000, `엑셀 다운로드 ${size} bytes`);
    console.log("E2E 통과");
  } catch (e) {
    await shot("zz-failure").catch(() => {});
    console.error(e);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
