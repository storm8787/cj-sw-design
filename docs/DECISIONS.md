# DECISIONS — 결정 기록

형식: 결정일 · 선택 · 근거 · 가정 · 대안 · 미결. 현재 유효한 결정은 '현재', 대체된 결정은 '과거'로 표시한다.

## 현재 결정

### D-001 (2026-10-29) 저장소·브랜치
- 선택: 연결 저장소 `storm8787/cj-sw-design`(예상과 일치), 작업 브랜치 `claude/kind-franklin-pjcpsr`. 원격·공개 범위 변경 없음.
- 근거: 세션 지정 브랜치. 시작 시 저장소에는 `README.md`, `.gitignore`만 존재(초기 커밋 1개).

### D-002 (2026-10-29) 기술 구성
- 선택: React 18 + TypeScript + Vite / Python 3.12+ FastAPI / SQLite(표준 `sqlite3`) / openpyxl / uv(잠금 `uv.lock`) / npm(`package-lock.json`).
- 근거: 사용자 기본안. 단일 사용자 MVP에 별도 DB 서버 불필요. ORM 없이 문서형 JSON 저장으로 ID·스냅샷·백업을 단순화.
- 대안: PostgreSQL(다중 사용자 시), SQLAlchemy ORM.

### D-003 (2026-10-29) 프로젝트 데이터 저장 방식
- 선택: 프로젝트 1건 = SQLite `projects.data`의 JSON 문서(Pydantic 검증). 스냅샷·작업·파일·변경이력은 별도 테이블. 업로드 원본은 `DATA_DIR/projects/<id>/files/`.
- 근거: 요구사항·기능·FP·견적이 강하게 연결되어 문서 단위 원자 저장이 단순하고, JSON 백업·복원과 동일 구조.
- 가정: 프로젝트당 항목 수천 건 이하. 낙관적 잠금(`version`)으로 동시 편집 충돌 감지.

### D-004 (2026-10-29) FP·개발비 기준 출처
- 선택: 업로드된 2026 산정양식 패키지의 1101/1102 양식 수식·VBA에서 추출한 값을 기준 버전 `KOSA-FORM-2024G-241231`로 사용. 미확인 값은 상태 표시.
- 근거: sw.or.kr이 이 환경에서 차단됨(프록시 403). 양식은 사용자가 제공한 공식 배포 파일.
- 미결: 2025 개정판 원문 대조(FP_RULES §8).

### D-005 (2026-10-29) 끝수·계산 순서
- 선택: Decimal 계산, 개발원가·이윤·VAT 단계에서 설정된 끝수 규칙 적용, 기본 '원 미만 절사'. FP_RULES §5.
- 근거: 양식에 끝수 규칙 없음. 원 단위 합계 일치와 엑셀 재현성 확보.
- 미결: 공식 끝수 규정 확인 후 기본값 조정.

### D-006 (2026-10-29) 목표예산 시나리오 방식
- 선택: 단일 조정률 r을 산출하고 조정률/환산FP/환산단가로 표현, 끝수조정 행을 공개. 기능 집합 불변.
- 근거: 사용자 요구(기능 유지 + 금액 맞춘 산출내역)와 투명성. 가상 비용항목 생성 금지.
- 대안: 보정계수 재선택 탐색 — 기준 판단을 왜곡하므로 채택하지 않음.

### D-007 (2026-10-29) AI 연결
- 선택: 서버 측 `AIProvider` 어댑터. 구현체 `AnthropicProvider`(Messages API, httpx) + `SampleProvider`(규칙 기반, AI 아님) + 테스트용 `MockProvider`.
  모델명은 `AI_MODEL` 환경변수 한 곳에서만 읽는다.
- 근거: 키 없이 전체 흐름 사용, CI는 mock.
- 가정: 이 작업 환경에는 앱용 AI 키가 없음 → **실제 AI 호출은 미검증**.
- AI 결과는 '변경안(proposal)'으로 저장 후 사용자가 항목별 적용/거절.

### D-008 (2026-10-29) 인증
- 선택: 단일 관리자. `ADMIN_PASSWORD_HASH`(scrypt) 또는 최초 실행 시 `ADMIN_PASSWORD` 환경변수, `SECRET_KEY` 필수. 서명 쿠키 세션(HttpOnly, SameSite=Strict) + 변경 요청에 `X-Requested-With` 헤더 요구.
- `AUTH_DISABLED=true`는 `APP_ENV=development`일 때만 허용. 운영 설정에서 비밀값 없으면 서버 기동 실패.

### D-009 (2026-10-29) 긴 작업 실행
- 선택: SQLite `jobs` 테이블 + 프로세스 내 스레드 실행. 동일 입력 해시의 진행 중/성공 작업은 재사용(중복 비용 방지). 기동 시 `running` → `interrupted`.
- 대안: Celery/Redis — 단일 사용자 규모에서 불필요(SPEC-06).

### D-010 (2026-10-29) 문서 추출
- 선택: PDF `pypdf`, DOCX `python-docx`, XLSX `openpyxl`, HWPX(zip+XML 직접 파싱), TXT/MD, HWP(olefile 기반 최소 본문 텍스트 추출, **실험적**).
- HWP는 실제 한글 파일 샘플 검증 전까지 '부분 지원(실험)' 표시 + HWPX/PDF 변환 안내. OCR 미구현.

### D-011 (2026-10-29) 엑셀 수식·캐시값
- 선택: 수식 셀 옆에 Python 확인값 열을 두고, `검산` 시트에서 수식값−확인값 차이를 표시. 통합문서는 열 때 전체 재계산(fullCalcOnLoad).
  테스트에서 LibreOffice headless로 재계산해 수식 결과와 Python 값을 비교.
- 근거: openpyxl은 수식 캐시값을 쓰지 못함.

### D-012 (2026-10-29) HW·SW 추천
- 선택: 입력 가정 기반 규칙 엔진 + 수동 등록 공식 자료(URL·확인일·상태). 서버 측 URL 조회는 `OFFICIAL_SOURCE_ALLOWLIST` 도메인만, 사설·루프백·링크로컬·메타데이터 IP 차단.
- 클라우드는 인스턴스 사양 미제시(사용자 요청).
- 기본 제공 SW 후보 정보는 '현재 상태 미확인'(모델 지식 기반)으로 표시.

## 과거 결정
- 없음
