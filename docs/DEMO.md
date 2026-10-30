# DEMO — GitHub Pages 샘플 시연판

서버·API 키 없이 **가상 샘플로 화면과 결과물을 둘러보는 정적 시연판**이다. 실제 기능을 쓰는 웹앱(서버)은 Render 배포(`docs/DEPLOY.md`, 다음 작업)로 따로 제공한다.

- 예상 주소: `https://storm8787.github.io/cj-sw-design/` (프로젝트 Pages 경로 `/cj-sw-design/`)
- 2026-10-30 첫 배포 완료(PR #4 병합 후 Actions run 40983396985). 최신 상태는 `docs/HANDOFF.md` §1.

## 1. 무엇을 보여 주나

| 샘플 | 시작 방식 | 성격 | 보여 주는 것 |
|---|---|---|---|
| A. 직원 교육 신청·관리 시스템 (`#/p/sampleA/…`) | 구상 기반 | 정상 완료 | 질문·답변(선택·모름→가정·나중에), 사용자 요구 vs 규칙 제안(적용·거절 이력), 설계·ID 연결, FP 분류 근거·점수, 기준 산정·목표예산 시나리오, 가상 업체 문서 대조 검토, HW·SW 추천, 엑셀 |
| B. 공공시설 예약 관리 시스템 (`#/p/sampleB/…`) | 참고문서 기반(가상 과업지시서) | 검토 필요 | 원문·추출 위치(문단), 타 기관 조건 표시, 유지·수정·제외와 이유, 결정 대기, 미확정·미분류 FP, 중복 의심, 연계 '확인 필요', 미답변 질문, 검토 대기 변경안 |

7단계(① 개요 ② 자료·질문 ③ 요구사항 ④ 설계 ⑤ FP·개발비 ⑥ 검토·추천 ⑦ 엑셀)를 실제 앱과 **같은 화면 코드**로 읽기 전용 표시한다.

### 시연판의 규칙
- 상단에 짧은 ‘샘플 시연판 · 저장 없이 둘러보기’를 지속 표시하고, 펼치면 실제 AI 호출·분석·저장 불가 안내를 제공한다.
- 로그인 없음. 파일 업로드·API 키 입력·서버 저장 기능 없음. 저장·AI 실행·업로드·삭제 버튼은 비활성화(마우스를 올리면 이유 표시), 표의 추가·수정·삭제는 숨김.
- 실제 앱의 **샘플 모드**(AI 키가 없을 때 서버가 규칙으로 질문·초안 생성)와 다르다: 시연판은 그 결과를 미리 저장해 둔 정적 화면이며 브라우저에서 아무것도 계산·생성하지 않는다. 진행 시간·토큰·완료 메시지를 꾸미지 않는다.
- 내려받는 엑셀·원본 문서·백업은 미리 만든 가상 파일(`SAMPLE-A_…`, `SAMPLE-B_…`)이며, 엑셀 첫 시트 제목 줄과 파일 속성에 '샘플 시연판(가상 데이터)'이 찍혀 있다.
- 첫 화면 **예제로 체험하기**에서 실제 앱과 같은 예제 파일(`examples/` 원본, 예제 C의 FP 산정표는 엑셀로 변환)을 내려받을 수 있다. 시연판에서는 올리기·실행이 되지 않으므로 예제 B·C는 실제 앱이나 내 PC 실행에서 해 본다. 파일은 `demo_data.py`가 `frontend/demo-public/demo-data/examples/`로 복사한다(커밋하지 않음).
- '샘플 초기화'는 화면에서 바꾼 탭·필터·선택을 지우고 샘플을 다시 불러온다(서버 저장 없음). '처음으로'는 샘플 선택 화면으로 돌아간다.

## 2. 구조(DECISIONS D-020)

```
backend/tools/demo_data.py  ── 개발·빌드 단계에서만 실행(서버 앱을 임시 폴더로 띄워 실제 API·계산 엔진·엑셀 생성기로 샘플 생성)
        │ frontend/demo-public/demo-data/  (커밋하지 않음 — 빌드 때마다 생성)
        │   manifest.json, system.json, sampleA/, sampleB/  (project.json, fp.json, estimate-preview.json,
        │   preview-*.json, changes.json, snapshots.json, diff-*.json, SAMPLE-*.xlsx, backup.json, 원본 가상 문서)
        ▼
vite build --mode demo  ── src/api.ts → src/demo/api.ts(정적 JSON만 읽음, 저장·실행 거절)
                           src/App.tsx → src/demo/DemoApp.tsx(로그인 없이 샘플 선택, Workspace readOnly)
        ▼ frontend/dist-demo/ (base /cj-sw-design/) → GitHub Pages
```

- 화면(단계·표·스타일·타입)은 실제 앱 것을 그대로 쓴다. 시연판만의 코드는 `src/demo/` 두 파일과 공용 컴포넌트의 읽기 전용 처리(`ActionButton`·`EditArea`·`useReadOnly`)뿐이다.
- 시연 모드는 **빌드 때만** 선택된다. 일반 빌드(`npm run build`)에는 시연 모듈·데이터가 들어가지 않고 URL 파라미터로 켤 수 없다(인증 우회 경로 없음).
- FP·금액을 손으로 적지 않는다. 생성기가 실제 API로 프로젝트를 만들고(샘플 규칙 모드, AI 호출 없음) 계산 엔진·엑셀 생성기 결과를 그대로 저장한다. `--check`는 저장된 값을 현재 엔진으로 다시 계산해 비교한다.

## 3. 로컬 실행·빌드

필요: Python 3.12+·uv(샘플 생성), Node.js 22.

```bash
cd frontend && npm ci
```

```bash
cd frontend && npm run demo:data
```
(= `cd backend && uv run python -m tools.demo_data && uv run python -m tools.demo_data --check` — 샘플 생성 후 검증)

```bash
cd frontend && npm run dev:demo
```
→ http://localhost:5173/cj-sw-design/ (백엔드 필요 없음)

```bash
cd frontend && npm run build:demo
```
→ `frontend/dist-demo/` (정적 파일만). 정적 서버로 확인:

```bash
node e2e/demo.cjs
```
(dist-demo를 `/cj-sw-design/` 아래에 제공하는 정적 서버를 스크립트가 직접 띄워 브라우저로 확인 — 로그인 없이 진입, 7단계, FP·개발비·검토의견, 샘플 엑셀, 단계 주소 새로고침, 모바일·태블릿 너비, 콘솔 오류·404, `/api`·외부 요청 0건. Playwright가 없으면 `cd e2e && npm ci && npx playwright install chromium`)

다른 경로(예: 사용자 Pages `/`)로 빌드하려면 `DEMO_BASE=/ npm run build:demo`.

## 4. 샘플 다시 만들기(화면·타입·계산 기준이 바뀌었을 때)
1. `cd frontend && npm run demo:data` — 생성 + 검증. 검증 실패 메시지(모델 불일치·FP/총액 불일치·엑셀 표시 누락)를 고친다.
2. 샘플 내용(시나리오)을 바꾸려면 `backend/tools/demo_data.py`의 `build_a`·`build_b`·`finish_b`·`vendor_docs`를 고친다. 값은 **API 호출로만** 만든다(FP 유형·DET·FTR 같은 담당자 입력값만 적고 점수·금액은 엔진이 계산).
3. `cd backend && uv run pytest -q tests/test_demo_data.py` — 생성기가 현재 코드로 동작하는지, A(완료)·B(검토 필요) 조건을 지키는지 확인(CI backend job에서도 실행).
4. `npm run build:demo` → `node e2e/demo.cjs`.
5. 커밋·PR. 생성된 `demo-public/demo-data/`와 `dist-demo/`는 커밋하지 않는다(Pages 워크플로가 빌드 때 다시 생성).

## 5. GitHub Pages 설정(사용자, 최초 1회)
1. 저장소 **Settings → Pages → Build and deployment → Source: `GitHub Actions`** 선택(“Deploy from a branch”가 아님).
2. 이 변경이 `main`에 병합되면 `.github/workflows/pages.yml`이 자동 실행되어 배포한다. 바로 다시 배포하려면 **Actions → Pages 시연판 → Run workflow**(브랜치 `main`).
3. 배포 후 Actions 실행의 `deploy` 작업 또는 Settings → Pages 상단에 표시되는 주소로 접속.
- 저장소는 Public이어야 무료 Pages를 쓸 수 있다(현재 Public). 공개 범위는 바꾸지 않는다.
- `github-pages` 환경은 첫 배포 때 자동으로 만들어지며 기본적으로 기본 브랜치(main)만 배포할 수 있다.

## 6. Pages 워크플로(`.github/workflows/pages.yml`)
- 트리거: `main` 푸시, 수동 실행(`workflow_dispatch`), PR.
- build: uv·Node 설치 → 샘플 생성·`--check` → `npm run build:demo` → 배포 파일 확인(html/js/css/json/xlsx/docx 외 파일·비밀값 이름이 있으면 실패) → Playwright로 `e2e/demo.cjs` → (main일 때만) `configure-pages@v6`·`upload-pages-artifact@v5`(경로 `frontend/dist-demo`만).
- deploy: main일 때만, `github-pages` 환경, 권한 `pages: write`·`id-token: write`만, 동시 배포 그룹 `pages`(진행 중 배포는 취소하지 않음) → `deploy-pages@v5`.
- PR에서는 생성·빌드·검증만 하고 아티팩트 업로드·배포를 하지 않는다. 기존 CI(`ci.yml`)는 그대로.
- 액션 버전은 2026-10-30 각 액션 저장소의 릴리스·GitHub 공식 starter workflow(`pages/static.yml`)와 대조했다. docs.github.com은 이 작업 세션의 네트워크 정책으로 열지 못했다.

## 7. 수정 후 배포
화면·데이터를 고친 PR을 `main`에 병합하면 Pages 워크플로가 샘플을 다시 생성·검증·배포한다. 시연판만 다시 배포하려면 Actions에서 수동 실행한다. 배포 결과가 이상하면 이전 커밋으로 되돌리는 PR을 병합하거나, Actions의 이전 성공 실행을 다시 실행한다.

## 8. 공통 디자인
`docs/DESIGN_SYSTEM.md`를 따른다. 홈은 샘플 A·B 선택·다운로드 중심, 단계 바로가기·차이 안내는 펼쳐보기로 제공한다. 일반 앱과 Header·Workspace·표·시트를 공유한다.

## 2026-10-30 엑셀 서식 개편 반영
시연판 샘플 엑셀도 같은 생성기(`backend/app/excel/export.py`)로 만들어 새 산출내역서형 서식이 적용된다(`docs/EXCEL_FORMAT.md`). 샘플 검증(`demo_data.py --check`)은 견적 총액 Python 값을 '검산' 시트에서, 금액 수식을 '개발비_기준' 시트에서 확인하도록 바뀌었다. 시연판은 AI를 호출하지 않으므로 모델 변경(`docs/AI_COST.md`)의 영향이 없다.
