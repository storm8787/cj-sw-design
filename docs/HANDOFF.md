# HANDOFF — 인수인계 (최종 갱신 2026-10-29)

## 1. 현재 위치
- 저장소: `storm8787/cj-sw-design`(2026-10-29 사용자가 Public으로 전환) · 작업 브랜치: `claude/kind-franklin-pjcpsr` · PR #1·#2 병합 완료, PR #3(여러 AI 연결·실제 OpenAI 검증) 진행 중
- 최근 커밋: `git log --oneline -5`로 확인. 문서(지침) → 백엔드 → 화면·E2E·배포 → 문서 마무리 순.
- PR: 만들지 않음(요청 시 생성).

## 2. 구현 현황 (PROJECT_SPEC ID 기준)

| 구분 | 상태 | 비고 |
|---|---|---|
| 공통 구조 SPEC-01~09 | 완료 | Docker 이미지 빌드·실행·재배포 영속성 확인. 외부 배포는 미실시(SPEC-08 의도) |
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
| 실제 AI 호출 | OpenAI 검증 / 그 외 **미검증** | OpenAI `gpt-6.1-sol`로 질문·요구사항·설계·FP 후보·문서 추출 모두 성공(VALIDATION §5-3, 발견된 문제 4건 수정). Anthropic·사내/상용 LLM은 실제 호출 미검증 |

## 3. 테스트 결과 (상세: `docs/VALIDATION.md`)
- 백엔드 pytest **117 passed**(2026-10-29, 실제 OpenAI 검증·PR #3 리뷰 수정 후), 프런트 타입검사·빌드 성공, 브라우저 E2E 통과, Docker 빌드·실행·재배포 영속성 확인.
- GitHub Actions(`.github/workflows/ci.yml`): run #1(ce87b9f) backend·frontend·e2e·docker 모두 성공(backend 88 passed / 1 skipped: 러너에 LibreOffice 없음). 이후 문서 커밋의 실행 결과는 Actions 탭에서 확인.

## 4. 알려진 문제·제약
1. KOSA 가이드 원문 미확인(네트워크 차단) — 단가 605,784원은 '2024 가이드' 표기 양식값, 이윤율 0.20은 양식 예시값, 끝수·단계 비율은 시스템/사용자 설정. `docs/FP_RULES.md §8`.
2. 샘플 모드 규칙은 표현 기반이라 FP 후보가 과대·과소일 수 있음(모두 '초안'으로 들어가 사용자 확정 필요).
3. 실 HWP 미검증, OCR 없음, PDF 표 구조 미보존.
4. 단일 프로세스 내 작업 실행(스레드). 다중 인스턴스 배포는 고려하지 않음.
5. 첨부 원본은 JSON 백업에 포함되지 않음(볼륨 백업 별도 필요).
6. 이 작업 환경 특성: Docker Hub 429·ghcr 차단·TLS 검사 프록시 → 로컬 Docker 빌드는 mirror.gcr.io 기반 이미지 + `--secret id=extra_ca` 사용.

## 5. 다음 작업(우선순위)
1. 사내/상용 LLM 또는 Anthropic을 쓸 경우 `LLM_*`·`ANTHROPIC_*`로 VALIDATION §5-3과 같은 절차(다섯 작업 각 1회) 실행. 설계 작업은 출력이 길어 1~2분 걸림(기본 시간 제한 600초).
2. sw.or.kr 접근 가능한 환경에서 가이드 2025 개정판 확인 → 차이가 있으면 새 기준 JSON 추가(기존 파일 수정 금지, 과거 견적 보존).
3. 실제 HWP 샘플로 추출 검증, 필요 시 변환 도구 연동 검토.
4. 운영 배포 결정(기관 서버/클라우드, HTTPS, 백업 정책) — 사용자 결정 필요.
5. AI 보조 문서 검토, 다중 사용자·권한, 유지관리비 등 후속 확장(PROJECT_SPEC §7).

## 6. 재개 명령
```bash
git checkout claude/kind-franklin-pjcpsr && git pull
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
- 운영: `SECRET_KEY`, `ADMIN_PASSWORD_HASH`(또는 `ADMIN_PASSWORD`), HTTPS 프록시와 `COOKIE_SECURE=true`, `/data` 볼륨 백업.
- AI 사용 시: 기본 OpenAI는 `OPENAI_API_KEY`·`OPENAI_MODEL`(검증한 모델: `gpt-6.1-sol`), 그 밖은 `.env.example`의 AI 연결 항목 참고. 각 서비스 결제 화면에서 월 지출 한도 설정. 외부 전송 동의 정책을 기관 보안 지침과 맞출 것.
- GitHub Actions: 비공개 상태에서는 계정 결제·지출 한도 문제로 작업 시작이 거부되었음(2026-10-29). Public 전환 후 정상 실행. 다시 비공개로 바꾸면 Billing & plans의 Actions 한도를 확인해야 함.
- 공개 저장소이므로 실제 사업 문서·DB·키·`.env`는 절대 커밋하지 않는다(.gitignore로 차단, 이력 점검 완료).
