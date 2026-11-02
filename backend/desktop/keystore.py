"""비밀값 보호 저장: Windows DPAPI(CryptProtectData, 현재 Windows 사용자 범위).

- 보호된 파일은 같은 PC·같은 Windows 계정에서만 풀린다. 다른 계정·다른 PC로 복사하면 풀 수 없다.
- 같은 계정으로 실행되는 다른 프로그램은 풀 수 있다(DPAPI의 한계). 파일 자체 암호화일 뿐 PC 전체 보호가 아니다.
- Windows가 아닌 환경(소스 시험)에서는 CJSWD_INSECURE_KEYSTORE=1일 때만 보호 없이 저장한다(시험 전용).
"""
from __future__ import annotations

import os
from pathlib import Path

ENTROPY = b"CJ-SW-Design/desktop/v1"
_PLAIN = b"UNPROTECTED-TEST-ONLY:"


class KeystoreError(RuntimeError):
    pass


def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def blob(b: bytes) -> Blob:
        buf = ctypes.create_string_buffer(b, len(b))
        return Blob(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    src, ent, out = blob(data), blob(ENTROPY), Blob()
    flags = 0x1  # CRYPTPROTECT_UI_FORBIDDEN
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if protect:
        ok = fn(ctypes.byref(src), "CJ-SW-Design", ctypes.byref(ent), None, None, flags, ctypes.byref(out))
    else:
        ok = fn(ctypes.byref(src), None, ctypes.byref(ent), None, None, flags, ctypes.byref(out))
    if not ok:
        raise KeystoreError(f"Windows 보호 저장소 처리 실패(오류 {ctypes.get_last_error()}). 다른 Windows 계정·PC에서 만든 파일일 수 있습니다.")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


def protect(data: bytes) -> bytes:
    if os.name == "nt":
        return _dpapi(data, True)
    if os.environ.get("CJSWD_INSECURE_KEYSTORE") == "1":
        return _PLAIN + data
    raise KeystoreError("보호 저장소는 Windows에서만 지원합니다.")


def unprotect(blob: bytes) -> bytes:
    if os.name == "nt":
        return _dpapi(blob, False)
    if os.environ.get("CJSWD_INSECURE_KEYSTORE") == "1" and blob.startswith(_PLAIN):
        return blob[len(_PLAIN):]
    raise KeystoreError("보호 저장소는 Windows에서만 지원합니다.")


def save(path: Path, value: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(protect(value.encode("utf-8")))
    os.replace(tmp, path)


def load(path: Path) -> str | None:
    if not path.exists():
        return None
    return unprotect(path.read_bytes()).decode("utf-8")


def delete(path: Path) -> None:
    path.unlink(missing_ok=True)
