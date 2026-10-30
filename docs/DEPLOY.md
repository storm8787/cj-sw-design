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
| 데이터 영속 저장 | `DATA_DIR` + 디스크 | `/data`, 디스크 1GB를 `/data`에 연결 | render.yaml |
| AI(기본 OpenAI) | `OPENAI_API_KEY` | 사용자 키 | **사용자** (Render 화면, 비밀값). 비우면 샘플 모드 |
| AI 모델 | `OPENAI_MODEL` | `gpt-6.1-sol`(2026-10-29 실제 검증한 모델) | render.yaml |
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
6. 확인: 주소 접속 시 로그인 화면 → 비밀번호 로그인 → 상단에 'OpenAI(ChatGPT) · gpt-6.1-sol'(키를 넣은 경우) 또는 '샘플 모드' 표시.

Blueprint 화면이 막히면 수동으로: New → Web Service → 저장소 선택 → Runtime **Docker**, Region **Singapore**, Instance **Starter**,
Health Check Path `/api/health`, Advanced → Disk 추가(Mount Path `/data`, 1GB) → 위 표의 환경변수 입력.

## 4. 운영 중 주의
- **실제 사업 문서·개인정보는 올리지 않는다.** 테스트 서버는 국외(싱가포르) 상용 클라우드다. 실데이터 사용은 기관 보안 검토 후 결정.
- 외부 AI로 보내는 내용은 요청마다 전송 범위를 보여 주고 동의를 받으며, 문서 원문은 문서별 동의가 따로 필요하다.
- 로그인 실패 5회/5분 제한은 배포 프록시 주소 단위로 걸려 모든 접속자가 함께 5분간 막힐 수 있다(단일 관리자 테스트용 한계).
- 백업: 프로젝트별 '7 엑셀 → JSON 백업 내려받기'(업로드 원본 제외). 디스크 자체 백업(스냅샷)은 Render 안내를 확인.
- 비밀번호·키 교체: Render → 서비스 → Environment에서 값 변경 → 자동 재시작. `SECRET_KEY`를 바꾸면 모든 로그인 세션이 끊긴다.
- 테스트가 끝나면 Render에서 서비스(디스크 포함)를 삭제해 과금을 멈춘다. 삭제하면 데이터도 지워지므로 필요한 프로젝트는 먼저 JSON 백업.

## 5. 로컬 사전 점검(2026-10-30, VALIDATION §5-4)
배포와 같은 설정(운영 모드·`PORT=10000`·root 소유 디스크·`COOKIE_SECURE=true`·HTTPS 프록시)으로 Docker 이미지를 실행해
구상 기반·참고문서 기반 브라우저 E2E, 재배포 후 데이터 유지, 실제 OpenAI 호출(질문·문서 추출), 엑셀 다운로드를 확인했다.
Render 위에서의 실제 배포는 사용자가 위 절차를 진행한 뒤 확인한다(미실시).
