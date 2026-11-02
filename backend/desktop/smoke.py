"""패키지 실행 검증(Windows CI). 빌드 폴더가 아니라 시험용 ZIP을 새로 풀어 그 실행파일을 실행한다.

    uv run python -m desktop.smoke --zip dist/CJ-SW-Design-windows-x64-<커밋>.zip --work <작업 폴더> [--e2e]

실행파일은 최소 환경변수(PATH=Windows 시스템 폴더만)로 띄워 개발 PC의 Python·Node·uv·소스를 쓰지 않게 한다.
이 스크립트(검사 도구)만 개발 도구를 쓴다. 가상 자료만 사용하고 유료 AI는 호출하지 않는다(가짜 키로 저장·표시만 확인).
"""
from __future__ import annotations

import argparse
import http.cookiejar
import http.server
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
from tests.fixtures_gen import docx_bytes, hwpx_bytes, pdf_text_bytes, xlsx_bytes  # noqa: E402

WIN = os.name == "nt"
EXE_NAME = "CJ-SW-Design.exe" if WIN else "CJ-SW-Design"
FAKE_KEY = "sk-fake-" + uuid.uuid4().hex + "TESTONLY"  # 실제 키 아님, 호출하지 않음
RESULTS: list[str] = []


def check(cond, msg: str) -> None:
    if not cond:
        raise AssertionError("확인 실패: " + msg)
    RESULTS.append(msg)
    print("  ✓", msg, flush=True)


# ---------------------------------------------------------------- HTTP
class Client:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(self.jar))

    def req(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None, csrf: bool = True):
        h = {"X-Requested-With": "swd"} if csrf and method != "GET" else {}
        h |= headers or {}
        r = urllib.request.Request(self.base + path, data=body, headers=h, method=method)
        try:
            with self.op.open(r, timeout=60) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)

    def json(self, method: str, path: str, data=None, **kw):
        body = json.dumps(data).encode() if data is not None else (b"" if method != "GET" else None)
        st, raw, _ = self.req(method, path, body, {"Content-Type": "application/json"}, **kw)
        return st, (json.loads(raw) if raw else None)

    def login(self, pw: str) -> int:
        return self.json("POST", "/api/auth/login", {"password": pw})[0]

    def upload(self, pid: str, name: str, data: bytes, kind: str = "reference"):
        b = "----swd" + uuid.uuid4().hex
        parts = [f"--{b}\r\nContent-Disposition: form-data; name=\"kind\"\r\n\r\n{kind}\r\n".encode(),
                 f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode(),
                 data, f"\r\n--{b}--\r\n".encode()]
        st, raw, _ = self.req("POST", f"/api/projects/{pid}/documents", b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={b}"})
        return st, json.loads(raw)


# ---------------------------------------------------------------- 실행파일 제어
class App:
    def __init__(self, folder: Path, local_appdata: Path, extra_env: dict | None = None):
        self.folder, self.lad = folder, local_appdata
        self.home = local_appdata / "CJ-SW-Design" if WIN else local_appdata
        self.extra = extra_env or {}
        self.proc: subprocess.Popen | None = None

    @property
    def exe(self) -> Path:
        return self.folder / "CJ-SW-Design" / EXE_NAME

    def env(self) -> dict:
        sysroot = os.environ.get("SystemRoot", r"C:\Windows")
        e = {"PATH": f"{sysroot}\\System32;{sysroot}" if WIN else "/usr/bin:/bin"}
        for k in ("SystemRoot", "windir", "SystemDrive", "TEMP", "TMP", "USERPROFILE", "USERNAME", "APPDATA", "COMPUTERNAME", "HOMEDRIVE", "HOMEPATH"):
            if k in os.environ:
                e[k] = os.environ[k]
        if WIN:
            e["LOCALAPPDATA"] = str(self.lad)  # 기본 경로 계산(%LOCALAPPDATA%\CJ-SW-Design)을 그대로 쓴다
        else:
            e |= {"HOME": os.environ.get("HOME", "/tmp"), "CJSWD_HOME": str(self.home), "CJSWD_INSECURE_KEYSTORE": "1"}
        # 개발·CI 셸에 남은 값이 섞이지 않는지 확인하려고 일부러 넣는다
        e |= {"OPENAI_API_KEY": "sk-inherited-" + "x" * 24, "AUTH_DISABLED": "true", "APP_ENV": "development", "DATA_DIR": str(self.lad / "wrong-data")}
        return e | self.extra

    def run(self, *args: str, timeout: float = 60) -> int:
        return subprocess.run([str(self.exe), *args], env=self.env(), cwd=str(self.lad.parent), timeout=timeout).returncode

    def start(self, *args: str) -> subprocess.Popen:
        self.proc = subprocess.Popen([str(self.exe), *args], env=self.env(), cwd=str(self.lad.parent))
        return self.proc

    def info(self) -> dict | None:
        try:
            return json.loads((self.home / "run" / "instance.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def wait_ready(self, timeout: float = 90) -> dict:
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            i = self.info()
            if i:
                try:
                    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(f"http://127.0.0.1:{i['port']}/__desktop/instance", timeout=2) as r:
                        if json.loads(r.read()).get("instance") == i["instance"]:
                            i["_secs"] = round(time.monotonic() - t0, 1)
                            return i
                except (urllib.error.URLError, OSError, ValueError):
                    pass
            if self.proc and self.proc.poll() is not None:
                raise AssertionError(f"실행파일이 준비 전에 끝남(코드 {self.proc.returncode}). 기록: {self.log_tail()}")
            time.sleep(0.5)
        raise AssertionError(f"{timeout}초 안에 준비되지 않음. 기록: {self.log_tail()}")

    def quit(self) -> None:
        port = (self.info() or {}).get("port")
        code = self.run("--quit")
        check(code == 0, "--quit 정상 종료(코드 0)")
        if self.proc:
            self.proc.wait(30)
            check(self.proc.returncode == 0, f"실행 중이던 프로세스가 코드 0으로 끝남({self.proc.returncode})")
        check(procs() == 0, "종료 후 CJ-SW-Design 프로세스 없음")
        if port:
            check(not port_open(port), f"종료 후 포트 {port} 해제")
        check(not (self.home / "run" / "instance.json").exists(), "종료 후 실행 정보 파일 정리")

    def log_tail(self, n: int = 8) -> str:
        try:
            return " | ".join((self.home / "logs" / "launcher.log").read_text(encoding="utf-8").splitlines()[-n:])
        except OSError:
            return "(기록 없음)"


def procs() -> int:
    if WIN:
        out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {EXE_NAME}", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
        return sum(1 for line in out.splitlines() if line.startswith(f'"{EXE_NAME}"'))
    out = subprocess.run(["pgrep", "-f", "CJ-SW-Design/CJ-SW-Design"], capture_output=True, text=True).stdout
    return len([x for x in out.split() if x.strip()])


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def window_titles(pid: int) -> list[str]:
    if not WIN:
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    titles: list[str] = []
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if buf.value:
                titles.append(buf.value)
        return True

    user32.EnumWindows(proto(cb), 0)
    return titles


def extract(zip_path: Path, dest: Path) -> Path:
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
    if not WIN:
        (dest / "CJ-SW-Design" / EXE_NAME).chmod(0o755)
    return dest


# ---------------------------------------------------------------- 시험
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--e2e", action="store_true", help="기존 브라우저 E2E(flow·reference·examples)를 패키지 서버에 실행")
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    zp, work = Path(a.zip).resolve(), Path(a.work).resolve()
    shutil.rmtree(work, ignore_errors=True)
    lad = work / "사용자 홍길동" / "AppData Local"  # 한글·공백 경로(실제 다른 Windows 계정은 아님)
    lad.mkdir(parents=True)
    pw = "시험용-" + uuid.uuid4().hex[:12]
    pwf = work / "pw.txt"
    pwf.write_text(pw, encoding="utf-8")

    print("[0] ZIP 내용")
    with zipfile.ZipFile(zp) as z:
        names = z.namelist()
        bad = [n for n in names if Path(n).name in (".env", "app.db", "launcher.log", "settings.json", "secret.bin", "openai_key.bin") or n.endswith((".db", ".log", ".sqlite"))]
        check(not bad, f"ZIP에 개발 설정·DB·기록·비밀 파일 없음({len(names)}개 파일)")
        check(f"CJ-SW-Design/{EXE_NAME}" in names and "CJ-SW-Design/_internal/frontend_dist/index.html" in names, "실행파일·일반 화면 빌드 포함")
        check(not any("demo-data" in n for n in names), "Pages 시연 데이터 미포함")
        check(any(n.startswith("CJ-SW-Design/_internal/examples/C-review/") for n in names) and any("KOSA-FORM" in n for n in names), "예제·FP 기준값 포함")
        info = json.loads(z.read("CJ-SW-Design/_internal/build_info.json"))
        print("    build:", info.get("commit"), info.get("python"), info.get("pyinstaller"), info.get("platform"))

    print("[1] 새 사용자 데이터 폴더에서 첫 실행(바탕화면 같은 한글·공백 경로)")
    app = App(extract(zp, work / "바탕 화면" / "새 폴더 A"), lad)
    check(procs() == 0, "시작 전 실행 중인 인스턴스 없음")
    app.start("--no-gui", "--no-browser", "--password-file", str(pwf))
    inf = app.wait_ready()
    check(True, f"서버 준비 {inf['_secs']}초, 주소 {inf['url']}")
    check(inf["url"].startswith("http://127.0.0.1:"), "127.0.0.1에만 바인딩한 주소")
    check((app.home / "data" / "app.db").exists(), f"DB가 사용자 데이터 폴더에 생성({app.home})")
    check(not list(app.folder.rglob("*.db")) and not (lad / "wrong-data").exists(), "프로그램 폴더·상속 DATA_DIR에 DB 없음")
    settings_txt = (app.home / "config" / "settings.json").read_text(encoding="utf-8")
    check(pw not in settings_txt and "scrypt$" in settings_txt, "비밀번호는 해시로만 저장")
    secret_blob = (app.home / "config" / "secret.bin").read_bytes()
    check(len(secret_blob) > 64 and b"UNPROTECTED" not in secret_blob if WIN else True, "세션 키 보호 저장(DPAPI)")
    c = Client(inf["url"])
    check(c.json("GET", "/api/projects")[0] == 401, "로그인 전 API 401(인증 유지, 상속 AUTH_DISABLED 무시)")
    check(c.login("wrong-password-x") == 401, "틀린 비밀번호 401")
    check(c.login(pw) == 200, "정한 비밀번호로 로그인")
    st, _ = c.json("POST", "/api/projects", {"name": "x"}, csrf=False)
    check(st == 403, "CSRF 헤더 없는 변경 요청 403")
    sysinfo = c.json("GET", "/api/system")[1]
    check(sysinfo["ai"]["kind"] == "sample" and sysinfo["app_env"] == "production", "샘플 모드·운영 모드로 시작(상속된 OPENAI_API_KEY·APP_ENV 무시)")
    cookie = next(iter(c.jar))
    check(not cookie.secure, "로컬 http 쿠키(Secure 아님)로 로그인 유지")

    print("[2] 샘플 프로젝트·편집·저장, 문서 파서 리소스, 검토, 견적, 엑셀")
    st, pj = c.json("POST", "/api/projects", {"name": "[시험] 교육 신청 관리", "sample": "education"})
    check(st == 200, "가상 샘플 프로젝트 생성")
    pid, ver = pj["project"]["id"], pj["version"]
    st, pj = c.json("PATCH", f"/api/projects/{pid}", {"version": ver, "overview": {"purpose": "직원 교육 신청을 온라인으로 처리(시험 수정)"}})
    check(st == 200 and pj["project"]["overview"]["purpose"].endswith("(시험 수정)"), "개요 수정·저장")
    docs = {
        "가상 과업.txt": ("SFR-001 교육과정을 등록·수정·삭제하여야 한다\nSFR-002 직원은 교육을 신청하고 취소할 수 있어야 한다\n".encode("utf-8"), "reference"),
        "가상.pdf": (pdf_text_bytes(["SFR-003 Course statistics report"]), "reference"),
        "가상.hwpx": (hwpx_bytes(["SFR-004 신청 승인과 반려 처리"]), "reference"),
        "가상.docx": (docx_bytes(["SFR-005 정원 초과 시 대기자 승계"]), "reference"),
        "가상.xlsx": (xlsx_bytes({"요구사항": [["ID", "내용"], ["SFR-006", "이수 통계"]]}), "reference"),
    }
    for name, (data, kind) in docs.items():
        st, r = c.upload(pid, name, data, kind)
        ex = r.get("document", {}).get("extraction", {})
        check(st == 200 and ex.get("status") in ("ok", "partial") and ex.get("chars", 0) > 0, f"업로드·추출 {name}: {ex.get('status')}·{ex.get('quality')}·{ex.get('chars')}자")
    ex_dir = REPO / "examples" / "C-review"
    for f, kind in (("vendor_task.txt", "vendor_task"), ("vendor_design.txt", "vendor_design"), ("vendor_cost.txt", "vendor_cost")):
        check(c.upload(pid, f, (ex_dir / f).read_bytes(), kind)[0] == 200, f"예제 C {f} 업로드")
    st, raw, _ = c.req("GET", "/api/examples/C-review/vendor_fp.xlsx")
    check(st == 200 and raw[:2] == b"PK", "번들 예제 FP 엑셀(CSV→XLSX) 제공")
    check(c.upload(pid, "vendor_fp.xlsx", raw, "vendor_fp")[0] == 200, "예제 C FP 산정표 업로드")
    st, rv = c.json("POST", f"/api/projects/{pid}/review/run", {})
    check(st == 200, "문서 검토 실행")
    st, pj = c.json("GET", f"/api/projects/{pid}")
    est_before = len(pj["project"].get("estimates", []))
    st, er = c.json("POST", f"/api/projects/{pid}/estimates", {"label": "시험 기준 산정"})
    if st != 200:
        print("    견적 응답:", st, str(er)[:300])
    check(st == 200, "기준 산정 실행·저장")
    st, pj = c.json("GET", f"/api/projects/{pid}")
    ests = pj["project"]["estimates"]
    check(len(ests) == est_before + 1, f"견적 버전 저장({len(ests)}개)")
    eid = ests[-1]["id"]
    st, sr = c.json("POST", f"/api/projects/{pid}/estimates/{eid}/scenarios", {"target_amount": 80000000})
    if st != 200:
        print("    시나리오 응답:", st, str(sr)[:300])
    check(st == 200, "목표예산 참고 시나리오")
    st, raw, hd = c.req("GET", f"/api/projects/{pid}/export.xlsx")
    xl = work / "다운로드 엑셀.xlsx"
    xl.write_bytes(raw)
    import openpyxl

    wb = openpyxl.load_workbook(xl)
    check(st == 200 and "검산" in wb.sheetnames and len(wb.sheetnames) >= 10, f"엑셀 내려받기·열기({len(wb.sheetnames)}개 시트)")
    snapshot = {"docs": len(pj["project"]["documents"]), "ests": len(ests), "name": pj["project"]["name"]}

    if a.e2e:
        print("[3] 기존 브라우저 E2E를 패키지 서버에 실행")
        for t in ("flow", "reference", "examples"):
            r = subprocess.run(["node", f"e2e/{t}.cjs"], cwd=REPO, env=os.environ | {"BASE_URL": inf["url"].rstrip("/"), "E2E_PASSWORD": pw}, capture_output=True, text=True, timeout=900)
            tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
            check(r.returncode == 0, f"E2E {t}: {' / '.join(tail)}")
        check(urllib.request.build_opener(urllib.request.ProxyHandler({})).open(inf["url"] + "api/health", timeout=5).status == 200,
              "브라우저(E2E)를 닫은 뒤에도 서버 계속 실행")

    print("[4] 중복 실행")
    t0 = time.monotonic()
    code = app.run("--no-gui", "--no-browser", timeout=60)
    check(code == 0 and time.monotonic() - t0 < 30, f"두 번째 실행은 기존 인스턴스를 확인하고 바로 끝남({round(time.monotonic() - t0, 1)}초)")
    check(procs() == 1, "인스턴스 1개만 실행 중")

    print("[5] 정상 종료 → 재실행 → 데이터 유지")
    app.quit()
    app.start("--no-gui", "--no-browser")
    inf = app.wait_ready()
    c = Client(inf["url"])
    check(c.login(pw) == 200, "재실행 후 같은 비밀번호로 로그인")
    pj = c.json("GET", f"/api/projects/{pid}")[1]["project"]
    check({"docs": len(pj["documents"]), "ests": len(pj["estimates"]), "name": pj["name"]} == snapshot, "프로젝트·업로드·견적 유지")
    st, raw, _ = c.req("GET", f"/api/projects/{pid}/documents/{pj['documents'][0]['id']}/download")
    check(st == 200 and raw.startswith(b"SFR-001"), "업로드 원본 유지")
    app.quit()

    print("[6] 배포 폴더 이동·새 ZIP으로 교체 후 데이터 유지")
    moved = work / "옮긴 위치 B"
    shutil.move(str(app.folder), str(moved))
    app.folder = moved
    app.start("--no-gui", "--no-browser")
    c = Client(app.wait_ready()["url"])
    check(c.login(pw) == 200 and any(p["id"] == pid for p in c.json("GET", "/api/projects")[1]), "옮긴 폴더에서 같은 데이터")
    app.quit()
    app.folder = extract(zp, work / "새 버전 C")
    app.start("--no-gui", "--no-browser")
    c = Client(app.wait_ready()["url"])
    check(c.login(pw) == 200 and any(p["id"] == pid for p in c.json("GET", "/api/projects")[1]), "새로 푼 ZIP에서 같은 데이터(초기화 없음)")
    app.quit()

    print("[7] 포트 충돌(다른 웹앱이 선호 포트 사용 중)")
    # 직전 시험의 TIME_WAIT 연결로 기본 포트를 바로 못 쓸 수 있어, 빈 포트를 선호 포트로 정하고 그 포트를 다른 웹앱이 차지하게 한다
    other = http.server.ThreadingHTTPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
    pref = other.server_address[1]
    sf = app.home / "config" / "settings.json"
    sf.write_text(json.dumps(json.loads(settings_txt) | {"port": pref}), encoding="utf-8")
    threading.Thread(target=other.serve_forever, daemon=True).start()
    try:
        app.start("--no-gui", "--no-browser")
        inf = app.wait_ready()
        check(inf["port"] != pref, f"선호 포트 {pref} 사용 중 → 빈 포트 {inf['port']} 사용")
        code = app.run("--no-gui", "--no-browser", timeout=60)
        check(code == 0 and procs() == 1, "포트 충돌 중에도 중복 실행은 실제 인스턴스를 찾음")
        app.quit()
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(f"http://127.0.0.1:{pref}/", timeout=5) as r:
            check(r.status == 200, "다른 웹앱은 종료되지 않고 계속 응답")
    finally:
        other.shutdown()
        other.server_close()
        sf.write_text(settings_txt, encoding="utf-8")

    print("[8] 강제 종료 후 재실행(DB·작업 상태)")
    app.start("--no-gui", "--no-browser")
    inf = app.wait_ready()
    db = sqlite3.connect(app.home / "data" / "app.db", timeout=10)
    db.execute("INSERT INTO jobs(id,project_id,kind,input_hash,status,progress,message,params,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
               ("JOB-smoke01", pid, "questions", "smoke", "running", 0.3, "실행 중", "{}", "2026-01-01T00:00:00", "2026-01-01T00:00:00"))
    db.commit()
    db.close()
    pid_exe = app.proc.pid
    if WIN:
        subprocess.run(["taskkill", "/PID", str(pid_exe), "/F"], capture_output=True)  # 이 프로세스만(전역 종료 아님)
    else:
        app.proc.kill()
    app.proc.wait(30)
    check(procs() == 0, "강제 종료됨(실행 정보 파일은 남은 상태)")
    check((app.home / "run" / "instance.json").exists(), "강제 종료 후 오래된 실행 정보가 남아 있음(시험 조건)")
    app.start("--no-gui", "--no-browser")
    c = Client(app.wait_ready()["url"])
    check(c.login(pw) == 200, "강제 종료 후 재실행·로그인(오래된 실행 정보 무시)")
    st, job = c.json("GET", "/api/jobs/JOB-smoke01")
    check(st == 200 and job["status"] == "interrupted", f"실행 중이던 작업은 '중단'으로 표시({job.get('status') if job else st})")
    check(len(c.json("GET", f"/api/projects/{pid}")[1]["project"]["documents"]) == snapshot["docs"], "강제 종료 후 DB 정상")
    app.quit()

    print("[9] 시작 실패 안내(설정 파일 손상)")
    sf = app.home / "config" / "settings.json"
    sf.write_text("{손상", encoding="utf-8")
    t0 = time.monotonic()
    code = app.run("--no-gui", "--no-browser", timeout=60)
    check(code == 5 and time.monotonic() - t0 < 30, f"손상된 설정은 무한 대기 없이 종료 코드 5({round(time.monotonic() - t0, 1)}초)")
    check("설정 파일을 읽지 못했습니다" in app.log_tail(3), "기록에 원인·조치 안내")
    sf.write_text(settings_txt, encoding="utf-8")

    print("[10] API 키 보호 저장·마스킹·삭제(가짜 키, 호출 없음)")
    kf = work / "key.txt"
    kf.write_text(FAKE_KEY, encoding="utf-8")
    check(app.run("--set-openai-key-file", str(kf)) == 0, "키 저장(실행 중이 아닐 때)")
    kf.unlink()
    blob = (app.home / "config" / "openai_key.bin").read_bytes()
    if WIN:
        check(FAKE_KEY.encode() not in blob and FAKE_KEY.encode("utf-16-le") not in blob, "키 파일에 원문 없음(DPAPI 보호 저장)")
    else:
        print("    (Windows 아님: 시험용 비보호 저장소라 원문 검사는 생략)")
    app.start("--no-gui", "--no-browser")
    inf = app.wait_ready()
    c = Client(inf["url"])
    c.login(pw)
    st, raw, _ = c.req("GET", "/api/system")
    sysinfo = json.loads(raw)
    check(sysinfo["ai"]["kind"] == "openai" and sysinfo["ai"]["model"] == "gpt-6-luna" and sysinfo["ai"]["task_models"].get("fp_candidates") == "gpt-6.1-sol",
          "다시 시작하면 OpenAI 연결·권장 모델(기본 gpt-6-luna, FP 후보 gpt-6.1-sol)")
    st2, raw2, _ = c.req("GET", f"/api/projects/{pid}")
    check(FAKE_KEY.encode() not in raw and FAKE_KEY.encode() not in raw2, "서버 응답에 키 원문 없음")
    app.quit()
    logs = b"".join(f.read_bytes() for f in (app.home / "logs").glob("*"))
    check(FAKE_KEY.encode() not in logs and pw.encode() not in logs, "기록에 키·비밀번호 없음")
    check(app.run("--clear-openai-key") == 0 and not (app.home / "config" / "openai_key.bin").exists(), "키 삭제")
    app.start("--no-gui", "--no-browser")
    c = Client(app.wait_ready()["url"])
    c.login(pw)
    check(c.json("GET", "/api/system")[1]["ai"]["kind"] == "sample", "키 삭제 후 샘플 모드")
    st, raw, _ = c.req("GET", f"/api/projects/{pid}/backup.json")
    check(st == 200 and b"scrypt$" not in raw and FAKE_KEY.encode() not in raw, "프로젝트 백업 JSON에 비밀번호 해시·키 없음")
    app.quit()

    if WIN:
        print("[11] 창 모드(직원이 더블클릭하는 방식)")
        app.start()  # 인자 없음: 런처 창 + 기본 브라우저 열기
        inf = app.wait_ready()
        time.sleep(2)
        titles = window_titles(app.proc.pid)
        check(any("정보화 설계 도우미" in t for t in titles), f"런처 창 표시: {titles}")
        app.quit()

    print(f"\n패키지 실행 검증 통과: {len(RESULTS)}개 항목")
    if a.report:
        Path(a.report).write_text(json.dumps({"build": info, "checks": RESULTS, "platform": sys.platform}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
