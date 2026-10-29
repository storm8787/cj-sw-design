# ARCHITECTURE — 실제 구성

## 1. 디렉터리

```
agent.md, CLAUDE.md           공통 작업 기준 / Claude Code 진입(@agent.md import)
docs/                         요구사항·결정·FP 기준·인수인계·검증 기록
backend/                      Python 3.12+ FastAPI (uv, uv.lock)
  app/main.py                 앱 팩토리(create_app), 인증·CSRF 미들웨어, 오류 매핑, 빌드 화면 제공
  app/routes.py               HTTP API 전체(/api/…)
  app/config.py               환경변수 → Settings, 운영 설정 검증(비밀값 필수)
  app/db.py                   SQLite(WAL) 스키마·트랜잭션
  app/models.py               프로젝트 공통 데이터(Pydantic) — 모든 산출물의 원천
  app/store.py                프로젝트 저장, ID 발급, 항목 편집, 변경이력, 영향 표시, 스냅샷
  app/fp/standards.py         산정 기준 버전(내장 JSON + 사용자 정의)
  app/standards/*.json        기준값과 항목별 근거·확인 상태
  app/fp/engine.py            간이법·정통법 계산, 중복·경계·연결 검사
  app/fp/cost.py              개발비(Decimal·끝수), 목표예산 시나리오
  app/fp/estimates.py         견적 버전(기준 스냅샷 포함)·상태·시나리오
  app/excel/export.py         12개 산출 시트 + 검산 시트, 미리보기 변환
  app/ai/provider.py          AI 어댑터(sample/anthropic/mock), 구조화 출력 스키마
  app/ai/sample.py            샘플 모드 규칙(질문 은행, 초안·FP 후보·문서 항목 분류)
  app/ai/tasks.py             작업 처리(검증·재시도) → 변경안(Proposal)
  app/jobs.py                 작업 실행기(중복 재사용·진행률·재시작 후 중단 표시)
  app/docs_extract/extract.py 업로드 검증·형식별 추출·구간 분할
  app/review/review.py        업체 문서 대조 검토
  app/tech/recommend.py       HW·SW 구성 추천 규칙, 공식 자료 후보
  app/tech/fetch.py           허용 도메인 조회(SSRF 차단)
  app/services/*.py           과업 초안, 샘플 프로젝트, 변경안 적용, 백업·복원, 진행 상태
  tests/                      pytest(가상 문서 생성기 포함, 실데이터 없음)
frontend/                     React 18 + TypeScript + Vite (package-lock.json)
  src/App.tsx                 로그인·해시 라우팅·모드 표시
  src/pages/                  Home(시작 4종·목록·복원), Workspace(7단계), Login
  src/steps/                  Overview, Sources(질문·문서·참고항목), Requirements, Design, Fp, Review(검토·추천), Excel
  src/components/             EditableTable, Proposals, Jobs, ui
e2e/flow.cjs                  Playwright 브라우저 E2E
Dockerfile, .dockerignore     단일 서버 이미지(화면+API, /data 볼륨)
.github/workflows/ci.yml      백엔드 테스트·프런트 타입검사/빌드·E2E·이미지 빌드
```

## 2. 데이터 흐름

```
[사용자 입력·질문 답변·업로드 문서]
        │ (AI/샘플 작업: 결과는 변경안으로만)
        ▼
  Project 문서(JSON, SQLite projects.data) ── ID로 연결 ──┐
   overview / requirements / workflows / functions /       │
   screens / data_entities / interfaces / fp_items /       │
   questions / assumptions / documents / sources /         │
   reference_items / cost_settings / estimates(스냅샷) /   │
   reviews / tech / official_sources / proposals /         │
   task_draft                                              │
        │                                                  │
        ├─ fp.engine → FP 집계(간이·정통), 연결·중복·경계 검사
        ├─ fp.cost/estimates → 기준 산정 버전 → 목표예산 시나리오
        ├─ services.taskdraft → 과업지시서 초안
        ├─ review → 검토의견, tech → 구성 추천
        └─ excel.export → .xlsx(수식+Python 확인값+검산) / 화면 미리보기
```

- 편집은 모두 `store.mutate()` 한 트랜잭션: 읽기 → 변경 → Pydantic 전체 재검증 → 저장(version+1) → change_log 기록.
  검증 실패 시 아무것도 바뀌지 않는다. `version`으로 동시 편집 충돌(409)을 감지한다.
- 항목이 바뀌면 `DEPENDENTS`(models.py)에 따라 연결된 항목에 `needs_review` 표시. 견적은 입력 해시 비교로 `stale` 판정.
- 견적 버전은 산정 시점의 기준 JSON·설정·FP 스냅샷을 통째로 보관(과거 버전 보존).

## 3. 저장소(SQLite, `DATA_DIR/app.db`)

| 테이블 | 내용 |
|---|---|
| projects | id, name, data(JSON), version, created_at, updated_at |
| change_log | 프로젝트별 변경 전후·주체·영향·재검토 필요 |
| snapshots | 설계 스냅샷(프로젝트 JSON 전체) |
| jobs | 작업 종류·입력 해시·상태·진행률·오류·결과 |
| doc_chunks | 문서 추출 구간(위치 범위 포함)·분석 여부 |

파일: `DATA_DIR/projects/<프로젝트ID>/files/<DOC-ID>.<확장자>` (원래 파일명은 메타데이터에만), 사용자 정의 기준 `DATA_DIR/standards/`.

## 4. API 요약(`/api`)

- 인증: `POST auth/login`, `POST auth/logout`, `GET auth/me`, `GET health`(공개)
- 시스템: `GET system`, `GET standards/{id}`, `POST standards/custom`
- 프로젝트: `GET/POST projects`, `GET/PATCH/DELETE projects/{pid}`(삭제는 `confirm_name`), `GET …/changes`, `POST/GET …/snapshots`, `GET …/snapshots/{sid}/diff`
- 항목: `POST …/items/{collection}`, `PATCH/DELETE …/items/{collection}/{id}` (requirements, workflows, functions, screens, data_entities, interfaces, fp_items, questions, assumptions, reference_items, reviews, official_sources)
- FP·견적: `GET …/fp`, `PUT …/cost-settings`, `GET …/estimate-preview`, `POST …/estimates`, `POST …/estimates/{eid}/scenarios`
- 과업 초안: `POST …/task-draft/generate`, `PATCH …/task-draft/{key}`
- AI/샘플 작업: `GET …/ai/transmission-preview`, `POST …/ai/{questions|requirements|design|fp_candidates}`, `POST …/questions/{qid}/answer`, `POST …/proposals/{prid}/apply|reject`, `GET …/jobs`, `GET jobs/{jid}`, `POST jobs/{jid}/retry`
- 문서: `POST …/documents`(multipart), `GET …/documents/{did}/download|chunks`, `POST …/documents/{did}/consent|analyze`, `DELETE …/documents/{did}`, `POST …/reference-items/{rid}/decide`
- 검토·추천: `POST …/review/run`, `PUT …/tech/inputs`, `POST …/tech/recommend`, `POST …/official-sources/suggested`, `POST …/official-sources/{sid}/fetch`
- 산출물: `GET …/export.xlsx`, `GET …/export/preview`, `GET …/backup.json`, `POST projects/restore`

## 5. AI 연결

여러 AI 연결을 동시에 두고 바꿔 끼우는 구조(DECISIONS D-018).

```
환경변수 ─ config.load_ai_profiles() ─ AIProfile(openai / anthropic / compatible / sample)
                                          │
                       ai/provider.py ProviderRegistry ─ 프로젝트.ai_profile(비우면 AI_PROVIDER 기본)
                                          │ generate_json(task, system, user, schema) → JSON 문자열
                       ai/tasks.py  call_ai(): 스키마·업무 검증, 1회 재시도 → 변경안(Proposal.source 기록)
```

| 연결 | 구현 | 구조화 출력 | 외부 전송 |
|---|---|---|---|
| `openai`(기본) | `openai` 공식 SDK, Chat Completions | `response_format` json_schema strict | 예(요청마다 동의) |
| `anthropic` | `anthropic` 공식 SDK, Messages | `output_config.format` json_schema | 예 |
| `compatible` | `openai` SDK + `LLM_BASE_URL`(Azure OpenAI v1, vLLM, Ollama, 국내 LLM 등) | `LLM_JSON_MODE`: json_schema / json_object / prompt(스키마를 지시문에 넣고 JSON만 추출) | `LLM_EXTERNAL`(내부 설치면 false) |
| `sample` | 규칙 엔진(ai/sample.py) | — | 아니오 |

- 공급자별 지원이 다른 스키마 제약(maxItems 등)은 보내는 스키마에서 제거하고 응답을 Pydantic으로 다시 검증.
- 거절·잘림·콘텐츠 필터·인증·모델 없음·한도·연결 오류를 연결 이름이 붙은 한국어 사유로 바꿔 작업 실패로 기록(데이터는 그대로).
- 같은 입력이라도 AI 연결이 다르면 다른 작업으로 취급(중복 실행 재사용 키에 연결 이름 포함).
- 새 공급자 추가: `AIProvider` 하위 클래스에 `generate_json()` 구현 + `load_ai_profiles()`에 설정 추가.
- 모든 응답은 Pydantic 재검증 + 업무 검증(없는 ID 제거, 사용자 기능 누락 복원, 과도한 질문 절단, 원문에 없는 추출 항목 제거). 치명 오류면 오류 내용을 붙여 1회 재시도.
- 외부 AI 모드에서는 요청마다 전송 범위 미리보기 + 동의(`consent`) 필요, 문서 원문은 문서별 동의 필요.

## 6. 보안·운영

- 운영(`APP_ENV=production`): `SECRET_KEY`(32자+)와 관리자 비밀번호(해시 권장) 없으면 기동 실패. `AUTH_DISABLED`는 development에서만.
- 세션: 서명 쿠키(HttpOnly, SameSite=Strict, 12시간). 변경 요청은 `X-Requested-With: swd` 필수. 로그인 실패 5회/5분 제한.
- 업로드: 확장자 허용 목록, 내용 서명, 크기, 압축 해제 용량·압축률·내부 경로 검사, 저장 파일명은 서버가 생성.
- 응답 헤더: nosniff, X-Frame-Options DENY, API는 no-store. 로그에 원문·키·비밀번호를 쓰지 않는다.

## 7. 배포·영속 저장

- 개발: 백엔드 8000 + Vite 5173(프록시) 또는 `frontend/dist` 빌드 후 백엔드 하나로 실행.
- Docker: `docker build -t sw-design-helper .` → `docker run -p 8000:8000 -v swdata:/data --env-file .env sw-design-helper`.
  DB·업로드·사용자 정의 기준은 `/data` 볼륨에 남아 컨테이너 교체(재배포) 후에도 유지(2026-10-29 실제 확인, VALIDATION 참고).
- HTTPS 종단은 리버스 프록시(기관 웹서버·로드밸런서)에서 처리하고 `COOKIE_SECURE=true`로 운영.
- GitHub Pages로는 동작하지 않는다(Python 서버 필요). 외부 공개 배포·유료 자원 생성은 하지 않았다(미배포).
