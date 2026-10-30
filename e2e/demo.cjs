// 정적 시연판(GitHub Pages) 브라우저 E2E — 백엔드 없이 정적 파일만 제공해 확인한다.
// 실행: (cd frontend && npm run demo:data && npm run build:demo) 후 `node e2e/demo.cjs`
//   DEMO_DIST(기본 frontend/dist-demo)를 /cj-sw-design/ 아래에 그대로 제공하는 정적 서버를 이 스크립트가 직접 띄운다.
// 확인: 로그인 없이 진입, 샘플 A·B 7단계, FP·개발비·검토의견, 샘플 엑셀 내려받기, 하위 경로·단계 주소 새로고침,
//       모바일·태블릿 너비, 콘솔 오류·404, /api 요청 0건, 정적 서버 밖(외부) 요청 0건.
const { chromium } = require("playwright");
const fs = require("fs");
const http = require("http");
const path = require("path");

const DIST = path.resolve(process.env.DEMO_DIST || path.join(__dirname, "..", "frontend", "dist-demo"));
const BASE_PATH = "/cj-sw-design/";
const PORT = Number(process.env.DEMO_PORT || 4174);
const ORIGIN = `http://127.0.0.1:${PORT}`;
const URL0 = ORIGIN + BASE_PATH;
const OUT = path.join(__dirname, "output");
fs.mkdirSync(OUT, { recursive: true });

const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document" };
const served = [];
const server = http.createServer((req, res) => {
  const u = new URL(req.url, ORIGIN);
  served.push(u.pathname);
  if (!u.pathname.startsWith(BASE_PATH)) {
    res.writeHead(404).end("not found");
    return;
  }
  let rel = decodeURIComponent(u.pathname.slice(BASE_PATH.length)) || "index.html";
  const file = path.join(DIST, rel);
  if (!file.startsWith(DIST) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404).end("not found");
    return;
  }
  res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" });
  fs.createReadStream(file).pipe(res);
});

function check(cond, msg) {
  if (!cond) throw new Error("확인 실패: " + msg);
  console.log("  ✓", msg);
}

(async () => {
  if (!fs.existsSync(path.join(DIST, "index.html"))) throw new Error(`${DIST}에 시연 빌드가 없습니다(npm run build:demo).`);
  await new Promise((r) => server.listen(PORT, "127.0.0.1", r));
  const browser = await chromium.launch();
  const requests = [];
  const failures = [];
  const consoleErrors = [];
  const watch = (page) => {
    page.on("request", (r) => requests.push(r.url()));
    page.on("response", (r) => r.status() >= 400 && failures.push(`${r.status()} ${r.url()}`));
    page.on("requestfailed", (r) => failures.push(`실패 ${r.url()} ${r.failure()?.errorText}`));
    page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
    page.on("pageerror", (e) => consoleErrors.push(String(e)));
    page.on("dialog", (d) => d.dismiss());
  };
  const ctx = await browser.newContext({ acceptDownloads: true, viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();
  watch(page);
  const shot = (n, p = page) => p.screenshot({ path: path.join(OUT, `demo-${n}.png`), fullPage: true });
  const banner = "샘플 시연판 — 가상 데이터로 기능 흐름과 결과를 보여줍니다. 실제 AI 호출·문서 분석·서버 저장은 수행하지 않습니다.";
  try {
    // 1. 로그인 없이 진입
    await page.goto(URL0);
    await page.getByText("샘플을 골라 둘러보세요").waitFor();
    check(await page.locator(".demo-banner summary").isVisible(), "상단 시연판 안내 문구 표시");
    check((await page.locator('input[type="password"]').count()) === 0, "로그인 없이 진입(비밀번호 입력 없음)");
    check(await page.getByText("정적 시연판 · 서버·AI 없음").isVisible(), "정적 시연판 표시(실제 앱 '샘플 모드'와 구분)");
    check((await page.locator('input[type="file"]').count()) === 0, "파일 업로드 입력 없음");
    await shot("01-home");
    const [hdl] = await Promise.all([page.waitForEvent("download"), page.locator(".demo-card", { hasText: "A. 구상 기반" }).getByRole("link", { name: /샘플 엑셀 다운로드/ }).click()]);
    check(/^SAMPLE-A_.*\.xlsx$/.test(hdl.suggestedFilename()), `첫 화면 샘플 엑셀 다운로드 이름 ${hdl.suggestedFilename()}`);

    // 2. 샘플 A — 7단계
    await page.locator(".demo-card", { hasText: "A. 구상 기반" }).getByRole("link", { name: "둘러보기" }).click();
    await page.getByRole("heading", { name: "[샘플] 직원 교육 신청·관리 시스템" }).waitFor();
    check(await page.locator(".demo-banner summary").isVisible(), "단계 화면에서도 안내 문구 유지");
    check(await page.getByRole("button", { name: "저장" }).first().isDisabled(), "① 개요: 저장 버튼 비활성화");
    check((await page.getByText("프로젝트 삭제").count()) === 0, "① 개요: 삭제 기능 숨김");
    await shot("A1-overview");

    await page.getByRole("link", { name: "2 자료·질문" }).click();
    await page.getByRole("button", { name: /답한 질문 \d+개 보기/ }).click();
    check(await page.getByText("모름 → 권장안 가정").first().isVisible(), "② 질문 답변 예시(모름→권장안 가정)");
    check(await page.getByRole("button", { name: /질문 받기|다음 질문 더 받기/ }).isDisabled(), "② 질문 받기(AI 실행) 비활성화");
    check(await page.getByText("가상_업체_FP산정표.xlsx").isVisible(), "② 미리 올린 가상 업체 문서 표시");
    await shot("A2-sources");

    await page.getByRole("link", { name: "3 요구사항" }).click();
    await page.getByText("요구사항 목록").waitFor();
    const reqTable = page.locator(".card", { hasText: "요구사항 목록" });
    check((await reqTable.locator(".badge-or-user").count()) >= 2 && (await reqTable.locator(".badge-or-sample").count()) >= 1, "③ 사용자 요구와 규칙 제안 출처 구분");
    check((await reqTable.getByRole("button", { name: "수정" }).count()) === 0, "③ 표 수정·삭제 버튼 숨김");
    check(await page.getByRole("button", { name: "요구사항 초안 만들기" }).isDisabled(), "③ 초안 만들기 비활성화");

    await page.getByRole("link", { name: "4 설계" }).click();
    for (const t of ["기능설계", "화면", "데이터", "연계"]) {
      await page.locator(".tabs button", { hasText: t }).first().click();
      check((await page.locator("table.grid tbody tr").count()) >= 1, `④ ${t} 표 표시`);
    }
    await page.locator(".tabs button", { hasText: "스냅샷·변경이력" }).click();
    await page.getByRole("button", { name: "현재와 비교" }).first().click();
    await page.getByRole("columnheader", { name: "변경(변경 전 → 후)" }).waitFor();
    check(true, "④ 스냅샷 비교(정적 데이터)");
    await shot("A4-design");

    await page.getByRole("link", { name: "5 FP·개발비" }).click();
    await page.getByText("FP 집계(확정 항목)").waitFor();
    const kpi = await page.locator(".kpi").first().innerText();
    check(/간이법\s*[\d.]+ FP/.test(kpi), `⑤ FP 집계: ${kpi.replace(/\s+/g, " ")}`);
    check(await page.getByText("직원이 입력한 만족도를 신청 정보(ILF)에 기록하는 외부 입력").isVisible(), "⑤ FP 분류 근거 표시");
    check(await page.getByRole("cell", { name: "총액(부가세 포함)" }).first().isVisible(), "⑤ 기준 산정 총액 표시");
    check(await page.getByText("예산 조정 결과(참고, 공식 측정값 아님)").first().isVisible(), "⑤ 목표예산 시나리오(참고) 표시");
    check(await page.getByRole("button", { name: "기준 산정 실행·저장" }).isDisabled(), "⑤ 기준 산정 실행 비활성화");
    await shot("A5-fp");

    await page.getByRole("link", { name: "6 검토·추천" }).click();
    await page.getByText("기존 문서 검토(대조)").waitFor();
    check(await page.locator(".badge-v-diff").first().isVisible() && (await page.locator(".badge-v-match").count()) > 0, "⑥ 검토의견(차이·일치) 표시");
    check(await page.getByText("부가세가 공급가액의 10%와 다릅니다.").isVisible(), "⑥ 금액 검토 결과 표시");
    check((await page.locator(".card", { hasText: "HW·SW 구성 추천" }).locator("tbody tr").count()) >= 3, "⑥ HW·SW 구성 추천 표시");
    await shot("A6-review");

    await page.getByRole("link", { name: "7 엑셀" }).click();
    await page.getByRole("button", { name: "개발비_기준" }).click();
    await page.getByRole("cell", { name: "총액(부가세 포함)", exact: true }).waitFor();
    check(true, "⑦ 엑셀 미리보기(개발비_기준)");
    const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: /샘플 엑셀 내려받기/ }).click()]);
    const xfile = path.join(OUT, "demo-sampleA.xlsx");
    await dl.saveAs(xfile);
    const buf = fs.readFileSync(xfile);
    check(buf.slice(0, 2).toString() === "PK" && buf.length > 5000 && /^SAMPLE-A_.*\.xlsx$/.test(dl.suggestedFilename()), `⑦ 샘플 엑셀 내려받기 ${buf.length} bytes (${dl.suggestedFilename()})`);
    check(dl.url().startsWith(URL0 + "demo-data/"), "⑦ 다운로드가 정적 파일(/api 아님)");
    await shot("A7-excel");

    // 3. 단계 주소 직접 접속·새로고침
    await page.goto(URL0 + "#/p/sampleA/fp");
    await page.reload();
    await page.getByText("FP 집계(확정 항목)").waitFor();
    check(true, "단계 주소(#/p/sampleA/fp) 직접 접속·새로고침");

    // 4. 샘플 B — 참고문서
    await page.getByRole("link", { name: "처음으로" }).click();
    await page.locator(".demo-card", { hasText: "B. 참고문서 기반" }).getByText("단계 바로가기", { exact: true }).click();
    await page.locator(".demo-card", { hasText: "B. 참고문서 기반" }).getByRole("link", { name: /② 자료·질문/ }).click();
    await page.getByText("참고문서 항목 — 우리 기관 기준으로 유지·수정·제외").waitFor();
    const ref = page.locator(".card", { hasText: "참고문서 항목 — 우리 기관 기준으로" });
    await ref.getByLabel(/결정 대기만 보기/).uncheck();
    check(await ref.getByText(/문단\d+/).first().isVisible(), "B② 원문 추출 위치(문단) 표시");
    check(await ref.getByText(/수정 후: .*2일 전까지 취소/).isVisible(), "B② 우리 사업에 맞춘 수정 예시");
    check(await ref.getByText("특정 제품 지정은 우리 사업에서 하지 않음").isVisible(), "B② 제외 예시와 이유");
    check(await ref.getByText(/타 기관 고유 조건/).first().isVisible(), "B② 타 기관 고유 조건 경고");
    check(await page.getByRole("link", { name: "원본(가상 문서)" }).isVisible(), "B② 원본 가상 문서 링크(정적 파일)");
    await shot("B2-sources");
    await page.getByRole("link", { name: "3 요구사항" }).click();
    await page.locator(".proposal").first().waitFor();
    check(await page.getByRole("button", { name: /선택 \d+건 적용/ }).isDisabled(), "B③ 검토 대기 변경안 표시·적용 비활성화");
    await page.getByRole("link", { name: "4 설계" }).click();
    await page.locator(".tabs button", { hasText: "연계" }).click();
    check(await page.getByText("확인 필요(결제 API 호출 또는 결제 화면 이동)").isVisible(), "B④ 확인이 필요한 연계 조건");
    await page.getByRole("link", { name: "5 FP·개발비" }).click();
    await page.getByText("FP 집계(확정 항목)").waitFor();
    check(await page.getByText(/중복 의심/).first().isVisible(), "B⑤ 중복 의심 표시");
    check(await page.getByText(/미확정 FP 항목 \d+건은 기준 산정에서 제외됨/).first().isVisible(), "B⑤ 미확정 FP 제외 경고");
    await shot("B5-fp");

    // 5. 샘플 초기화·처음으로
    await page.getByRole("button", { name: "샘플 초기화" }).click();
    await page.waitForFunction(() => location.hash.endsWith("/overview"));
    check(true, "샘플 초기화 → 개요로 다시 불러오기");
    await page.getByRole("link", { name: "처음으로" }).click();
    await page.getByText("샘플을 골라 둘러보세요").waitFor();
    check(true, "처음으로");

    // 6. 모바일·태블릿 너비
    for (const [name, w, h] of [["mobile", 390, 844], ["tablet", 820, 1180]]) {
      const p = await ctx.newPage();
      watch(p);
      await p.setViewportSize({ width: w, height: h });
      await p.goto(URL0);
      await p.getByText("샘플을 골라 둘러보세요").waitFor();
      const over = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      check(over <= 1, `${name}(${w}px) 첫 화면 가로 넘침 없음`);
      await p.goto(URL0 + "#/p/sampleB/fp");
      await p.getByText("FP 집계(확정 항목)").waitFor();
      const over2 = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      check(over2 <= 1, `${name}(${w}px) FP 화면 가로 넘침 없음(표는 표 안에서 스크롤)`);
      check(await p.locator(".demo-banner summary").isVisible(), `${name} 안내 문구 표시`);
      await p.getByRole("link", { name: "6 검토·추천" }).click();
      await p.getByText("기존 문서 검토(대조)").waitFor();
      await shot(`${name}-review`, p);
      await p.close();
    }

    // 7. 네트워크·콘솔
    const external = requests.filter((u) => !u.startsWith(ORIGIN + BASE_PATH) && !u.startsWith("blob:") && !u.startsWith("data:"));
    const apiCalls = requests.filter((u) => new URL(u).pathname.startsWith("/api") || u.includes("/api/"));
    const ai = requests.filter((u) => /openai|anthropic/i.test(u));
    check(apiCalls.length === 0, `/api 요청 0건 (전체 요청 ${requests.length}건)`);
    check(ai.length === 0, "외부 AI(OpenAI·Anthropic) 요청 0건");
    check(external.length === 0, `정적 서버 밖 요청 0건${external.length ? ": " + external.slice(0, 5).join(", ") : ""}`);
    check(failures.length === 0, `404·실패 응답 0건${failures.length ? ": " + failures.slice(0, 5).join(", ") : ""}`);
    check(consoleErrors.length === 0, `콘솔 오류 0건${consoleErrors.length ? ": " + consoleErrors.slice(0, 3).join(" | ") : ""}`);
    check(served.every((p) => p.startsWith(BASE_PATH)), "모든 파일이 /cj-sw-design/ 하위 경로에서 로드됨");
    console.log("시연판 E2E 통과");
  } catch (e) {
    await shot("zz-failure").catch(() => {});
    console.error(e);
    console.error("요청 실패:", failures.slice(0, 10), "콘솔 오류:", consoleErrors.slice(0, 5));
    process.exitCode = 1;
  } finally {
    await browser.close();
    server.close();
  }
})();
