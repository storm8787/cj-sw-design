"""허용 도메인 공식 자료의 서버 측 조회(SSRF 방지).

- https만, 허용 목록 도메인만, 리다이렉트 따라가지 않음.
- DNS 결과가 사설·루프백·링크로컬(클라우드 메타데이터 169.254.169.254 포함)·예약 주소면 차단.
- 응답 2MB·10초 제한. 제목만 추출하며 버전·지원 상태는 사용자가 확인해 입력한다(자동 판단하지 않음).
"""
from __future__ import annotations

import ipaddress
import re
import socket
from html import unescape
from urllib.parse import urlsplit

import httpx


class FetchBlocked(ValueError):
    pass


def check_url(url: str, allowlist: list[str], resolver=socket.getaddrinfo) -> str:
    u = urlsplit(url.strip())
    if u.scheme != "https":
        raise FetchBlocked("https 주소만 조회할 수 있습니다.")
    if u.username or u.password:
        raise FetchBlocked("계정 정보가 포함된 주소는 조회하지 않습니다.")
    host = (u.hostname or "").lower().rstrip(".")
    if not host:
        raise FetchBlocked("주소의 호스트가 없습니다.")
    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        is_ip = False
    if is_ip:
        raise FetchBlocked("IP 주소로는 조회할 수 없습니다(허용 도메인만).")
    if host not in allowlist:
        raise FetchBlocked(f"허용 목록에 없는 도메인입니다: {host}")
    if u.port not in (None, 443):
        raise FetchBlocked("443 이외 포트는 조회하지 않습니다.")
    try:
        infos = resolver(host, 443, proto=socket.IPPROTO_TCP)
    except OSError as e:
        raise FetchBlocked(f"도메인 확인 실패: {host}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise FetchBlocked("내부·예약 주소로 연결되는 도메인은 조회하지 않습니다.")
    return host


def fetch_title(url: str, allowlist: list[str], transport: httpx.BaseTransport | None = None, resolver=socket.getaddrinfo) -> dict[str, str]:
    check_url(url, allowlist, resolver)
    with httpx.Client(follow_redirects=False, timeout=10.0, transport=transport) as c:
        with c.stream("GET", url, headers={"User-Agent": "sw-design-helper/0.1"}) as r:
            if r.is_redirect:
                raise FetchBlocked(f"다른 주소로 이동하는 응답({r.status_code})은 따라가지 않습니다. 최종 주소를 직접 등록하세요.")
            if r.status_code != 200:
                raise FetchBlocked(f"조회 실패(HTTP {r.status_code})")
            body = b""
            for part in r.iter_bytes():
                body += part
                if len(body) > 2 * 1024 * 1024:
                    break
    text = body.decode("utf-8", errors="replace")
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    return {"title": unescape(" ".join(m.group(1).split()))[:200] if m else "", "bytes": str(len(body))}
