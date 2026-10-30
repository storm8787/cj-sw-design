# 구동안내서 초안 — 정보화 설계 도우미 ([양식 2-1] 항목 순서)

> 제출용 PDF(A4 3~5쪽)로 옮길 초안입니다. Markdown 분량만으로 쪽수를 검증하지 않았습니다. PDF로 만든 뒤 쪽수를 확인하세요.
> 참가 안내서 원문은 이 작업에서 다시 확인하지 못했습니다. 항목 구성은 사용자가 전달한 요강 요약(양식 2-1의 7개 항목)을 따랐습니다.

## 1. 실행 환경
| 구분 | 웹으로 체험(권장) | 내 PC에서 실행 |
|---|---|---|
| OS | 무관 | Windows 10/11, macOS, Linux |
| 브라우저 | 최신 Chrome·Edge·Safari·Firefox | 같음 |
| 필요 소프트웨어 | 없음 | Docker Desktop(Windows·macOS) 또는 Docker Engine(Linux). 소스 실행 시 Python 3.12+·uv·Node.js 22 |
| 권장 사양 | — | 메모리 2GB 이상 여유, 디스크 2GB(이미지·데이터). 클라우드 배포안은 서버 1대 512MB 메모리 기준(render.yaml Starter) |
| 네트워크 | 인터넷 | 샘플 모드는 외부 접속 불필요(이미지 빌드 때 패키지 다운로드). AI 사용 시 AI 공급자 API 접속 |

## 2. 설치·실행 절차
### 2-1. 웹으로 체험(설치 없음)
1. 실제 앱 https://sw-design-helper.onrender.com 접속 → 별도로 전달받은 관리자 비밀번호로 **로그인**.
2. 첫 화면 '무엇을 하시겠어요?'에서 시작 방식을 고르거나 **예제로 체험하기**를 펼칩니다(4절).
3. 설치 없이 화면만 보려면 읽기 전용 시연판 https://storm8787.github.io/cj-sw-design/ (로그인·저장·AI 실행 없음).

### 2-2. 내 PC에서 Docker로 실행(권장, 2026-10-30 Linux에서 실행 확인)
저장소를 받은 폴더에서:
1. `.env.example`을 `.env`로 복사하고 `SECRET_KEY`(32자 이상 무작위), `ADMIN_PASSWORD`(10자 이상)를 채웁니다. `DATA_DIR`은 주석 그대로 둡니다.
2. 이미지 만들기:
   ```bash
   docker build -t sw-design-helper .
   ```
3. 실행:
   ```bash
   docker run -d -p 8000:8000 -v swdata:/data --env-file .env --name sw-design-helper sw-design-helper
   ```
4. http://localhost:8000 접속 → `ADMIN_PASSWORD`로 로그인.
- 데이터 저장 위치: Docker 볼륨 `swdata`(컨테이너를 지우고 다시 만들어도 유지). 끄기·켜기: `docker stop sw-design-helper` / `docker start sw-design-helper`.
- 로컬은 http이므로 `COOKIE_SECURE=false`(기본). https 운영에서만 `true`.
- 사내 SSL 검사 프록시 망에서 빌드가 실패하면 기관 루트 인증서를 넘깁니다: `docker build --secret id=extra_ca,src=<인증서.pem> -t sw-design-helper .`

### 2-3. Docker 없이 소스로 실행(대안)
필요: Python 3.12+와 uv, Node.js 22. 앱은 `.env` 파일을 읽지 않으므로 환경변수를 터미널에서 지정합니다.

macOS·Linux(bash) — 2026-10-30 Linux에서 같은 방식으로 실행 확인:
```bash
cd frontend && npm ci && npm run build && cd ../backend && uv sync
```

```bash
SECRET_KEY=<32자 이상> ADMIN_PASSWORD=<10자 이상> uv run uvicorn app.main:create_app --factory --port 8000
```

Windows PowerShell — 이 작업 환경에서는 실행해 보지 못했습니다(문법만 대조):
```powershell
cd frontend; npm ci; npm run build; cd ..\backend; uv sync
```

```powershell
$env:SECRET_KEY = "<32자 이상>"; $env:ADMIN_PASSWORD = "<10자 이상>"; uv run uvicorn app.main:create_app --factory --port 8000
```
- `backend` 폴더에서 실행합니다. 화면은 `frontend/dist`를 자동으로 찾아 함께 제공합니다. 데이터는 `backend/data`에 저장됩니다. 종료는 Ctrl+C.

## 3. LLM 연결 설정
- **키가 없으면 샘플 모드**(서버 규칙 기반, AI 아님)로 전 단계를 쓸 수 있고 화면·엑셀에 '샘플 모드'로 표시됩니다.
- 키·모델 입력 위치: Docker는 `.env`, 클라우드는 배포 화면의 환경변수, 소스 실행은 터미널 환경변수. 화면에는 키를 입력하지 않습니다.
  - OpenAI(기본): `OPENAI_API_KEY`, `OPENAI_MODEL`, (선택) 작업별 `OPENAI_MODEL_FP_CANDIDATES` 등.
  - Anthropic: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`.
  - OpenAI 호환 상용·사내 LLM: `LLM_BASE_URL`, `LLM_MODEL`(+선택 항목).
- 교체 방법: 여러 연결을 동시에 설정해 두고 프로젝트마다 **1 개요 → AI 연결**에서 고릅니다. 공급자 코드는 `backend/app/ai/provider.py`의 `generate_json()` 하나만 구현하면 됩니다.
- **실제로 시험한 것과 연결만 있는 것의 구분**
  - 실제 호출 시험: OpenAI만. `gpt-6.1-sol`, `gpt-6.1-terra`, `gpt-6-luna`로 가상 3사례 비교([AI_COST](AI_COST.md)).
  - 권장 구성: 기본 `gpt-6-luna`, FP 후보만 `gpt-6.1-sol`.
  - Anthropic·사내 LLM: 연결 코드와 모의 시험만 있고 실제 호출은 미검증.
  - 운영 서버에 권장 구성이 적용됐는지는 화면 상단 AI 표시로 확인합니다.
- 외부 전송: AI 실행 버튼을 누를 때마다 전송 범위를 보여 주고 동의를 받습니다. 업로드만으로는 전송하지 않습니다.

## 4. 모의데이터 안내
모두 가상 자료입니다(저장소 `examples/`, 첫 화면 '예제로 체험하기'에서 같은 파일 내려받기). 상세: [examples/README.md](../examples/README.md)

| 파일 | 용도 | 투입 방법 |
|---|---|---|
| `examples/A-idea/idea_example.md` | 구상 입력 예시(사업명·구상·목표예산·기능 일곱 줄) | '예제 값으로 시작'으로 만들기 창 채움 → '3 요구사항' 기능 입력란에 일곱 줄 붙여 넣기 |
| `examples/B-reference/reference_task_order.txt` | 가상 타 기관 과업지시서(예산·기간·특정 제품·개인정보·문서 속 지시문 포함) | '참고문서로 시작하기' → '2 자료·질문'에 종류 '참고문서(타 기관)'로 올리기 → '항목 추출' |
| `examples/C-review/vendor_task.txt`, `vendor_design.txt`, `vendor_fp.csv`(화면에서는 `vendor_fp.xlsx`), `vendor_cost.txt` | 오류를 일부러 넣은 가상 업체 제출 문서 | '기존 문서 검토하기' → '2 자료·질문'에 각각 업체 과업지시서·설계서·FP 산정표·금액 산출서로 올리기 → '6 검토·추천' → '검토 실행' |
| `examples/C-review/expected_findings.md` | 예제 C의 넣어 둔 오류·기대 결과·탐지 한계 | 검토 결과와 비교 |

원본 파일은 읽기 전용으로 둡니다. 앱에 올린 뒤의 결과는 앱 프로젝트에 따로 저장됩니다.

## 5. 기능 사용 순서(핵심 흐름)
1. **구상 → 설계 → FP·개발비 → 엑셀**
   1. '구상으로 시작하기' → '2 자료·질문' **질문 받기**(답·모름·나중에)
   2. '3 요구사항' **요구사항 초안 만들기** → 변경안 비교·적용
   3. '4 설계' **요구사항으로 설계 초안 만들기**
   4. '5 FP·개발비' **기능·데이터로 FP 후보 만들기** → 후보마다 **업무 확인**(있음/없음/모름)
   5. **기준 산정 실행·저장** → (목표예산이 있으면) **시나리오 만들기**
   6. '7 엑셀' **엑셀 내려받기**
2. **참고문서 재설계** — 문서 올리기 → **항목 추출** → 유지·수정(이유)·제외(이유) → '3 요구사항'에서 원문 위치가 연결된 요구사항 확인.
3. **기존 문서 검토** — 업체 문서 종류별로 올리기 → '6 검토·추천' **검토 실행** → 판정별 필터(확인 일치·차이 발견·확인 필요·근거 부족).

역할 분담:
- **AI(또는 샘플 규칙)**: 질문·요구사항·설계 초안·FP 후보·문서 항목 추출을 '변경안'으로 제안합니다. 사용자가 골라 적용합니다.
- **Python 코드**: FP 가중치·복잡도·합계, 개발비(Decimal)·끝수, 검토 대조, 엑셀 수식·검산.

## 6. 알려진 제약
- **산정 기준:** FP 단가·보정계수는 2026 산정양식 수식에서 추출했고 KOSA 가이드 원문은 미확인입니다. 이윤율·끝수·단계 비율은 '확인 필요'로 표시됩니다.
- **결과의 성격:** 공식 FP 감정·법적 적합성 보증 도구가 아닙니다. 업무 확인만 한 FP는 '추정 산정'이며 전문가 검토 전입니다. 검산 '일치'는 계산 일치일 뿐 설계 타당성 보증이 아닙니다.
- **검토 기능:** 규칙 기반입니다. 요구사항 ID 대조, 같은 이름의 중복만 찾고, 실제 성능·연계·보안은 판단하지 않습니다([예제 C 한계](../examples/C-review/expected_findings.md)).
- **사용 범위:** 단일 관리자 로그인, HWP 실험적, 스캔 PDF OCR 없음. 엑셀은 LibreOffice로 확인했고 Microsoft Excel 화면은 미확인입니다.
- **오픈소스·외부 구성요소:** [THIRD_PARTY](THIRD_PARTY.md).
  - 주요 런타임은 FastAPI·Uvicorn·Pydantic·openpyxl·pypdf·python-docx·OpenAI/Anthropic SDK(Python), React(화면)입니다. MIT·BSD·Apache-2.0 계열을 메타데이터로 확인했습니다.
  - 의존성 전체(하위 의존성 포함)의 재배포 조건은 다 확인하지 못했습니다.
  - 이 저장소 자체의 라이선스 파일은 아직 없습니다(사용자 결정 필요).

## 7. 개발 경위 요약
- **문제 인식:**
  - 신규 정보화사업을 기획하는 공무원은 업무 목적은 설명할 수 있습니다. 그러나 요구사항을 설계로 구체화하고 FP로 개발비를 산정하는 일은 전문 영역입니다.
  - 그래서 타 기관 문서를 그대로 베끼거나, 근거 없는 금액에 맞춰 기능을 줄이기 쉽습니다.
  - 숫자(DET·FTR)를 직접 넣으라는 도구는 비전문가에게 진입 장벽입니다.
- **접근:**
  - 사용자는 업무를 설명하고 업무상 선택(있음/없음/모름, 처리 종류)만 확인합니다.
  - AI는 질문·초안·분류 후보를 '변경안'으로 제안하고, 계산·검산은 코드가 합니다.
  - 정보가 부족하면 확정하지 않고 '추정·부분·미산정'과 확인 목록으로 남깁니다.
  - 기준 산정과 목표예산 참고 시나리오를 분리해 요구 기능을 보존합니다.
  - 모든 항목을 고유 ID로 연결해 요구사항 → 설계 → FP → 견적 → 엑셀을 추적합니다.
- **진행:**
  - 규칙 기반 샘플 모드로 전 흐름을 먼저 만들었습니다.
  - 실제 OpenAI 호출로 검증했습니다.
  - 사용자가 실제로 써 본 산출물에서 '0원 견적·확정 0건인데 완료 표시·중복 후보'를 발견해 고쳤습니다.
  - 가상 사례 비교시험으로 품질을 유지하는 저비용 모델 구성을 골랐습니다.
  - 엑셀을 산출내역서형 인쇄 서식으로 개선했습니다.
- 효과는 실제 측정하지 않았습니다. 시간 절감률·정확도 수치는 제시하지 않습니다.
