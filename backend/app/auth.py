"""단일 관리자 인증.

- 비밀번호: ADMIN_PASSWORD_HASH(scrypt) 권장. ADMIN_PASSWORD(평문 환경변수)도 허용하되 메모리에서만 해시.
- 세션: itsdangerous 서명 쿠키(HttpOnly, SameSite=Strict, 만료). 기본 비밀번호·비밀키는 코드에 없다.
- 변경 요청(POST/PUT/PATCH/DELETE)은 X-Requested-With 헤더 필수(교차 사이트 요청 방지).
- 해시 생성: `uv run python -m app.auth hash`
"""
from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import secrets
import sys
import threading
import time

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

COOKIE = "swd_session"
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "swd"


def client_ip(peer: str, forwarded_for: str | None, hops: int) -> str:
    """로그인 실패 제한에 쓸 접속자 식별값.

    리버스 프록시(배포 서비스) 뒤에서는 peer가 프록시 주소라서 모든 접속자가 한 값으로 묶인다.
    그러면 한 사람의 오타 5회로 다른 사람까지 5분간 막힌다. 그래서 `X-Forwarded-For`를 쓰지만,
    **왼쪽 값은 클라이언트가 위조할 수 있으므로 신뢰하지 않는다**(프록시가 지우지 않고 덧붙이기만 하는
    서비스가 있다). 바로 연결된 프록시가 **오른쪽에 덧붙인** 값만 신뢰하고, 오른쪽에서 `hops`번째를 쓴다.

    hops=0  → peer만 사용(**기본값**). 프록시가 없으면 헤더를 아예 믿지 않는다 —
              직접 노출된 서버에서 hops>0으로 두면 접속자가 헤더를 바꿔 새 키를 만들어 제한을 피할 수 있다.
    hops=1  → 맨 오른쪽 값. 프록시 1단이면 실제 접속자 주소다(배포 설정에서 '선언'한다, render.yaml)
    hops=2  → 오른쪽에서 두 번째. 프록시가 2단인 서비스에서 실제 접속자 주소다
    체인이 hops보다 짧으면(프록시를 거치지 않은 직접 접속) peer로 되돌린다.
    """
    if hops <= 0 or not forwarded_for:
        return peer
    parts = [p.strip() for p in forwarded_for.split(",") if p.strip()]
    if len(parts) < hops:
        return peer
    return parts[-hops]


def hash_password(pw: str, n: int = 2**14, r: int = 8, p: int = 1) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${base64.b64encode(salt).decode()}${base64.b64encode(h).decode()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b, hash_b = stored.split("$")
        if algo != "scrypt":
            return False
        h = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt_b), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(h, base64.b64decode(hash_b))
    except (ValueError, TypeError):
        return False


class Auth:
    def __init__(self, secret_key: str, password_hash: str, plain_password: str, max_age: int, disabled: bool):
        self.disabled = disabled
        self.max_age = max_age
        self.signer = URLSafeTimedSerializer(secret_key or secrets.token_hex(32), salt="swd-session")
        self.password_hash = password_hash or (hash_password(plain_password) if plain_password else "")
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def throttled(self, ip: str) -> bool:
        now = time.time()
        with self._lock:
            arr = [t for t in self._fails.get(ip, []) if now - t < 300]
            self._fails[ip] = arr
            return len(arr) >= 5

    def login(self, ip: str, password: str) -> str | None:
        if self.throttled(ip):
            raise PermissionError("로그인 실패가 많아 5분간 제한됩니다.")
        if self.password_hash and verify_password(password, self.password_hash):
            with self._lock:
                self._fails.pop(ip, None)
            return self.signer.dumps({"u": "admin", "n": secrets.token_hex(8)})
        with self._lock:
            self._fails.setdefault(ip, []).append(time.time())
        return None

    def check(self, token: str | None) -> bool:
        if self.disabled:
            return True
        if not token:
            return False
        try:
            data = self.signer.loads(token, max_age=self.max_age)
            return data.get("u") == "admin"
        except (BadSignature, SignatureExpired):
            return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "hash":
        pw = getpass.getpass("관리자 비밀번호(10자 이상): ")
        if len(pw) < 10:
            sys.exit("10자 이상이어야 합니다.")
        if pw != getpass.getpass("다시 입력: "):
            sys.exit("일치하지 않습니다.")
        print(hash_password(pw))
    else:
        print("사용법: python -m app.auth hash")
