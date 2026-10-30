# 정보화 설계 도우미

지방자치단체 공무원이 **신규 정보화사업(홈페이지·포털, 일반 SW·정보시스템 신규개발)**을 구상하거나 참고문서를 제시하면,
질문으로 요구사항과 설계를 구체화하고 **FP(기능점수)·개발비·검토의견·엑셀 산출물**을 만들어 주는 웹앱입니다.

- **샘플 시연판(GitHub Pages)**: https://storm8787.github.io/cj-sw-design/ (2026-10-30 배포, `main` 변경 시 자동 재배포). 안내: [`docs/DEMO.md`](docs/DEMO.md)
- 실제 앱 접속 주소: **미배포**. 테스트 배포 준비 완료 — Render 1대 + 영속 디스크 추천안과 절차는 [`docs/DEPLOY.md`](docs/DEPLOY.md), 배포 후 사용자 테스트 순서는 [`docs/USER_TEST.md`](docs/USER_TEST.md). 배포 서비스 가입·결제·비밀값 입력은 사용자가 직접 합니다.
- 상태·다음 작업: [`docs/HANDOFF.md`](docs/HANDOFF.md) · 요구사항: [`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md) · FP 기준: [`docs/FP_RULES.md`](docs/FP_RULES.md)

## 실제 앱과 샘플 시연판

| | 실제 앱(서버 — Render 등 배포 예정) | 샘플 시연판(GitHub Pages) |
|---|---|---|
| 목적 | 실제 사업을 설계하고 산출물을 만든다 | 가상 샘플로 화면 흐름과 결과물을 둘러본다 |
| 로그인 | 관리자 비밀번호 | 없음 |
| 데이터 | 프로젝트 생성·편집·저장·이어하기 | 미리 만든 가상 샘플 2종(구상 기반 완료 사례, 참고문서 기반 검토 필요 사례), 저장 안 함 |
| AI·문서 | AI 연결(또는 서버 '샘플 모드' 규칙)로 질문·초안 생성, 문서 업로드·추출 | AI 호출·업로드·분석 없음(미리 만든 결과 표시) |
| FP·개발비·엑셀 | 입력할 때마다 계산·생성 | 서버 계산 엔진·엑셀 생성기로 미리 만든 값·샘플 파일 |
| 실행 | Python 서버 필요(`docker run …`) | 정적 파일만(`npm run build:demo`) |

시연판은 실제 앱과 같은 화면 코드를 읽기 전용으로 쓰며, 빌드할 때만 선택됩니다(일반 앱에서 주소로 켤 수 없음). 자세히: [`docs/DEMO.md`](docs/DEMO.md)

## 주요 기능
- **시작 4종**: 새 설계(한 줄 구상) / 참고문서로 설계 / 기존 문서 검토 / 프로젝트 이어하기, 샘플 프로젝트 2종
- **질문으로 구체화**: 사업 목적에 맞는 질문을 몇 개씩, 선택지·직접 입력·모름(권장안을 가정으로 기록)·나중에 결정
- **요구사항·설계 작업대**: 요구사항, 업무흐름, 기능설계, 화면, 데이터, 연계, 검수 기준, 과업지시서 초안 — 표에서 직접 수정
- **참고문서 재설계**: PDF·HWPX·DOCX·XLSX·TXT·MD 추출(원문 위치 보존), 항목별 유지/수정/제외, 타 기관 예산·기간·개인정보·제품 조건 표시
- **FP 산정**: 간이법·정통법(서로 다른 계산), 미확정·미분류·중복 의심·경계 밖·요구사항 연결 표시, 용어 설명
- **개발비**: 기준 산정 버전(당시 기준 보존) + 목표예산 시나리오(기능 유지, 조정률·환산값·끝수조정 공개)
- **기존 문서 검토**: 요구사항 ID 누락, FP 가중치·중복·합계, 산식·VAT·총액, 불명확 범위, 문서로 확정 불가 항목
- **HW·SW 구성 추천**: 자체 서버 가정 기반 구성안 / 클라우드 서비스 구성(사양 미제시), 공식 출처·확인일 관리
- **엑셀 산출물**: 12개 시트 + 검산 시트(수식 값 = Python 계산값 확인), 화면 미리보기, JSON 백업·복원
- **AI(여러 공급자 교체 가능)**: OpenAI(ChatGPT, 기본)·Anthropic(Claude)·OpenAI 호환 상용/사내 LLM을 동시에 설정하고 프로젝트마다 선택. 키가 없으면 **샘플 모드**(서버 규칙, AI 아님)로 전체 흐름 사용 가능. AI 결과는 '변경안'으로만 제시되어 사용자가 골라 적용

## 사용 순서
1 개요(목적·경계·금액 조건) → 2 자료·질문 → 3 요구사항 → 4 설계 → 5 FP·개발비 → 6 검토·추천 → 7 엑셀. 언제든 이전 단계로 돌아갈 수 있고 모든 변경은 즉시 저장됩니다.

## 구조
React + TypeScript 화면(`frontend/`) + Python FastAPI 서버(`backend/`) + SQLite·파일 저장(`DATA_DIR`).
**GitHub는 코드 보관 장소일 뿐이며, 실행하려면 Python 서버가 필요합니다(GitHub Pages만으로는 동작하지 않음).** 자세한 구성: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## 설치·실행 (2026-10-30 확인)
필요: Python 3.12+와 [uv](https://docs.astral.sh/uv/), Node.js 22

```bash
cd backend && uv sync
```

```bash
cd frontend && npm ci && npm run build
```

```bash
cd backend && APP_ENV=development AUTH_DISABLED=true uv run uvicorn app.main:create_app --factory --port 8000
```

브라우저에서 http://localhost:8000 (빌드된 화면을 서버가 함께 제공). 화면 개발 중에는 `cd frontend && npm run dev`(http://localhost:5173, API는 8000으로 프록시).

운영 모드(인증 사용)는 `.env.example`을 `.env`로 복사해 `SECRET_KEY`와 `ADMIN_PASSWORD_HASH`(또는 `ADMIN_PASSWORD`)를 채운 뒤 실행합니다. 비밀번호 해시 생성:

```bash
cd backend && uv run python -m app.auth hash
```

## 테스트
```bash
cd backend && uv run pytest -q
```

```bash
cd frontend && npm run typecheck && npm run build
```

```bash
E2E_PASSWORD=<관리자 비밀번호> node e2e/flow.cjs
```

```bash
E2E_PASSWORD=<관리자 비밀번호> node e2e/reference.cjs
```
(E2E는 서버를 운영 모드로 띄운 뒤 실행. `flow.cjs`는 구상 기반, `reference.cjs`는 참고문서 기반 흐름. 다른 주소는 `BASE_URL`, 자체서명 HTTPS는 `E2E_IGNORE_HTTPS_ERRORS=1`. Playwright가 없으면 `cd e2e && npm ci && npx playwright install chromium`)

## 샘플 시연판 빌드(서버 불필요)
```bash
cd frontend && npm run demo:data
```

```bash
cd frontend && npm run build:demo
```

```bash
node e2e/demo.cjs
```
(`demo:data`는 Python으로 샘플을 생성·검증 — 빌드 단계 전용. 결과 `frontend/dist-demo/`는 `/cj-sw-design/` 경로용 정적 파일. 배포는 `.github/workflows/pages.yml`)

## Docker 단일 서버 배포
```bash
docker build -t sw-design-helper .
```

```bash
docker run -d -p 8000:8000 -v swdata:/data --env-file .env --name sw-design-helper sw-design-helper
```
- DB·업로드·사용자 정의 기준은 `/data` 볼륨에 영속 저장되어 컨테이너를 바꿔도 유지됩니다. 배포 서비스 디스크가 root 소유로 붙어도 시작 시 소유자를 맞추고 비루트(`app`)로 실행합니다.
- 포트는 `PORT` 환경변수를 따릅니다(없으면 8000).
- HTTPS는 배포 서비스나 기관 리버스 프록시에서 처리하고 `COOKIE_SECURE=true`로 설정하세요.
- 클라우드 테스트 배포(Render, `render.yaml`): [`docs/DEPLOY.md`](docs/DEPLOY.md)
- SSL 검사 프록시가 있는 망에서 빌드할 때: `docker build --secret id=extra_ca,src=/path/사내루트인증서.pem -t sw-design-helper .`

## 환경변수
`.env.example` 참고. 주요 항목: `APP_ENV`, `DATA_DIR`, `SECRET_KEY`, `ADMIN_PASSWORD_HASH`/`ADMIN_PASSWORD`, `COOKIE_SECURE`, `AUTH_DISABLED`(개발 전용), `MAX_UPLOAD_MB`, `OFFICIAL_SOURCE_ALLOWLIST`.

### AI 연결
| 연결 | 켜는 방법 | 비고 |
|---|---|---|
| OpenAI(ChatGPT) — 기본 | `OPENAI_API_KEY`, `OPENAI_MODEL` | 2026-10-29 `gpt-6.1-sol`로 실제 호출 검증. 구조화 출력(JSON 스키마) 사용. `OPENAI_BASE_URL`로 프록시·Azure OpenAI v1 주소 지정 가능 |
| Anthropic(Claude) | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | 구조화 출력 사용. 실제 호출 미검증 |
| OpenAI 호환 상용·사내 LLM | `LLM_BASE_URL`, `LLM_MODEL`, (`LLM_API_KEY`, `LLM_LABEL`, `LLM_JSON_MODE`, `LLM_EXTERNAL`) | 구조화 출력 미지원 서버는 `LLM_JSON_MODE=prompt`. 기관 내부 설치면 `LLM_EXTERNAL=false`. 실제 호출 미검증 |
| 샘플 모드 | 항상 사용 가능 | AI 아님(규칙 기반), 외부 전송 없음 |

- `AI_PROVIDER`로 서버 기본 연결을 정하고(비우면 OpenAI 키가 있을 때 openai, 없으면 sample), 각 프로젝트의 '개요 → AI 연결'에서 다른 연결을 고를 수 있습니다.
- 모든 AI 응답은 공급자와 관계없이 같은 검증(JSON·스키마·없는 ID·사용자 기능 누락·과도한 응답)을 거쳐 '변경안'으로만 들어옵니다.
- AI API는 쓴 만큼 요금이 나갑니다. 각 서비스의 결제 화면에서 월 지출 한도를 꼭 설정하세요.
- 새 공급자를 추가하려면 `backend/app/ai/provider.py`에 `generate_json()` 하나를 구현하고 `config.load_ai_profiles()`에 설정을 추가하면 됩니다.

## 제약
- FP·개발비 기준값은 2026 산정양식 패키지의 양식 수식에서 추출했습니다. KOSA 가이드 원문(2025 개정판)은 이 작업 환경에서 접속이 막혀 **미확인**이며, 이윤율·끝수·단계별 비율은 확인 필요로 표시됩니다(`docs/FP_RULES.md`).
- 실제 AI 호출은 OpenAI(`gpt-6.1-sol`)로만 검증했습니다(2026-10-29 다섯 작업, 2026-10-30 배포 설정에서 질문·문서 추출). Anthropic·사내/상용 LLM은 가짜 전송 계층으로만 시험했습니다. HWP는 실험적 지원이며 HWPX/PDF 변환을 권장합니다. 스캔 PDF는 OCR을 하지 않습니다.
- 장비 구매비는 개발비에 포함하지 않습니다. 유료 SW·클라우드 비용은 '별도 비용'으로만 표시합니다.
- 단일 관리자용 MVP입니다(다중 사용자·권한 분리는 후속).
- 연간 유지관리, 장비 유지관리, ITS/BIS, RFID, 단독 DB·공간정보 구축, 컨설팅은 후속 확장 범위입니다.
