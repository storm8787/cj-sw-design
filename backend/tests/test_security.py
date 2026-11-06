import socket

import httpx
import pytest

from app.config import ConfigError, Settings, validate
from app.docs_extract import extract as dx
from app.tech import fetch as tf
from tests.conftest import client_for


def test_unauthenticated_blocked(app_factory):
    app = app_factory()
    admin = client_for(app)
    pid = admin.post("/api/projects", json={"name": "비공개", "sample": "education"}).json()["project"]["id"]
    up = admin.post(f"/api/projects/{pid}/documents", files={"file": ("a.txt", "SFR-001 신청 기능을 제공하여야 한다".encode(), "text/plain")}, data={"kind": "reference"}).json()
    did = up["document"]["id"]
    anon = client_for(app, login=False)
    for url in [f"/api/projects", f"/api/projects/{pid}", f"/api/projects/{pid}/export.xlsx", f"/api/projects/{pid}/backup.json", f"/api/projects/{pid}/documents/{did}/download", f"/api/projects/{pid}/export/preview", "/api/system"]:
        assert anon.get(url).status_code == 401, url
    assert anon.post("/api/projects", json={"name": "x"}).status_code == 401
    assert anon.get("/api/health").status_code == 200
    # 위조 쿠키
    anon.cookies.set("swd_session", "forged.token.value")
    assert anon.get("/api/projects").status_code == 401
    # 로그인 사용자는 다운로드 가능
    assert admin.get(f"/api/projects/{pid}/documents/{did}/download").status_code == 200


def test_csrf_header_required(app_factory):
    app = app_factory()
    c = client_for(app)
    from fastapi.testclient import TestClient

    raw = TestClient(app)
    raw.cookies = c.cookies
    assert raw.post("/api/projects", json={"name": "x"}).status_code == 403


def test_login_wrong_and_throttle(app_factory):
    app = app_factory()
    c = client_for(app, login=False)
    for _ in range(5):
        assert c.post("/api/auth/login", json={"password": "wrong-password"}).status_code == 401
    assert c.post("/api/auth/login", json={"password": "wrong-password"}).status_code == 429


def test_client_ip_counts_from_right_not_left():
    """X-Forwarded-For의 왼쪽은 클라이언트가 위조할 수 있다. 오른쪽에서 센 값만 쓴다."""
    from app.auth import client_ip

    # 프록시 없음
    assert client_ip("203.0.113.9", None, 0) == "203.0.113.9"
    assert client_ip("203.0.113.9", None, 1) == "203.0.113.9"
    # 프록시 1단: 프록시가 실제 접속자를 오른쪽에 덧붙인다
    assert client_ip("10.0.0.1", "198.51.100.7", 1) == "198.51.100.7"
    # 위조: 클라이언트가 왼쪽에 남의 주소를 넣어도 오른쪽(프록시가 붙인 값)이 이긴다
    assert client_ip("10.0.0.1", "1.2.3.4, 198.51.100.7", 1) == "198.51.100.7"
    assert client_ip("10.0.0.1", "1.2.3.4, 5.6.7.8, 9.9.9.9, 198.51.100.7", 1) == "198.51.100.7"
    # 프록시 2단
    assert client_ip("10.0.0.1", "198.51.100.7, 10.0.0.9", 2) == "198.51.100.7"
    assert client_ip("10.0.0.1", "1.2.3.4, 198.51.100.7, 10.0.0.9", 2) == "198.51.100.7"
    # 체인이 설정보다 짧으면(프록시를 거치지 않은 직접 접속) peer로 되돌린다 — 위조로 새 키를 만들 수 없다
    assert client_ip("10.0.0.1", "1.2.3.4", 2) == "10.0.0.1"
    assert client_ip("10.0.0.1", "", 1) == "10.0.0.1"
    assert client_ip("10.0.0.1", "  ,  ", 1) == "10.0.0.1"
    # 기본값 0(프록시 없음·직접 노출): 헤더를 아무리 보내도 무시한다
    for forged in ("1.2.3.4", "1.2.3.4, 5.6.7.8", "a, b, c, d, e, f"):
        assert client_ip("203.0.113.9", forged, 0) == "203.0.113.9"


def test_default_does_not_trust_forwarded_header(app_factory):
    """기본 설정(프록시 없음)에서는 X-Forwarded-For를 바꿔 로그인 실패 제한을 피할 수 없다."""
    from app.config import Settings

    assert Settings().trusted_proxy_hops == 0  # 직접 노출에서 안전한 기본값
    app = app_factory()  # trusted_proxy_hops 기본값
    c = client_for(app, login=False)
    for i in range(5):
        assert c.post("/api/auth/login", json={"password": "wrong"}, headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code == 401
    # 매 요청 헤더를 바꿔도 같은 접속자로 세어 제한된다
    assert c.post("/api/auth/login", json={"password": "wrong"}, headers={"X-Forwarded-For": "10.9.9.9"}).status_code == 429
    assert c.post("/api/auth/login", json={"password": "wrong"}).status_code == 429


def test_login_throttle_is_per_client_behind_proxy(app_factory):
    """프록시 뒤에서 A의 실패 5회가 다른 접속자 B의 정상 로그인을 막지 않는다(검수 보고서 [차단-1])."""
    from tests.conftest import PASSWORD

    app = app_factory(trusted_proxy_hops=1)
    c = client_for(app, login=False)
    A, B = "198.51.100.7", "198.51.100.8"

    # 프록시는 실제 접속자 주소를 오른쪽에 덧붙인다
    for _ in range(5):
        assert c.post("/api/auth/login", json={"password": "wrong"}, headers={"X-Forwarded-For": A}).status_code == 401
    # A는 추가 시도가 제한된다 — 올바른 비밀번호라도 막힌다
    assert c.post("/api/auth/login", json={"password": "wrong"}, headers={"X-Forwarded-For": A}).status_code == 429
    assert c.post("/api/auth/login", json={"password": PASSWORD}, headers={"X-Forwarded-For": A}).status_code == 429
    # B는 한 번도 틀리지 않았으므로 올바른 비밀번호로 로그인된다
    assert c.post("/api/auth/login", json={"password": PASSWORD}, headers={"X-Forwarded-For": B}).status_code == 200

    # 제한 우회 시도: A가 왼쪽에 B를 위조해 넣어도, 프록시가 붙인 오른쪽 값(A)으로 계속 제한된다
    assert c.post("/api/auth/login", json={"password": PASSWORD}, headers={"X-Forwarded-For": f"{B}, {A}"}).status_code == 429
    assert c.post("/api/auth/login", json={"password": PASSWORD}, headers={"X-Forwarded-For": f"9.9.9.9, 1.2.3.4, {A}"}).status_code == 429
    # 헤더를 아예 지워도 peer(프록시 주소)로 떨어지므로 A의 기록을 피할 수는 있으나 공용 키라 새 우회 수단이 아니다
    assert c.post("/api/auth/login", json={"password": "wrong"}).status_code == 401


def test_system_reports_login_throttle_key(app_factory):
    """배포 환경에서 프록시 단 수를 잠금 없이 확인할 수 있는 진단값."""
    app = app_factory(trusted_proxy_hops=1)
    c = client_for(app)
    info = c.get("/api/system", headers={"X-Forwarded-For": "1.2.3.4, 198.51.100.7"}).json()["client"]
    assert info["forwarded_count"] == 2
    assert info["trusted_proxy_hops"] == 1
    assert info["login_throttle_key"] == "198.51.100.7"
    assert info["shared_key_warning"] == ""
    # 프록시 단 수를 0으로 두면 모든 접속자가 프록시 주소 하나로 묶인다 → 경고
    app0 = app_factory(trusted_proxy_hops=0)
    c0 = client_for(app0)
    info0 = c0.get("/api/system", headers={"X-Forwarded-For": "1.2.3.4, 198.51.100.7"}).json()["client"]
    assert info0["login_throttle_key"] == info0["peer"]
    assert "함께 걸릴 수 있습니다" in info0["shared_key_warning"]


def test_trusted_proxy_hops_validated():
    s = Settings()
    s.secret_key, s.admin_password = "k" * 40, "0123456789"
    s.trusted_proxy_hops = -1
    with pytest.raises(ConfigError):
        validate(s)
    s.trusted_proxy_hops = 6
    with pytest.raises(ConfigError):
        validate(s)
    s.trusted_proxy_hops = 1
    validate(s)


def test_config_requires_secrets_and_local_only_bypass():
    s = Settings()
    s.app_env = "production"
    s.auth_disabled = True
    with pytest.raises(ConfigError):
        validate(s)
    s = Settings()
    s.app_env = "production"
    with pytest.raises(ConfigError):
        validate(s)  # SECRET_KEY·비밀번호 없음
    s.secret_key = "k" * 40
    s.admin_password = "short"
    with pytest.raises(ConfigError):
        validate(s)
    s = Settings()
    s.app_env = "development"
    s.auth_disabled = True
    validate(s)


def test_upload_validation():
    mb = 1024 * 1024
    with pytest.raises(dx.UploadRejected):
        dx.check_upload("a.exe", b"MZ", mb, mb)
    with pytest.raises(dx.UploadRejected):
        dx.check_upload("a.pdf", b"not a pdf", mb, mb)
    with pytest.raises(dx.UploadRejected):
        dx.check_upload("a.docx", b"%PDF", mb, mb)
    with pytest.raises(dx.UploadRejected):
        dx.check_upload("a.txt", b"x" * (mb + 1), mb, 10 * mb)
    import io
    import zipfile

    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", "0" * (5 * mb))  # 고압축 → 폭탄 의심
    with pytest.raises(dx.UploadRejected):
        dx.check_upload("a.docx", bio.getvalue(), mb, 2 * mb)
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        z.writestr("../../evil.xml", "x")
    with pytest.raises(dx.UploadRejected):
        dx.check_upload("a.xlsx", bio.getvalue(), mb, mb)
    assert dx.safe_filename("../../etc/passwd") == "passwd"
    assert dx.safe_filename("C:\\Users\\x\\과업지시서.hwpx") == "과업지시서.hwpx"


def test_upload_traversal_name_stored_safely(client):
    pid = client.post("/api/projects", json={"name": "x"}).json()["project"]["id"]
    r = client.post(f"/api/projects/{pid}/documents", files={"file": ("../../../outside.txt", "내용".encode(), "text/plain")}, data={"kind": "reference"})
    d = r.json()["document"]
    assert d["file_name"] == "outside.txt" and d["stored_name"] == f"{d['id']}.txt"
    assert client.get("/api/projects/../../etc/x").status_code in (401, 404)


def _resolver(ip):
    return lambda host, port, proto=0: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]


def test_ssrf_guard():
    allow = ["www.postgresql.org", "example.org"]
    pub = _resolver("93.184.216.34")
    with pytest.raises(tf.FetchBlocked):
        tf.check_url("http://www.postgresql.org/", allow, pub)
    with pytest.raises(tf.FetchBlocked):
        tf.check_url("https://169.254.169.254/latest/meta-data", allow, pub)
    with pytest.raises(tf.FetchBlocked):
        tf.check_url("https://evil.example.com/", allow, pub)
    with pytest.raises(tf.FetchBlocked):
        tf.check_url("https://example.org/", allow, _resolver("169.254.169.254"))
    with pytest.raises(tf.FetchBlocked):
        tf.check_url("https://example.org/", allow, _resolver("10.0.0.5"))
    with pytest.raises(tf.FetchBlocked):
        tf.check_url("https://example.org:8443/", allow, pub)
    assert tf.check_url("https://www.postgresql.org/support/versioning/", allow, pub) == "www.postgresql.org"


def test_fetch_title_and_redirect_block():
    allow = ["example.org"]
    pub = _resolver("93.184.216.34")
    ok = httpx.MockTransport(lambda req: httpx.Response(200, html="<html><title>Versioning Policy</title></html>"))
    assert tf.fetch_title("https://example.org/v", allow, ok, pub)["title"] == "Versioning Policy"
    redir = httpx.MockTransport(lambda req: httpx.Response(302, headers={"Location": "http://169.254.169.254/"}))
    with pytest.raises(tf.FetchBlocked):
        tf.fetch_title("https://example.org/v", allow, redir, pub)


def test_secrets_not_logged(app_factory, caplog):
    import logging

    caplog.set_level(logging.DEBUG)
    c = client_for(app_factory())
    pid = c.post("/api/projects", json={"name": "개인정보 홍길동 010-1234-5678"}).json()["project"]["id"]
    c.post(f"/api/projects/{pid}/documents", files={"file": ("a.txt", "주민등록번호 900101-1234567".encode(), "text/plain")}, data={"kind": "reference"})
    text = caplog.text
    assert "900101-1234567" not in text and "010-1234-5678" not in text and "test-password" not in text
