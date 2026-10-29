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
