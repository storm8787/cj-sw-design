# HANDOFF — 인수인계 (최종 갱신 2026-10-30)

## 1. 현재 위치
- 최신 main `3cd1e24`와 최초 work 브랜치가 동일했고 작업 트리는 깨끗했다. 작업 브랜치 `design/clear-workflow`에서 UI·UX 개선.
- 원격 `claude/kind-franklin-pjcpsr`에 남은 미병합 `af4fbdc`(Pages 배포 결과 문서)를 발견해 README·DEMO·HANDOFF·VALIDATION의 내용을 보존했다. 원격 브랜치 자체는 수정하지 않았다.
- 기존 Pages 배포 기록: PR #4 이후 Actions run 40983396985 성공, https://storm8787.github.io/cj-sw-design/ . 이번 세션에서는 공개 주소 프록시 403으로 직접 확인하지 못했다.
- 이번 UI는 두 로컬 빌드·브라우저에서 검증. 아직 main 병합/Pages 재배포/Render 배포를 하지 않았다. Render는 사용자 지시로 진행하지 않는다.
- 디자인 기준 `docs/DESIGN_SYSTEM.md`; Codex 진입점 AGENTS.md → agent.md 직접 읽기. Claude Code도 같은 공통 기준 유지.
- 시작 화면 3종 분리, 시연 홈 A/B 선택 우선, 단계별 제목·이전/다음 이동, 핵심 입력 1건+전체 목록, 개요 상세 설정, 표 상태 필터·ID 상세 패널, 반응형 시트·성공 피드백·실제 로딩/오류 재시도 추가.
- 백엔드 계산·기준·ID 연결·AI 동의·엑셀 결과 구조·인증은 변경하지 않았다. API/App의 demo 교체는 빌드에서만 유지.

## 2. 구현 현황 (PROJECT_SPEC ID 기준)

| 구분 | 상태 | 비고 |
|---|---|---|
| 공통 구조 SPEC-01~09 | 완료 | Docker 이미지 빌드·실행·재배포 영속성 확인. 배포 서비스와 같은 설정(root 소유 디스크·PORT·HTTPS)으로 로컬 점검 완료. 외부 배포는 미실시(사용자 결정 대기) |
| 핵심 데이터 SPEC-10~19 | 완료 | 고유 ID, 1:N 연결, 영향 표시, 견적 스냅샷, 변경안 적용 |
| A 프로젝트 관리 | 완료 | 생성·목록·이름 변경·이어하기·삭제(이름 확인)·샘플 2종 |
| B 구상 기반 설계 | 완료 | 질문 은행 26종(공통+목적별 트리거). 실제 AI 질문 생성은 OpenAI로 확인(VALIDATION §5-3) |
| C 참고문서 기반 | 완료(HWP 실험적) | PDF/HWPX/DOCX/XLSX/TXT/MD. HWP 5.0 본문 텍스트 추출은 실제 HWP 샘플 미검증 → '실험' 표시. OCR 미구현(스캔 PDF는 '스캔본'으로 표시) |
| D 설계 작업대 | 완료 | 요구사항·업무흐름·기능·화면·데이터·연계·검수·과업 초안(사용자 수정 보존), 용어 설명 |
| E FP 산정 | 완료 | 간이·정통 별도 경로, 누락→미확정/가정, 중복·경계·연결 검사 |
| F 개발비·목표예산 | 완료 | 기준 버전·시나리오 분리, Decimal, 끝수 설정, 부가세 역산 |
| G 문서 검토 | 완료(규칙 기반) | AI 보조 검토는 미구현(후속) |
| H HW·SW 추천 | 완료(규칙 기반) | 공식 자료 등록·서버 조회(제목 확인)·사용자 확인 입력. 최신 버전 자동 판정은 하지 않음 |
| 엑셀 X1~X6 | 완료 | 12시트+검산, LibreOffice 재계산 일치 확인 |
| 품질 Q1~Q12 | 완료 | 단일 관리자 인증, CSRF, 업로드 검증, SSRF 차단, 백업·복원, 작업 재사용·중단 표시 |
| 여러 AI 연결(D-018) | 완료 | OpenAI 기본·Anthropic·OpenAI 호환 상용/사내 LLM·샘플을 동시에 설정, 프로젝트별 선택. OpenAI만 실제 호출 확인 |
| 샘플 시연판(D-020) | 완료·배포됨 | 정적 빌드·샘플 2종(생성기·검증)·읽기 전용 화면·Pages 워크플로·시연 E2E. 실제 Pages 배포는 사용자 설정·병합 후 |
| 실제 AI 호출 | OpenAI 검증 / 그 외 **미검증** | OpenAI `gpt-6.1-sol`로 질문·요구사항·설계·FP 후보·문서 추출 모두 성공(VALIDATION §5-3, 발견된 문제 4건 수정). Anthropic·사내/상용 LLM은 실제 호출 미검증 |

## 3. 테스트 결과 (상세: `docs/VALIDATION.md`)
- 백엔드 pytest **120 passed**(2026-10-30), 프런트 타입검사·일반 빌드·시연 빌드 성공.
- 샘플 시연판(VALIDATION §5-5): 정적 서버만으로 `e2e/demo.cjs` 통과 — `/api`·외부·404·콘솔 오류 0건, 모바일·태블릿, 샘플 엑셀 재계산 검산 일치.
- 배포 설정 로컬 점검(2026-10-30, VALIDATION §5-4): HTTPS 프록시 뒤 운영 모드 컨테이너에서 구상 기반(`e2e/flow.cjs`)·참고문서 기반(`e2e/reference.cjs`) 브라우저 E2E 통과, 컨테이너 교체 후 데이터 유지, 실제 OpenAI 질문·문서 추출 성공, 엑셀 다운로드, 로그에 비밀값·원문 없음.
- GitHub Actions(`.github/workflows/ci.yml`): PR #3 최신 커밋(56998ac)에서 backend·frontend·e2e·docker 모두 성공. 이번 브랜치부터 e2e job이 참고문서 E2E도 실행.

## 4. 알려진 문제·제약
1. KOSA 가이드 원문 미확인(네트워크 차단) — 단가 605,784원은 '2024 가이드' 표기 양식값, 이윤율 0.20은 양식 예시값, 끝수·단계 비율은 시스템/사용자 설정. `docs/FP_RULES.md §8`.
2. 샘플 모드 규칙은 표현 기반이라 FP 후보가 과대·과소일 수 있음(모두 '초안'으로 들어가 사용자 확정 필요).
3. 실 HWP 미검증, OCR 없음, PDF 표 구조 미보존.
4. 단일 프로세스 내 작업 실행(스레드). 다중 인스턴스 배포는 고려하지 않음(배포 시 1대 고정). 재배포·재시작 때 실행 중이던 AI 작업은 '중단' 표시 후 재시도.
5. 첨부 원본은 JSON 백업에 포함되지 않음(볼륨 백업 별도 필요).
6. 이 작업 환경 특성: Docker Hub 429·ghcr 차단·TLS 검사 프록시 → 로컬 Docker 빌드는 mirror.gcr.io 기반 이미지 + `--secret id=extra_ca` 사용.
7. 로그인 실패 제한(5회/5분)이 배포 프록시 주소 단위로 걸려, 배포 환경에서는 모든 접속자가 함께 5분간 막힐 수 있음(단일 관리자 테스트용 한계).
8. 샘플 시연판은 읽기 전용 정적 화면(새 계산·생성 없음). 샘플 데이터는 커밋하지 않고 빌드 때 `backend/tools/demo_data.py`로 생성하므로, 화면·모델·계산을 바꾼 뒤 `npm run demo:data`가 실패하면 생성기(`build_a`·`build_b`)를 함께 고쳐야 Pages 배포가 진행됨.

## 5. 다음 작업(우선순위)
1. (사용자) 시연 주소 `https://storm8787.github.io/cj-sw-design/` 접속 확인(샘플 A·B, 단계 이동, 샘플 엑셀). 문제가 있으면 화면·문구를 알려 주면 수정 후 main 병합으로 재배포.
2. (사용자) `docs/DEPLOY.md` §3대로 Render 배포(실제 앱, `render.yaml`은 main에 병합됨) → `docs/USER_TEST.md` A·B 순서로 직접 테스트 → 문제 기록을 다음 작업으로 반영. 배포 후 VALIDATION에 실제 배포 확인 결과 기록.
3. 사내/상용 LLM 또는 Anthropic을 쓸 경우 `LLM_*`·`ANTHROPIC_*`로 VALIDATION §5-3과 같은 절차(다섯 작업 각 1회) 실행. 설계 작업은 출력이 길어 1~2분 걸림(기본 시간 제한 600초).
4. sw.or.kr 접근 가능한 환경에서 가이드 2025 개정판 확인 → 차이가 있으면 새 기준 JSON 추가(기존 파일 수정 금지, 과거 견적 보존).
5. 실제 HWP 샘플로 추출 검증, 필요 시 변환 도구 연동 검토.
6. 운영(기관 서비스) 배포 결정(기관 서버/클라우드, 실데이터 보안 검토, 백업 정책) — 사용자 결정 필요. 테스트 배포와 별개.
7. AI 보조 문서 검토, 다중 사용자·권한, 유지관리비 등 후속 확장(PROJECT_SPEC §7).

## 6. 재개 명령
```bash
git switch design/clear-workflow
# 기존 변경을 먼저 확인하며 임의로 브랜치를 리셋하지 않는다.
```

```bash
cd backend && uv sync && uv run pytest -q
```

```bash
cd frontend && npm ci && npm run typecheck && npm run build
```

```bash
cd backend && APP_ENV=development AUTH_DISABLED=true uv run uvicorn app.main:create_app --factory --port 8000
```

## 7. 외부 설정 필요사항
- 테스트 배포(Render): 사용자가 입력할 값은 `ADMIN_PASSWORD`(또는 해시)와 `OPENAI_API_KEY`뿐. `SECRET_KEY`는 Render가 생성, 나머지는 `render.yaml`. 비용 약 월 7.25달러 + OpenAI 사용료(`docs/DEPLOY.md` §1).
- 운영: `SECRET_KEY`, `ADMIN_PASSWORD_HASH`(또는 `ADMIN_PASSWORD`), HTTPS 프록시와 `COOKIE_SECURE=true`, `/data` 볼륨 백업.
- AI 사용 시: 기본 OpenAI는 `OPENAI_API_KEY`·`OPENAI_MODEL`(검증한 모델: `gpt-6.1-sol`), 그 밖은 `.env.example`의 AI 연결 항목 참고. 각 서비스 결제 화면에서 월 지출 한도 설정. 외부 전송 동의 정책을 기관 보안 지침과 맞출 것.
- GitHub Actions: 비공개 상태에서는 계정 결제·지출 한도 문제로 작업 시작이 거부되었음(2026-10-29). Public 전환 후 정상 실행. 다시 비공개로 바꾸면 Billing & plans의 Actions 한도를 확인해야 함.
- 공개 저장소이므로 실제 사업 문서·DB·키·`.env`는 절대 커밋하지 않는다(.gitignore로 차단, 이력 점검 완료).

## 8. UI·UX 검증과 다음 작업 (2026-10-30)
- `docs/VALIDATION.md` §7: 타입검사·두 빌드·백엔드 120개·일반 앱 2종 E2E·시연 E2E·추가 UX 검사 통과.
- 스크린샷: `/workspace/artifacts/cj-design/before`, `after`. 저장소 밖의 비교 산출물이며 커밋하지 않는다.
- 실제 모바일 기기·스크린리더, 공개 Pages에서 새 UI, Render, 유료 AI는 미검증. 브라우저는 시스템 Chromium/Playwright 1.63.0으로 확인.
- UI 구현 커밋 `c572419`, 원격 `design/clear-workflow`에 push 완료. PR 조회/생성을 시도했으나 `api.github.com/graphql`에서 Forbidden. 본문은 `docs/UI_UX_PR.md`, 생성 주소는 https://github.com/storm8787/cj-sw-design/pull/new/design/clear-workflow . PR 생성 자체는 미완료이며 main 병합 금지.
