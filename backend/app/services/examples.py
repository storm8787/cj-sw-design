"""모의데이터(예제) 파일 제공. 원본은 저장소 `examples/` 한 곳에만 두고 화면 다운로드·시연판·테스트가 같은 파일을 쓴다.

- 허용 목록에 있는 파일만 내려준다(경로 조작 방지).
- 업체 FP 산정표는 검토 기능이 엑셀 표를 읽으므로, 저장소의 CSV 원본을 내려받을 때 .xlsx로 바꿔 준다(내용 동일).
- 모든 예제는 가상 자료다. 내려받기만으로 프로젝트·AI 호출이 생기지 않는다.
"""
from __future__ import annotations

import csv
import io
import os
from pathlib import Path

# (공개 파일명, 저장소 원본, 예제, 설명, 업로드할 때 고를 문서 종류)
FILES: list[tuple[str, str, str, str, str]] = [
    ("A-idea/idea_example.md", "A-idea/idea_example.md", "A", "구상 입력 예시(사업명·구상·기능 일곱 줄)", ""),
    ("B-reference/reference_task_order.txt", "B-reference/reference_task_order.txt", "B", "가상 타 기관 과업지시서", "reference"),
    ("C-review/vendor_task.txt", "C-review/vendor_task.txt", "C", "가상 업체 과업지시서", "vendor_task"),
    ("C-review/vendor_design.txt", "C-review/vendor_design.txt", "C", "가상 업체 설계서", "vendor_design"),
    ("C-review/vendor_fp.xlsx", "C-review/vendor_fp.csv", "C", "가상 업체 FP 산정표(엑셀)", "vendor_fp"),
    ("C-review/vendor_cost.txt", "C-review/vendor_cost.txt", "C", "가상 업체 금액 산출서", "vendor_cost"),
    ("C-review/expected_findings.md", "C-review/expected_findings.md", "C", "기대 확인 목록(넣어 둔 오류·탐지 결과·한계)", ""),
]
TYPES = {".md": "text/markdown; charset=utf-8", ".txt": "text/plain; charset=utf-8", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


def examples_dir() -> Path:
    env = os.environ.get("EXAMPLES_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[3] / "examples"


def listing() -> list[dict[str, str]]:
    return [{"name": n, "case": c, "label": lab, "kind": k} for n, _, c, lab, k in FILES]


def csv_to_xlsx(text: str, sheet: str = "FP산정") -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    for row in csv.reader(io.StringIO(text)):
        vals: list[object] = []
        for v in row:
            try:
                vals.append(float(v) if v.strip() and v.replace(".", "", 1).isdigit() else v)
            except ValueError:
                vals.append(v)
        ws.append(vals)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def read(name: str) -> tuple[bytes, str] | None:
    """반환 (내용, Content-Type). 허용 목록 밖이면 None."""
    hit = next((f for f in FILES if f[0] == name), None)
    if hit is None:
        return None
    src = examples_dir() / hit[1]
    if not src.is_file():
        return None
    data = src.read_bytes()
    if name.endswith(".xlsx") and src.suffix == ".csv":
        data = csv_to_xlsx(data.decode("utf-8"))
    return data, TYPES[Path(name).suffix]
