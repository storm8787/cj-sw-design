# 개발·테스트·환경변수

README에서 옮긴 개발자용 상세 안내입니다. 평가·사용 안내는 [README](../README.md)와 [구동안내서](RUN_GUIDE.md)를 보세요.

## 구조
React + TypeScript 화면(`frontend/`) + Python FastAPI 서버(`backend/`) + SQLite·파일 저장(`DATA_DIR`).
GitHub·GitLab은 코드 보관 장소일 뿐이며, 실행하려면 Python 서버가 필요합니다(정적 시연판 제외). 자세히: [ARCHITECTURE](ARCHITECTURE.md)

## 소스에서 실행(개발)
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

브라우저 http://localhost:8000 (빌드된 화면을 서버가 함께 제공). 화면 개발 중에는 `cd frontend && npm run dev`(http://localhost:5173, API는 8000으로 프록시).
인증을 켠 운영 모드 실행과 Windows PowerShell 문법은 [구동안내서 2절](RUN_GUIDE.md#2-설치실행-절차). 비밀번호 해시 생성:

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

E2E는 서버를 운영 모드(인증)로 띄운 뒤 실행합니다. 다른 주소는 `BASE_URL`, 자체서명 HTTPS는 `E2E_IGNORE_HTTPS_ERRORS=1`. Playwright가 없으면 `cd e2e && npm ci && npx playwright install chromium`.

```bash
E2E_PASSWORD=<관리자 비밀번호> node e2e/flow.cjs
```

```bash
E2E_PASSWORD=<관리자 비밀번호> node e2e/reference.cjs
```

```bash
E2E_PASSWORD=<관리자 비밀번호> node e2e/examples.cjs
```

```bash
E2E_PASSWORD=<관리자 비밀번호> node e2e/ux.cjs
```

(`flow` 구상 기반 전체 흐름, `reference` 참고문서 흐름, `examples` 첫 화면 예제·예제 C 검토, `ux` 반응형·시트·필터·저장 UX)

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

`demo:data`는 Python으로 샘플과 예제 파일을 생성·검증합니다(빌드 단계 전용, 결과는 커밋하지 않음). 배포는 `.github/workflows/pages.yml`. 자세히: [DEMO](DEMO.md)

## Docker
README의 실행 방법과 같습니다. 덧붙임:
- DB·업로드·사용자 정의 기준은 `/data` 볼륨에 영속 저장됩니다. `.env`에서 `DATA_DIR`을 지정하면 Docker에서도 그 경로를 써서 볼륨 밖에 저장될 수 있으니 주석으로 둡니다.
- 포트는 `PORT` 환경변수를 따릅니다(없으면 8000). HTTPS는 배포 서비스나 기관 리버스 프록시에서 처리하고 `COOKIE_SECURE=true`.
- SSL 검사 프록시가 있는 망에서 빌드: `docker build --secret id=extra_ca,src=/path/사내루트인증서.pem -t sw-design-helper .`
- 클라우드 배포(Render, `render.yaml`): [DEPLOY](DEPLOY.md)

## 환경변수
`.env.example`에 설명이 있습니다. 주요 항목: `APP_ENV`, `DATA_DIR`, `SECRET_KEY`, `ADMIN_PASSWORD_HASH`/`ADMIN_PASSWORD`, `COOKIE_SECURE`, `AUTH_DISABLED`(개발 전용), `MAX_UPLOAD_MB`, `OFFICIAL_SOURCE_ALLOWLIST`, `AI_TIMEOUT_SEC`, `AI_MAX_OUTPUT_TOKENS`, `EXAMPLES_DIR`(예제 폴더 위치, 보통 비움).

### AI 연결
| 연결 | 켜는 방법 | 비고 |
|---|---|---|
| OpenAI(ChatGPT) — 기본 | `OPENAI_API_KEY`, `OPENAI_MODEL`, (선택) `OPENAI_MODEL_<작업>`, `OPENAI_REASONING_EFFORT` | 권장: `OPENAI_MODEL=gpt-6-luna` + `OPENAI_MODEL_FP_CANDIDATES=gpt-6.1-sol`([AI_COST](AI_COST.md)). 구조화 출력(JSON 스키마). `OPENAI_BASE_URL`로 프록시·Azure OpenAI v1 |
| Anthropic(Claude) | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | 구조화 출력. 실제 호출 미검증 |
| OpenAI 호환 상용·사내 LLM | `LLM_BASE_URL`, `LLM_MODEL`, (`LLM_API_KEY`, `LLM_LABEL`, `LLM_JSON_MODE`, `LLM_EXTERNAL`, `LLM_MODEL_<작업>`) | 구조화 출력 미지원 서버는 `LLM_JSON_MODE=prompt`. 기관 내부 설치면 `LLM_EXTERNAL=false`. 실제 호출 미검증 |
| 샘플 모드 | 항상 사용 가능 | AI 아님(규칙 기반), 외부 전송 없음 |

- `AI_PROVIDER`로 서버 기본 연결을 정하고(비우면 OpenAI 키가 있을 때 openai, 없으면 sample), 프로젝트마다 '1 개요 → AI 연결'에서 고를 수 있습니다.
- 모든 AI 응답은 같은 검증(JSON·스키마·없는 ID·사용자 기능 누락·언어·처리 후보 누락)을 거쳐 '변경안'으로만 들어옵니다. 작업마다 실제 호출 모델·토큰이 작업 상태에 표시됩니다.
- 새 공급자: `backend/app/ai/provider.py`에 `generate_json()` 하나를 구현하고 `config.load_ai_profiles()`에 설정을 추가합니다.
- 모델 비교시험(실제 호출·비용 발생, 가상 자료만): `cd backend && uv run python -m tools.ai_compare --model <모델> --budget 0.5 --out <파일>`

## UI·UX 개발
공통 디자인: [DESIGN_SYSTEM](DESIGN_SYSTEM.md). 작업 기준은 [agent.md](../agent.md)(Codex 진입점 [AGENTS.md](../AGENTS.md), Claude Code 진입점 [CLAUDE.md](../CLAUDE.md)).
