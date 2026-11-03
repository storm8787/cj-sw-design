"""끝수 처리 정책(2026-11-03): 기본 10원 미만 절사, 최종 총액 끝수조정 행, 과거 견적 보존.

미리보기 → 설정 저장 → 새 견적 → 목표예산 → 엑셀 수식 → LibreOffice 재계산 검산을 대조한다(Python 값 복사 비교만 하지 않음).
"""
import io
import json
import shutil
import subprocess

import openpyxl
import pytest

from app.fp import cost


def pj(r):
    assert r.status_code == 200, r.text
    return r.json()


def _recalc(c, pid, tmp_path, name="x"):
    src = tmp_path / f"{name}.xlsx"
    src.write_bytes(c.get(f"/api/projects/{pid}/export.xlsx").content)
    out = tmp_path / f"r-{name}"
    subprocess.run(["soffice", "--headless", "--calc", "--convert-to", "xlsx", "--outdir", str(out), str(src)], check=True, timeout=180, capture_output=True)
    return openpyxl.load_workbook(out / f"{name}.xlsx", data_only=True), openpyxl.load_workbook(src)


def _rows(ws):
    return {r[0]: r[9] for r in ws.iter_rows(values_only=True) if r and r[0] and len(r) > 9}


def test_new_project_default_is_10_down(client):
    p = pj(client.post("/api/projects", json={"name": "새 사업"}))["project"]
    assert p["cost_settings"]["rounding"] == {"unit": 10, "mode": "down"}


@pytest.mark.skipif(not shutil.which("soffice"), reason="LibreOffice 없음(재계산 검증은 로컬에서 실행)")
def test_preview_save_estimate_scenario_excel_agree(client, tmp_path):
    c = client
    d = pj(c.post("/api/projects", json={"name": "끝수 시험", "sample": "education"}))
    pid = d["project"]["id"]
    cs = d["project"]["cost_settings"] | {"direct_expenses": [{"id": "DE-1", "name": "교재 인쇄", "basis": "가상", "amount": 13}], "rounding": {"unit": 10, "mode": "down"}}
    pj(c.put(f"/api/projects/{pid}/cost-settings", json=cs))
    pv = pj(c.get(f"/api/projects/{pid}/estimate-preview"))["money"]
    est = pj(c.post(f"/api/projects/{pid}/estimates", json={"label": "10원 절사"}))["estimate"]
    m = est["result"]["money"]
    for k in ("dev_cost", "profit", "direct_total", "supply", "vat", "total_before_adjustment", "final_adjustment", "total"):
        assert pv[k] == m[k], k  # 미리보기 = 저장된 견적
    assert m["direct_total"] == 13 and m["supply"] == m["dev_cost"] + m["profit"] + 13
    assert m["total"] % 10 == 0 and m["total_before_adjustment"] + m["final_adjustment"] == m["total"] and m["final_adjustment"] != 0
    assert m["rounding"]["label"] == "10원 미만 절사(일의 자리 버림)" and m["rounding"]["policy"] == cost.ROUNDING_POLICY
    sc = pj(c.post(f"/api/projects/{pid}/estimates/{est['id']}/scenarios", json={"target_amount": 60_000_005, "includes_vat": True}))["scenario"]["result"]
    assert sc["target_amount"] == 60_000_005 and sc["unit_conflict"] is True and sc["base_total"] == m["total"]

    vals, forms = _recalc(c, pid, tmp_path)
    got = _rows(vals["개발비_기준"])
    assert got["부가세 포함 합계(최종 끝수조정 전)"] == m["total_before_adjustment"]
    assert got["최종 끝수조정(참고 조정)"] == m["final_adjustment"]
    assert got["총액(부가세 포함)"] == m["total"] and got["직접경비"] == 13
    frow = {r[0].value: r[9] for r in forms["개발비_기준"].iter_rows() if r[0].value and len(r) > 9}
    assert str(frow["총액(부가세 포함)"].value).startswith("=ROUNDDOWN(") and frow["최종 끝수조정(참고 조정)"].data_type == "f"
    checks = [r for r in vals["검산"].iter_rows(min_row=5, values_only=True) if r[0]]
    assert any("최종 끝수조정" in str(r[0]) for r in checks)
    bad = [r for r in checks if r[5] != "일치"]
    assert checks and not bad, bad
    texts = " ".join(str(v) for row in forms["목표예산_시나리오"].iter_rows(values_only=True) for v in row if v)
    assert "목표액 맞춤 끝수조정(참고)" in texts and "동시에 만족할 수 없음" in texts


@pytest.mark.skipif(not shutil.which("soffice"), reason="LibreOffice 없음(재계산 검증은 로컬에서 실행)")
@pytest.mark.parametrize("unit", [1, 10])
def test_legacy_estimate_is_preserved(client, tmp_path, unit):
    """정책 변경 전에 만든 견적(최종 끝수조정 필드 없음)은 당시 금액·방식 그대로 열리고 내려받아진다. unit=1은 재해석하지 않는다."""
    c = client
    d = pj(c.post("/api/projects", json={"name": f"이전 견적 {unit}", "sample": "education"}))
    pid = d["project"]["id"]
    cs = d["project"]["cost_settings"] | {"direct_expenses": [{"id": "DE-1", "name": "교재", "basis": "가상", "amount": 13}], "rounding": {"unit": unit, "mode": "down"}}
    pj(c.put(f"/api/projects/{pid}/cost-settings", json=cs))
    pj(c.post(f"/api/projects/{pid}/estimates", json={"label": "이전 방식"}))
    # 이전 코드가 저장한 모양으로 되돌린다: 총액 = 공급가액 + 부가세, 정책·끝수조정 필드 없음, 이전 상태 해시
    ctx = c.app.state.ctx
    p, _ = ctx.store.get(pid)
    e = p.estimates[-1]
    mm = e.result["money"]
    legacy_total = mm["supply"] + mm["vat"]
    for k in ("total_before_adjustment", "final_adjustment"):
        mm.pop(k)
    mm["total"] = legacy_total
    mm["rounding"] = {"unit": unit, "mode": "down", "label": "원 미만 절사" if unit == 1 else "10원 미만 절사"}
    from app.fp import estimates as est_mod
    from app.store import stable_hash

    old_hash = {"fp": est_mod._fp_fields(p), "design": est_mod._design_fields(p), "settings": p.cost_settings.model_dump(),
                "phases": p.overview.phases.model_dump(), "ratios": p.overview.phase_ratios.model_dump(), "boundary": p.overview.boundary_name,
                "std": e.standard_snapshot.get("id"), "method": e.method}
    e.input_hash = stable_hash(old_hash)
    ctx.db.execute("UPDATE projects SET data=? WHERE id=?", (p.model_dump_json(), pid))

    d = pj(c.get(f"/api/projects/{pid}"))
    e2 = d["project"]["estimates"][-1]
    assert e2["result"]["money"]["total"] == legacy_total and "final_adjustment" not in e2["result"]["money"]
    assert d["project"]["cost_settings"]["rounding"]["unit"] == unit  # 저장된 단위 그대로
    # 원 미만은 새 정책으로 다시 계산해도 같으므로 '현재 데이터와 일치' 유지, 10원 이상은 다시 계산하면 달라지므로 '갱신 필요'
    assert d["status"]["estimate_states"][e2["id"]] == ("current" if unit == 1 else "stale")
    vals, forms = _recalc(c, pid, tmp_path, f"legacy{unit}")
    got = _rows(vals["개발비_기준"])
    assert "최종 끝수조정(참고 조정)" not in got and got["총액(부가세 포함)"] == legacy_total
    bad = [r for r in vals["검산"].iter_rows(min_row=5, values_only=True) if r[0] and r[5] != "일치"]
    assert not bad, bad
    # 백업 → 복원해도 당시 견적·설정 그대로
    raw = c.get(f"/api/projects/{pid}/backup.json").content
    r = pj(c.post("/api/projects/restore", files={"file": ("b.json", raw, "application/json")}))
    assert r["project"]["estimates"][-1]["result"]["money"]["total"] == legacy_total
    assert r["project"]["cost_settings"]["rounding"]["unit"] == unit
    # 새 견적은 새 정책
    new = pj(c.post(f"/api/projects/{pid}/estimates", json={"label": "새 방식"}))["estimate"]["result"]["money"]
    assert new["rounding"]["policy"] == cost.ROUNDING_POLICY and new["total"] % unit == 0
    assert json.loads(raw)["project"]["estimates"][-1]["result"]["money"]["total"] == legacy_total
