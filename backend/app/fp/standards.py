"""산정 기준 버전 관리.

기본 기준은 저장소의 `app/standards/*.json`(읽기 전용), 사용자 정의 기준은 `DATA_DIR/standards/`.
견적 버전은 사용한 기준 전체를 스냅샷으로 보관하므로 기준 파일이 바뀌어도 과거 견적은 유지된다.
"""
from __future__ import annotations

import copy
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

BUILTIN_DIR = Path(__file__).resolve().parents[1] / "standards"
DEFAULT_STANDARD_ID = "KOSA-FORM-2024G-241231"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,80}$")


class StandardError(ValueError):
    pass


class StandardRegistry:
    def __init__(self, custom_dir: Path):
        self.custom_dir = custom_dir
        custom_dir.mkdir(parents=True, exist_ok=True)

    def _builtin(self) -> dict[str, dict[str, Any]]:
        out = {}
        for p in sorted(BUILTIN_DIR.glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            d["_builtin"] = True
            out[d["id"]] = d
        return out

    def _custom(self) -> dict[str, dict[str, Any]]:
        out = {}
        for p in sorted(self.custom_dir.glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            d["_builtin"] = False
            out[d["id"]] = d
        return out

    def list(self) -> list[dict[str, Any]]:
        allstd = {**self._builtin(), **self._custom()}
        return [
            {"id": k, "title": v.get("title", ""), "builtin": v["_builtin"], "official_guide_checked": v.get("official_guide_checked", False)}
            for k, v in allstd.items()
        ]

    def get(self, std_id: str) -> dict[str, Any]:
        b = self._builtin()
        if std_id in b:
            return b[std_id]
        c = self._custom()
        if std_id in c:
            return c[std_id]
        raise StandardError(f"산정 기준 '{std_id}'를 찾을 수 없습니다.")

    def create_custom(self, base_id: str, new_id: str, title: str, overrides: dict[str, Any]) -> dict[str, Any]:
        """기준 복제 후 단가·이윤율 등 일부 값을 사용자 정의로 바꾼다. 가중치·복잡도표는 바꾸지 않는다."""
        if not _ID_RE.match(new_id) or not new_id.startswith("custom-"):
            raise StandardError("사용자 정의 기준 ID는 'custom-'으로 시작하고 영문·숫자·._- 만 사용합니다.")
        if new_id in self._builtin() or new_id in self._custom():
            raise StandardError("이미 있는 기준 ID입니다.")
        base = copy.deepcopy(self.get(base_id))
        base.pop("_builtin", None)
        base["id"] = new_id
        base["title"] = title or f"사용자 정의 기준 (원본: {base_id})"
        base["derived_from"] = base_id
        base["official_guide_checked"] = False
        allowed = {"unit_price", "profit_rate", "vat_rate"}
        for k, v in overrides.items():
            if k not in allowed:
                raise StandardError(f"사용자 정의 기준에서 바꿀 수 없는 항목: {k}")
            if k == "unit_price":
                iv = int(v)
                if iv <= 0:
                    raise StandardError("단가는 양수여야 합니다.")
                base[k] = {"value": iv, "basis": "사용자 입력", "status": "user_defined"}
            else:
                dv = Decimal(str(v))
                if dv < 0 or dv > 1:
                    raise StandardError(f"{k}는 0~1 사이 비율입니다.")
                base[k] = {"value": str(dv), "basis": "사용자 입력", "status": "user_defined"}
        (self.custom_dir / f"{new_id}.json").write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
        return base
