# HANDOFF — 인수인계 (최종 갱신 2026-11-03, D-027)

## 1. 현재 위치
- 저장소: `storm8787/cj-sw-design`(Public) · 작업 브랜치: `claude/kind-franklin-pjcpsr`(PR #9 병합 후 최신 main 99618bc에서 다시 시작)
- PR #1~#9 모두 `main`에 병합. 이번 작업(D-027 끝수 처리)은 새 PR — **main 병합 전**.
- 배포 상태:
  - 실제 앱: 사용자가 Render(`https://sw-design-helper.onrender.com`)에 배포해 운영 중(사용자 전달). main 병합 시 Render가 자동 재배포한다. 이번 작업 환경에서는 이 주소에 접속할 수 없어 직접 확인하지 못했다.
    - 권장 모델 구성(`OPENAI_MODEL=gpt-6-luna`, `OPENAI_MODEL_FP_CANDIDATES=gpt-6.1-sol`)이 기존 Render 서비스에 적용되었는지는 **미확인**. 화면 오른쪽 위 AI 표시로 확인한다(`docs/AI_COST.md` §7).
  - 샘플 시연판: `https://storm8787.github.io/cj-sw-design/`(main 병합 시 자동 재배포). 이번 작업 환경에서 접속 확인은 못 했다.
- 대상 사용자: **설계·FP 비전문가 공무원**. 제출 대상: 2026 공공 AI 대전환 챌린지 세션 1(`docs/SUBMISSION.md`, 마감 2026-11-11).

### 이번 작업(2026-11-03, D-027) — 끝수 처리 점검·화면·계산·엑셀 일치
- 원인:
  - 기본값이 원 미만 절사였다. 사용자 사례 총액 26,735,177원은 이 설정에서 정확히 성립한다.
  - 10원 이상 단위에서도 총액은 공급가액+부가세 단순 합이라, 직접경비가 단위 배수가 아니면 총액이 단위 배수가 아닐 수 있었다.
- 조치:
  - 새 산정 기본값을 10원 미만 절사로 바꿨다.
  - 최종 총액에도 끝수를 적용하고 차액을 '최종 끝수조정(참고 조정)' 행으로 표시한다(화면·엑셀 수식·검산 동일).
  - 끝수 이름에 자리와 예시를 함께 보여 주고, 설정 변경 전후와 재산정 안내를 표시한다.
  - 목표액이 단위 배수가 아니면 충돌을 경고한다.
- 과거 견적은 당시 금액·방식 그대로 남는다. 원 미만 견적은 상태도 그대로이고, 10원 이상 이전 견적은 '갱신 필요'로 바뀐다.
- 근거: FP_RULES §5·§6, VALIDATION §12, D-027. PR은 main 병합 전이다.

### 이전 작업(2026-11-02, D-026, PR #9 병합) — Windows 로컬 실행 시험판(미서명)
| 작업 | 결과 | 근거 |
|---|---|---|
| 런처 | `backend/desktop/`: 127.0.0.1 바인딩, 선호 포트 사용 중이면 빈 포트, 한 사용자 한 인스턴스(잠금+실행 정보 대조), 준비 확인 후 브라우저, 60초 시한, 정상 종료 시 작업 '중단' 기록·DB 닫기, 최소 tkinter 창(상태·브라우저·설정·데이터 폴더·종료) | `docs/WINDOWS.md` |
| 설정·비밀값 | 첫 실행 비밀번호(해시), 설치별 세션 키·OpenAI 키는 DPAPI 보호 파일(`%LOCALAPPDATA%\CJ-SW-Design\config`), 앱 설정 환경변수 정리 후 런처 값(운영 모드·인증·CSRF 유지, 로컬 http 쿠키) | `desktop/config.py`, `server.py` |
| 패키징 | PyInstaller 6.22.3 one-folder(창 모드), Python 3.13.14 런타임 포함, 일반 화면 빌드·예제·기준값 포함, 금지 파일 검사·ZIP·SHA-256·build_info | `desktop/cj-sw-design.spec`, `build.py` |
| Windows 검증 | `.github/workflows/windows.yml`이 ZIP을 한글·공백 경로에 풀어 최소 PATH로 실행파일을 띄우고 `desktop/smoke.py` + 기존 E2E 3종 실행, artifact 14일 | VALIDATION §11 |
| AI 오류 안내 | 인증서 확인 실패·프록시 실패를 구분(검증은 끄지 않음), Windows 인증서 저장소 사용(truststore) | `app/ai/provider.py` |

### 이전 작업(2026-10-30, D-025, PR #8 병합) — 처음 보는 평가자·사용자가 이해하고 실행할 수 있게
| 작업 | 결과 | 근거 |
|---|---|---|
| README 재구성 | 소개·실제 앱/시연판/내 PC 비교·입력→출력·예제·Docker 실행·AI 비용·제약·문서 표. 개발 세부는 `docs/DEVELOPMENT.md`로 이동(삭제 없음) | README.md |
| 예제로 체험하기 | 첫 화면 접힌 영역에 예제 A(구상)·B(참고문서)·C(기존 문서 검토). 원본은 `examples/`, 서버는 허용 목록 파일만 `/api/examples/`로 제공, 시연판은 정적 파일. 누르기만으로 프로젝트·AI 호출 없음 | `examples/README.md`, `e2e/examples.cjs` |
| 평가자 문서 | 구동안내서 초안([양식 2-1] 7항목), 평가자 체험 순서, 제출 체크리스트·시연영상 구성(촬영 전)·평가 항목별 근거/한계, 외부 구성요소·라이선스 | `docs/RUN_GUIDE.md`, `EVALUATOR_GUIDE.md`, `SUBMISSION.md`, `THIRD_PARTY.md` |
| 실행 경로 버그 | `.env.example`의 `DATA_DIR=./data`가 Docker `--env-file`에서 이미지 기본 `/data`를 덮어 볼륨 밖에 저장되던 문제 → 주석 처리 | `.env.example`, VALIDATION §10 |

참가 안내 원문은 첨부되지 않아 다시 확인하지 못했다(사용자 요약 기준). 제출·메일 발송·GitLab 설정·자동배포 변경은 하지 않았다.

### 이전 작업(2026-10-30, D-023·D-024, PR #7 병합)
| 작업 | 결과 | 근거 |
|---|---|---|
| AI 사용량 측정 | 작업마다 입력·캐시·출력·추론 토큰·시간·실패 저장, 작업 상태에 호출 모델·토큰 표시. 작업 제출 때 모델·추론 설정 고정, 재사용 키에 모델 포함 | `backend/app/ai/usage.py`, `jobs.py` |
| 모델 비교시험 | 가상 3사례, sol 1·terra 1·luna 5·혼합 2회, 추정 $1.34 | `docs/AI_COST.md` |
| 기본 모델 | `gpt-6-luna` + FP 후보만 `gpt-6.1-sol`. 약 68~75% 절감(이 사례·단가 가정). luna 단독은 FP 후보 필수 처리 누락으로 불채택 | render.yaml, .env.example |
| FP 후보 검증 | 처리 후보 없는 기능을 코드가 찾아 1회 재요청·경고 | `tasks.fp_function_gaps` |
| 엑셀 서식 | 산출내역서형 업무 서식·인쇄 설정. 같은 가상 4종 서식 전후 ID·점수·금액 차이 0, LibreOffice 재계산 검산 전부 일치 | `docs/EXCEL_FORMAT.md` |

### 이전 작업(D-022, PR #6 병합) 요약 — 사용자 산출물 '충주여행 반값세일 홈페이지 구축_설계산출물' 분석에서 출발
| 관찰된 문제 | 원인 | 조치 |
|---|---|---|
| 확정 0건인데 '완료'·0원 견적 | 집계 0건도 complete로 판단 | 산정 상태(미산정/부분/추정/확정), 0건이면 금액 없음 |
| 간이법 화면·엑셀에 DET 누락 경고 | 정통법 메모를 공통 경고로 붙임 | 정통법 메모 분리(`detailed_note`) |
| 정통법을 하려면 DET·FTR 숫자를 사람이 입력 | 숫자 입력 외 경로 없음 | 기능 입력·출력, 데이터 항목·하위 그룹 목록에서 코드가 셈(FP_RULES §4-1) |
| 확정해야만 집계 → 비전문가가 진행 불가 | 업무 확인과 기술 검토가 한 상태 | `scope_confirmed`(업무 확인) 분리, 업무 확인만으로 간이법 추정 산정 |
| FP 후보 재실행 시 중복(PR-008) | 정확히 같은 이름만 거름 | 갱신 변경안·비슷함 표시·적용 시 merged, 자동 삭제 없음 |
| 일본어 혼입 | AI 언어 이탈 | 감지 후 1회 재요청, 남으면 항목 표시 |
| 요구사항 검수 기준 비어 있음 | 기능 검수 기준을 쓰지 않음 | 연결 기능 기준으로 보완(과업지시서 9절·엑셀) |
| '확인 필요: 없음' | 질문·가정만 모음 | 확인 목록 5구분(화면·과업지시서 10절·엑셀 근거 시트) |
| 개요 빈칸 | 제안 수단 없음 | '빈 항목 채우기 제안'(채운 칸 유지) |
| (샘플 모드) 문장 그대로 기능·데이터명, 요구사항마다 ILF | 규칙이 문장형 요구사항을 처리 못 함 | 짧은 제목·목적어 명사·같은 대상 묶기·조회/통계는 새 데이터 없음 |

## 2. 구현 현황 (PROJECT_SPEC ID 기준)

| 구분 | 상태 | 비고 |
|---|---|---|
| 공통 구조 SPEC-01~09 | 완료 | Docker 이미지 빌드·실행·재배포 영속성 확인. 배포 서비스와 같은 설정(root 소유 디스크·PORT·HTTPS)으로 로컬 점검 완료. Render 배포는 사용자가 진행(작업 환경에서 접속 확인 못 함) |
| 핵심 데이터 SPEC-10~19 | 완료 | 고유 ID, 1:N 연결, 영향 표시, 견적 스냅샷, 변경안 적용 |
| A 프로젝트 관리 | 완료 | 생성·목록·이름 변경·이어하기·삭제(이름 확인)·샘플 2종 |
| B 구상 기반 설계 | 완료 | 질문 은행 26종(공통+목적별 트리거). 실제 AI 질문 생성은 OpenAI로 확인(VALIDATION §5-3) |
| C 참고문서 기반 | 완료(HWP 실험적) | PDF/HWPX/DOCX/XLSX/TXT/MD. HWP 5.0 본문 텍스트 추출은 실제 HWP 샘플 미검증 → '실험' 표시. OCR 미구현(스캔 PDF는 '스캔본'으로 표시) |
| D 설계 작업대 | 완료 | 요구사항·업무흐름·기능·화면·데이터·연계·검수·과업 초안(사용자 수정 보존), 용어 설명 |
| E FP 산정 | 완료 | 간이·정통 별도 경로, 업무 확인/기술 검토 분리, 산정 상태 4단계, 근거 목록 DET·FTR/RET 집계(시스템 규칙), 중복·경계·연결·언어 검사 |
| F 개발비·목표예산 | 완료 | 기준 버전·시나리오 분리, Decimal, 끝수 설정, 부가세 역산 |
| G 문서 검토 | 완료(규칙 기반) | AI 보조 검토는 미구현(후속) |
| H HW·SW 추천 | 완료(규칙 기반) | 공식 자료 등록·서버 조회(제목 확인)·사용자 확인 입력. 최신 버전 자동 판정은 하지 않음 |
| 엑셀 X1~X6 | 완료 | 12시트+검산, LibreOffice 재계산 일치 확인 |
| 품질 Q1~Q12 | 완료 | 단일 관리자 인증, CSRF, 업로드 검증, SSRF 차단, 백업·복원, 작업 재사용·중단 표시 |
| 여러 AI 연결(D-018) | 완료 | OpenAI 기본·Anthropic·OpenAI 호환 상용/사내 LLM·샘플을 동시에 설정, 프로젝트별 선택. OpenAI만 실제 호출 확인 |
| 샘플 시연판(D-020) | 완료·배포됨 | 정적 빌드·샘플 2종(생성기·검증)·읽기 전용 화면·Pages 워크플로·시연 E2E. main 병합 시 자동 재배포 |
| 예제 체험·평가자 안내(D-025) | 완료 | 예제 3종(`examples/`), 첫 화면·시연판 진입, README·구동안내서 초안·평가자 순서·제출 체크리스트. 공식 양식 PDF·영상·GitLab 제출은 사용자 작업 |
| 실제 AI 호출 | OpenAI 검증 / 그 외 **미검증** | 2026-10-30 `gpt-6.1-sol`·`gpt-6.1-terra`·`gpt-6-luna` 가상 3사례 비교(`docs/AI_COST.md`), 권장 구성 luna+FP 후보 sol. 이전: `gpt-6.1-sol` 다섯 작업(VALIDATION §5-3). Anthropic·사내/상용 LLM은 실제 호출 미검증 |
| 엑셀 산출물 서식 | 완료 | 산출내역서형 서식·인쇄(2026-10-30). Microsoft Excel 화면·인쇄 미리보기는 미확인(LibreOffice로 확인) |

## 3. 테스트 결과 (상세: `docs/VALIDATION.md`)
- API 응답 charset(2026-11-06, VALIDATION §14, D-029): 모든 JSON 응답에 `charset=utf-8` 명시. 백엔드 pytest **193 passed**.
  브라우저로 API 주소를 직접 열었을 때 한글이 CP949로 읽혀 깨지던 문제. 실제 Render 배포본 표시는 사용자 확인 대기.
- 제출 전 검수 지적사항 수정(2026-11-06, VALIDATION §13, D-028): 백엔드 pytest **191 passed**, E2E 5종 통과,
  예제 A 엑셀 검산 35/35 일치(총액 54,780,140원 불변), 예제 C 검토 5·8·4 불변.
  로그인 실패 제한은 **로컬 프록시 재현 환경에서만** 검증(A 429 / B 200, 위조 우회 불가) — 실제 Render는 미확인.
- Windows 시험판(2026-11-02, VALIDATION §11): windows-2025 runner에서 ZIP을 새로 풀어 실행파일로 109개 항목 통과(첫 실행·파서·견적·엑셀·기존 E2E 3종·중복 실행·재실행·폴더 이동·포트 충돌·강제 종료·시작 실패·가짜 키·창 모드). 개발 도구 없는 실제 직원 PC는 미검증.
- 백엔드 pytest **185 passed**(2026-11-03, 끝수 처리 시험 포함). 2026-11-02: **144 passed**. 이전: **138 passed**(2026-10-30, 예제 3건 포함), 프런트 타입검사·일반 빌드·시연 빌드 성공, 로컬 운영 모드에서 `flow`·`reference`·`ux`·`examples`·`demo` E2E 통과, README의 Docker 경로·소스 실행(bash)을 깨끗한 위치에서 재현(VALIDATION §10). PowerShell 명령은 실행하지 않았다(문법만).
- 샘플 시연판(VALIDATION §5-5): 정적 서버만으로 `e2e/demo.cjs` 통과 — `/api`·외부·404·콘솔 오류 0건, 모바일·태블릿, 샘플 엑셀 재계산 검산 일치.
- 배포 설정 로컬 점검(2026-10-30, VALIDATION §5-4): HTTPS 프록시 뒤 운영 모드 컨테이너에서 구상 기반(`e2e/flow.cjs`)·참고문서 기반(`e2e/reference.cjs`) 브라우저 E2E 통과, 컨테이너 교체 후 데이터 유지, 실제 OpenAI 질문·문서 추출 성공, 엑셀 다운로드, 로그에 비밀값·원문 없음.
- GitHub Actions(`.github/workflows/ci.yml`): PR #3 최신 커밋(56998ac)에서 backend·frontend·e2e·docker 모두 성공. 이번 브랜치부터 e2e job이 참고문서 E2E도 실행.

## 4. 알려진 문제·제약
1. KOSA 가이드 원문 미확인(네트워크 차단) — 단가 605,784원은 '2024 가이드' 표기 양식값, 이윤율 0.20은 양식 예시값, 끝수·단계 비율은 시스템/사용자 설정. `docs/FP_RULES.md §8`.
2. 샘플 모드 규칙은 표현 기반이라 FP 후보가 과대·과소일 수 있음(모두 '초안'으로 들어가 업무 확인 필요). 문장형 요구사항 처리는 보완했지만 동의어(예: '환급'과 '반환')는 묶지 못함.
9. DET·FTR/RET 근거 목록 집계는 시스템 규칙(원문 미확인, FP_RULES §4-1). 업무 확인만 한 항목이 있는 견적은 '추정 산정'이며 FP 전문가 검토 전 확정 금액이 아니다.
10. 이번 수정은 실제 AI(OpenAI) 호출로 다시 검증하지 않았다(키를 이 세션에 두지 않음). 프롬프트 변경(숫자 대신 항목 목록, 언어 재요청)은 모의 공급자 테스트로만 확인.
3. 실 HWP 미검증, OCR 없음, PDF 표 구조 미보존.
4. 단일 프로세스 내 작업 실행(스레드). 다중 인스턴스 배포는 고려하지 않음(배포 시 1대 고정). 재배포·재시작 때 실행 중이던 AI 작업은 '중단' 표시 후 재시도.
5. 첨부 원본은 JSON 백업에 포함되지 않음(볼륨 백업 별도 필요).
6. 이 작업 환경 특성: Docker Hub 429·ghcr 차단·TLS 검사 프록시 → 로컬 Docker 빌드는 mirror.gcr.io 기반 이미지 + `--secret id=extra_ca` 사용.
7. 로그인 실패 제한(5회/5분)은 **접속자별**로 센다(D-028, 2026-11-06). `X-Forwarded-For`를 오른쪽에서 `TRUSTED_PROXY_HOPS`번째 값으로 식별하며,
   기본값 0은 헤더를 믿지 않고(직접 노출에서 안전) `render.yaml`이 `1`로 선언한다. 왼쪽 위조로는 제한을 피할 수 없다.
   **Render의 실제 프록시 단 수는 미확인** — 2단이면 다시 공용 잠금이 되므로 배포 후 `docs/DEPLOY.md` §4-1(`/api/system`의 `client`)로 확인해 값을 맞춰야 한다.
8. 샘플 시연판은 읽기 전용 정적 화면(새 계산·생성 없음). 샘플 데이터는 커밋하지 않고 빌드 때 `backend/tools/demo_data.py`로 생성하므로, 화면·모델·계산을 바꾼 뒤 `npm run demo:data`가 실패하면 생성기(`build_a`·`build_b`)를 함께 고쳐야 Pages 배포가 진행됨.

## 5. 다음 작업(우선순위)
000. (사용자) PR #9 artifact의 Windows 시험판 ZIP을 실제 직원 PC(개발 도구 없음)에서 `docs/WINDOWS.md` §7 체크리스트로 확인 → SmartScreen·백신·프록시 반응 기록 → 결과에 따라 코드 서명·배포 채널(Release 등) 결정(사용자 결정, 이번 범위 아님).
00. (사용자, 제출) `docs/SUBMISSION.md` 체크리스트: 참가신청서·구동안내서 PDF(`docs/RUN_GUIDE.md`를 공식 양식에 옮김)·시연영상(§4 구성안)·GitLab 비공개 저장소·Topics·심사위원 권한·로그인 정보 별도 전달. 제출 커밋 태그와 Render 배포 커밋 일치 확인(§3). 참가 안내 원문과 항목 재대조.
0. (사용자) 이번 PR 검토·병합 → Render 환경변수 `OPENAI_MODEL=gpt-6-luna`, `OPENAI_MODEL_FP_CANDIDATES=gpt-6.1-sol` 확인·변경(`docs/AI_COST.md` §7) → 엑셀 내려받아 인쇄 미리보기 확인(Microsoft Excel) → OpenAI 사용량 화면에서 모델별 금액 확인.
0-1. (이전) PR 검토·병합 → Render 자동 재배포 확인 → `docs/USER_TEST.md` §C(비전문가 흐름) 실행. 기존 프로젝트는 그대로 열리며(삭제·재설정 없음) 초안 FP는 '업무 확인 전'으로 보인다. 결과를 VALIDATION에 '배포 환경 확인'으로 기록.
1. (사용자) 시연 주소 `https://storm8787.github.io/cj-sw-design/` 접속 확인(샘플 A·B, 단계 이동, 샘플 엑셀). 문제가 있으면 화면·문구를 알려 주면 수정 후 main 병합으로 재배포.
2. (사용자, Render 배포는 완료) `docs/USER_TEST.md` A·B 순서와 첫 화면 '예제로 체험하기'로 직접 테스트 → 문제 기록을 다음 작업으로 반영. 배포 후 VALIDATION에 실제 배포 확인 결과 기록.
3. 사내/상용 LLM 또는 Anthropic을 쓸 경우 `LLM_*`·`ANTHROPIC_*`로 VALIDATION §5-3과 같은 절차(다섯 작업 각 1회) 실행. 설계 작업은 출력이 길어 1~2분 걸림(기본 시간 제한 600초).
4. sw.or.kr 접근 가능한 환경에서 가이드 2025 개정판 확인 → 차이가 있으면 새 기준 JSON 추가(기존 파일 수정 금지, 과거 견적 보존).
5. 실제 HWP 샘플로 추출 검증, 필요 시 변환 도구 연동 검토.
6. 운영(기관 서비스) 배포 결정(기관 서버/클라우드, 실데이터 보안 검토, 백업 정책) — 사용자 결정 필요. 테스트 배포와 별개.
7. AI 보조 문서 검토, 다중 사용자·권한, 유지관리비 등 후속 확장(PROJECT_SPEC §7).

## 6. 재개 명령
```bash
git switch claude/kind-franklin-pjcpsr
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
- AI 사용 시: 기본 OpenAI는 `OPENAI_API_KEY`·`OPENAI_MODEL`(권장 `gpt-6-luna`)·`OPENAI_MODEL_FP_CANDIDATES`(권장 `gpt-6.1-sol`), 그 밖은 `.env.example`의 AI 연결 항목 참고. 각 서비스 결제 화면에서 월 지출 한도 설정. 외부 전송 동의 정책을 기관 보안 지침과 맞출 것.
- GitHub Actions: 비공개 상태에서는 계정 결제·지출 한도 문제로 작업 시작이 거부되었음(2026-10-29). Public 전환 후 정상 실행. 다시 비공개로 바꾸면 Billing & plans의 Actions 한도를 확인해야 함.
- 공개 저장소이므로 실제 사업 문서·DB·키·`.env`는 절대 커밋하지 않는다(.gitignore로 차단, 이력 점검 완료).

## 8. UI·UX 검증과 다음 작업 (2026-10-30)
- `docs/VALIDATION.md` §7: 타입검사·두 빌드·백엔드 120개·일반 앱 2종 E2E·시연 E2E·추가 UX 검사 통과.
- 스크린샷: `/workspace/artifacts/cj-design/before`, `after`. 저장소 밖의 비교 산출물이며 커밋하지 않는다.
- 실제 모바일 기기·스크린리더, 공개 Pages에서 새 UI, Render, 유료 AI는 미검증. 브라우저는 시스템 Chromium/Playwright 1.63.0으로 확인.
- UI 구현 커밋 `c572419`(원격 `design/clear-workflow`). Codex 세션에서는 PR 생성 API가 Forbidden이라, Claude Code가 이 브랜치(`claude/kind-franklin-pjcpsr`)에 병합해 PR로 올렸다(PR 본문이 기존 `docs/UI_UX_PR.md` 초안을 대신함). main 병합은 사용자 결정.
