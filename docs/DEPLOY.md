# DEPLOY — 테스트 배포 안내 (2026-10-30)

신규개발 기능을 실제 주소로 접속해 써 보기 위한 **테스트 배포** 절차다. 운영(기관 서비스) 배포가 아니다.
배포 서비스 가입·결제·비밀값 입력은 사용자가 직접 한다. 이 저장소와 문서에는 비밀값을 쓰지 않는다.

## 1. 추천안: Render 웹 서비스 1개 + 영속 디스크

| 항목 | 내용 |
|---|---|
| 서비스 | [Render](https://render.com) Web Service(Docker) — 저장소의 `Dockerfile`을 그대로 빌드 |
| 설정 파일 | 저장소 루트 `render.yaml`(Blueprint). 화면에서 저장소만 연결하면 아래 설정이 채워짐 |
| 지역 | Singapore(한국과 가장 가까운 Render 지역) |
| 인스턴스 | Starter(0.5 CPU / 512MB) 1대 — 로컬 점검 때 메모리 사용 약 73MB |
| 저장 | 1GB 디스크를 `/data`에 연결(SQLite DB·업로드 원본·사용자 기준). 재배포·재시작 후에도 유지 |
| 주소·HTTPS | `https://<서비스이름>.onrender.com` 자동 발급, 인증서 자동 |
| 배포 | `main` 브랜치에 커밋이 들어가면 자동 재배포(재배포 중 잠시 접속 불가, 실행 중이던 AI 작업은 '중단'으로 표시되어 재시도 가능) |

고른 이유: 현재 구조(Docker 이미지 1개가 화면+API 제공, SQLite 파일 저장, 작업 스레드)는 **서버 1대 + 영속 디스크**가 맞다.
Render는 GitHub 저장소 연결과 화면 입력만으로 배포·HTTPS·비밀값 관리가 되어 명령줄 도구가 필요 없다.

대안(참고): Fly.io(1대 512MB + 1GB 볼륨 약 월 3.8달러로 더 저렴하지만 `flyctl` 명령줄 도구 필요), 기관 VM에 Docker 직접 실행(README의 Docker 절).
**쓰면 안 되는 구성**: Render 무료 인스턴스(디스크가 붙지 않아 재시작마다 데이터 삭제, 일정 시간 미사용 시 잠듦), GitHub Pages(파이썬 서버 없음).

### 예상 비용(2026-10 검색 기준, 가입 전 Render 요금 화면에서 다시 확인)
- Starter 인스턴스 월 7달러 + 디스크 1GB 월 0.25달러 ≈ **월 7.25달러**(초 단위 일할 계산). 서비스를 삭제하면 과금 중지.
- OpenAI API 사용료 별도(쓴 만큼). 2026-10-29 실제 검증 1회(질문·요구사항·설계·FP 후보·문서 추출 각 1회)는 약 0.4~0.7달러로 추정. OpenAI 결제 화면에서 **월 한도**를 먼저 설정할 것.
- 이 세션에서는 render.com·fly.io 공식 페이지가 네트워크 정책으로 막혀 검색 결과로만 확인했다.

## 2. 필요한 설정 정리

| 목적 | 환경변수 | 값 | 입력 주체 |
|---|---|---|---|
| 운영 모드(인증 필수) | `APP_ENV` | `production` | render.yaml |
| 로그인 세션 서명 | `SECRET_KEY` | 무작위 32자 이상 | Render가 자동 생성(`generateValue`) |
| 로그인 비밀번호 | `ADMIN_PASSWORD` | 10자 이상 | **사용자** (Render 화면, 비밀값) |
| (선택) 비밀번호 해시 | `ADMIN_PASSWORD_HASH` | `scrypt$…` | 사용자 — 쓰면 `ADMIN_PASSWORD`는 지움. 생성: `cd backend && uv run python -m app.auth hash` |
| HTTPS 쿠키 | `COOKIE_SECURE` | `true` | render.yaml |
| 로그인 실패 제한 단위 | `TRUSTED_PROXY_HOPS` | **`2`** (2026-11-06 실제 배포 측정: 전달 체인 2단 = [접속자, Cloudflare 엣지]). 인프라가 바뀌면 §4-1로 다시 확인 | render.yaml |
| 데이터 영속 저장 | `DATA_DIR` + 디스크 | `/data`, 디스크 1GB를 `/data`에 연결 | render.yaml |
| AI(기본 OpenAI) | `OPENAI_API_KEY` | 사용자 키 | **사용자** (Render 화면, 비밀값). 비우면 샘플 모드 |
| AI 모델 | `OPENAI_MODEL` | `gpt-6-luna`(2026-10-30 비교시험 통과, `docs/AI_COST.md`) | render.yaml |
| AI 모델(FP 후보만) | `OPENAI_MODEL_FP_CANDIDATES` | `gpt-6.1-sol`(FP 후보는 상위 모델 유지) | render.yaml |
| 포트 | `PORT` | Render가 지정(기본 10000) | 자동 — 이미지가 `PORT`를 따라감 |
| 엑셀 다운로드 | (추가 설정 없음) | 로그인 쿠키로 `/api/projects/{id}/export.xlsx` 내려받기 | — |

- 업로드 한도 `MAX_UPLOAD_MB`(기본 30)·AI 시간 제한 `AI_TIMEOUT_SEC`(기본 600)는 기본값으로 충분하다.
- 다른 AI(Anthropic·사내/상용 LLM)는 `.env.example`의 항목을 Render 환경변수에 추가하면 프로젝트마다 고를 수 있다(실제 호출은 미검증).
- 컨테이너는 root로 시작해 `/data` 소유자만 맞춘 뒤 비루트(`app`)로 서버를 실행한다(`docker-entrypoint.sh`). 배포 서비스 디스크가 root 소유로 붙어도 동작한다.

## 3. 배포 절차(사용자)
1. `render.yaml`이 들어간 브랜치를 `main`에 병합(PR). Render는 `main`을 배포한다.
2. Render 가입 → 결제 수단 등록(Starter 유료).
3. Dashboard → **New → Blueprint** → GitHub 연결 → 저장소 `storm8787/cj-sw-design` 선택.
4. 입력란이 뜨면: `ADMIN_PASSWORD`(10자 이상, 남에게 알려 주지 않는 새 비밀번호), `OPENAI_API_KEY`(본인 키, 샘플 모드로만 볼 거면 비움).
5. **Apply** → 빌드·배포(수 분) → 서비스 화면의 `https://….onrender.com` 주소로 접속.
6. 확인: 주소 접속 시 로그인 화면 → 비밀번호 로그인 → 상단에 'OpenAI(ChatGPT) · gpt-6-luna (작업별: FP 후보 gpt-6.1-sol)'(키를 넣은 경우) 또는 '샘플 모드' 표시.

### 이미 배포한 서비스의 모델 바꾸기(2026-10-30)
`render.yaml`을 바꿔도 **기존 서비스의 환경변수는 자동으로 바뀌지 않을 수 있다**(Blueprint 동기화 여부에 따라 다름). Render → 서비스 → Environment에서 `OPENAI_MODEL=gpt-6-luna`로 바꾸고 `OPENAI_MODEL_FP_CANDIDATES=gpt-6.1-sol`을 추가한 뒤 저장(재시작). 확인: 상단 AI 표시, 각 AI 작업 상태의 '호출 모델 …'(질문·설계는 gpt-6-luna, FP 후보는 gpt-6.1-sol). 자세한 근거·확인 순서는 `docs/AI_COST.md` §7.

Blueprint 화면이 막히면 수동으로: New → Web Service → 저장소 선택 → Runtime **Docker**, Region **Singapore**, Instance **Starter**,
Health Check Path `/api/health`, Advanced → Disk 추가(Mount Path `/data`, 1GB) → 위 표의 환경변수 입력.

## 4. 운영 중 주의
- **실제 사업 문서·개인정보는 올리지 않는다.** 테스트 서버는 국외(싱가포르) 상용 클라우드다. 실데이터 사용은 기관 보안 검토 후 결정.
- 외부 AI로 보내는 내용은 요청마다 전송 범위를 보여 주고 동의를 받으며, 문서 원문은 문서별 동의가 따로 필요하다.
- 로그인 실패 5회/5분 제한은 **접속자별**로 걸린다(§4-1). 프록시 단 수가 맞지 않으면 모든 접속자가 함께 막힐 수 있으므로 배포 후 한 번 확인한다.
- 백업: 프로젝트별 '7 엑셀 → JSON 백업 내려받기'(업로드 원본 제외). 디스크 자체 백업(스냅샷)은 Render 안내를 확인.
- 비밀번호·키 교체: Render → 서비스 → Environment에서 값 변경 → 자동 재시작. `SECRET_KEY`를 바꾸면 모든 로그인 세션이 끊긴다.
- 테스트가 끝나면 Render에서 서비스(디스크 포함)를 삭제해 과금을 멈춘다. 삭제하면 데이터도 지워지므로 필요한 프로젝트는 먼저 JSON 백업.

## 4-1. 로그인 실패 제한이 '접속자별'로 걸리는지 확인(배포 후 1회, 2026-11-06 추가)

리버스 프록시 뒤에서는 서버가 보는 접속 주소가 프록시 주소라서, 설정이 맞지 않으면 **한 사람의 오타 5회가
다른 접속자까지 5분간 막는다**. 심사 기간에 여러 심사위원이 같은 비밀번호로 접속하므로 배포 후 한 번 확인한다.

앱은 `X-Forwarded-For`를 **오른쪽에서** `TRUSTED_PROXY_HOPS`번째 값으로 접속자를 식별한다.
왼쪽 값은 클라이언트가 위조할 수 있어 신뢰하지 않는다(`backend/app/auth.py::client_ip`).

1. **먼저 앱에 로그인한다**(`https://<서비스 주소>/` → 관리자 비밀번호). 그 **다음에 같은 브라우저 탭·창**에서
   `https://<서비스 주소>/api/system` 을 열고 `client` 항목을 본다.
   ```json
   "client": { "peer": "10.x.x.x", "forwarded_count": 1, "trusted_proxy_hops": 1,
               "login_throttle_key": "<내 공인 IP>", "shared_key_warning": "" }
   ```
   **반드시 주소창에 직접 입력·붙여넣기 한다.** 메일·메신저·문서의 링크를 클릭하면 안 된다 — 로그인 쿠키가
   `SameSite=strict`이라 **다른 사이트에서 넘어온 최초 이동에는 쿠키가 붙지 않고**, 로그인돼 있어도 401이 난다.

   - `{"detail":"로그인이 필요합니다."}`가 나왔을 때 — 원인이 셋이고 메시지는 모두 같다. 순서대로 가린다:
     1. **그 페이지에서 F5(새로고침)** → 정상으로 보이면 링크 클릭 때문이었다(새로고침은 같은 사이트 이동이라 쿠키가 붙는다). 끝.
     2. 그래도 401이면 앱(`/`)으로 가서 **다시 로그인** → 그 탭의 주소창을 고쳐 `/api/system`을 붙인다.
        세션은 12시간이면 만료되고, 재배포로 `SECRET_KEY`가 새로 생성되면 기존 로그인이 무효가 된다(둘 다 같은 401).
     3. 시크릿 창·다른 브라우저는 로그인 상태가 공유되지 않는다.
   - 참고: 세션이 무효가 돼도 화면(`/`)은 200으로 뜨고, 앱은 다음 API 호출에서 401을 받아 로그인 화면으로 돌아간다
     (`frontend/src/api.ts`의 `onUnauthorized`). 그래서 "화면은 로그인된 것처럼 보이는데 API만 401"인 상태가 생길 수 있다.
   - 한글이 `濡쒓렇…`처럼 깨져 보이면 **구버전이 배포된 것이다**. 2026-11-06부터 API 응답에
     `Content-Type: application/json; charset=utf-8`을 명시한다. Events에서 배포 커밋을 확인한다.
2. 판정
   - `login_throttle_key`가 **본인 공인 IP**(검색창에 "my ip"로 확인한 값)와 같고 `shared_key_warning`이 비어 있으면 **정상**. 더 할 일 없음.
   - `shared_key_warning`에 문구가 있으면 → 문구가 알려주는 값(= `forwarded_count`)을 그대로
     Render → 서비스 → **Environment** → `TRUSTED_PROXY_HOPS`에 넣고 저장(자동 재시작) → 1번을 다시 확인.
     경고는 두 가지다: ① 식별값이 `peer`(프록시 주소)와 같음 → 모든 접속자가 한 키로 묶임,
     ② 전달 체인이 설정보다 길다 → 중간 프록시·CDN 주소를 쓰고 있을 수 있음(2026-11-06에 실제로 이 경우였다).
   - `forwarded_count`가 `0`이면 프록시가 헤더를 주지 않는 것이므로 Render 지원에 문의한다. 이 경우에는 제한이 공용으로 걸리므로
     심사 안내에 "비밀번호 5회 실패 시 5분 뒤 재시도"를 적어 둔다.
3. **운영 서버에서 일부러 5회 실패를 만들어 확인하지 않는다**(심사 중 실제 잠금이 걸린다). 위 진단값으로만 판단하고,
   잠금 동작 자체는 로컬에서 확인한다(`backend/tests/test_security.py::test_login_throttle_is_per_client_behind_proxy`).

## 5. 로컬 사전 점검(2026-10-30, VALIDATION §5-4)
배포와 같은 설정(운영 모드·`PORT=10000`·root 소유 디스크·`COOKIE_SECURE=true`·HTTPS 프록시)으로 Docker 이미지를 실행해
구상 기반·참고문서 기반 브라우저 E2E, 재배포 후 데이터 유지, 실제 OpenAI 호출(질문·문서 추출), 엑셀 다운로드를 확인했다.
Render 배포는 사용자가 위 절차로 진행해 운영 중이다(`https://sw-design-helper.onrender.com`, 사용자 전달). 작업 세션 환경에서는 이 주소에 접속할 수 없어 Render 위 동작을 직접 확인하지 못했다.
- 제출·심사 기간에는 main 병합이 곧 자동 재배포이므로, 제출 커밋과 배포 커밋을 맞추는 절차를 `docs/SUBMISSION.md` §3에서 따른다.
- 내 PC Docker 실행은 README '내 PC에서 실행하기'와 같다. `.env`에 `DATA_DIR`를 넣지 않는다(이미지 기본 `/data` 볼륨을 덮어쓰면 볼륨 밖에 저장됨, VALIDATION §10).
