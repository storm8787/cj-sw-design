"""설계·FP 비전문가 흐름(샘플 모드, AI 키 없음). 모든 사업·문서는 가상이다.

기대값은 앱 계산 결과를 옮겨 적지 않고, FP_RULES.md의 가중치·보정계수·공식으로 이 파일에서 따로 계산한다.
목표예산(2,200만 원)과 맞는지는 정답 기준이 아니다.
"""
import io
import json
from decimal import ROUND_DOWN, Decimal

import openpyxl

from app.ai.provider import MockProvider
from app.models import Project
from tests.conftest import client_for

REF_DOC = """가상시 관광 경비 환급 홈페이지 구축 과업지시서(가상 문서)
SFR-001 관광객이 여행 경비 환급을 온라인으로 신청하는 기능을 제공하여야 한다
SFR-002 신청자가 본인의 환급 신청 내역과 처리 상태를 조회하는 기능을 제공하여야 한다
SFR-003 담당자가 환급 신청을 심사하여 승인 또는 반려하는 기능을 제공하여야 한다
SFR-004 담당자가 가맹업소 정보를 등록하고 수정하는 기능을 제공하여야 한다
SFR-005 담당자가 월별 환급 현황 통계를 확인하는 기능을 제공하여야 한다
SFR-006 휴대전화 본인인증 기관과 연계하여 신청자 본인 확인을 하여야 한다
"""

# FP_RULES.md §3 간이법 평균 가중치
W = {"ILF": Decimal("7.5"), "EIF": Decimal("5.4"), "EI": Decimal("4.0"), "EO": Decimal("5.2"), "EQ": Decimal("3.9")}


def pj(r):
    assert r.status_code == 200, r.text
    return r.json()


def independent_money(fp: Decimal) -> dict[str, int]:
    """FP_RULES.md §5: 개발원가 = FP × 605,784 × 규모(500FP 미만 1.28) × 연계 0.94 × 성능 0.95 × 호환 1.00 × 보안 1.03,
    이윤 0.2(양식 예시값), 원 미만 절사, 부가세 10%."""
    dev = int((fp * 605784 * Decimal("1.28") * Decimal("0.94") * Decimal("0.95") * Decimal("1.00") * Decimal("1.03")).to_integral_value(ROUND_DOWN))
    profit = int((Decimal(dev) * Decimal("0.2")).to_integral_value(ROUND_DOWN))
    supply = dev + profit
    vat = int((Decimal(supply) * Decimal("0.1")).to_integral_value(ROUND_DOWN))
    return {"dev_cost": dev, "profit": profit, "supply": supply, "total": supply + vat}


def _cells(wb, sheet):
    return [str(c.value) for row in wb[sheet].iter_rows() for c in row if c.value is not None]


def test_scenario_a_reference_doc_to_estimate_without_fp_numbers(client):
    c = client
    pid = pj(c.post("/api/projects", json={"name": "가상 관광 경비 환급 홈페이지 구축", "overview": {
        "idea_text": "관광객 여행 경비 일부를 환급해 주는 홈페이지", "business_type": "portal", "users": "관광객, 시청 담당자",
        "budget_mode": "target", "target_amount": 22000000, "target_includes_vat": True}}))["project"]["id"]
    d = pj(c.post(f"/api/projects/{pid}/documents", files={"file": ("ref.txt", REF_DOC.encode(), "text/plain")}, data={"kind": "reference"}))["document"]
    pj(c.post(f"/api/projects/{pid}/documents/{d['id']}/analyze", json={}))
    p = pj(c.get(f"/api/projects/{pid}"))["project"]
    # 문서 제목 줄은 요구사항으로 뽑지 않는다
    assert len(p["reference_items"]) == 6 and not any("과업지시서" in r["text"] for r in p["reference_items"])
    for r in p["reference_items"]:
        pj(c.post(f"/api/projects/{pid}/reference-items/{r['id']}/decide", json={"decision": "keep"}))
    p = pj(c.get(f"/api/projects/{pid}"))["project"]
    titles = [r["title"] for r in p["requirements"]]
    assert "여행 경비 환급을 온라인으로 신청" in titles  # 짧은 제목, 원문은 보존
    assert all(r["original_text"].startswith("SFR-") for r in p["requirements"])

    # 사업 개요 빈 항목 제안: 이미 쓴 이용자는 그대로, 비어 있는 목적·FP 측정 대상만 채움
    prop = pj(c.post(f"/api/projects/{pid}/overview/suggest"))["project"]["proposals"][-1]
    assert prop["kind"] == "overview" and {i["key"] for i in prop["items"]} >= {"purpose", "boundary_name"} and "users" not in {i["key"] for i in prop["items"]}
    pj(c.post(f"/api/projects/{pid}/proposals/{prop['id']}/apply", json={}))
    ov = pj(c.get(f"/api/projects/{pid}"))["project"]["overview"]
    assert ov["boundary_name"] == "가상 관광 경비 환급 홈페이지" and ov["users"] == "관광객, 시청 담당자" and ov["purpose"]

    # 설계 초안: 조회·통계는 새 데이터를 만들지 않고, 같은 업무 대상(환급)은 데이터 하나로 묶는다
    r = pj(c.post(f"/api/projects/{pid}/ai/design", json={}))
    pj(c.post(f"/api/projects/{pid}/proposals/{r['job']['result']['proposal_id']}/apply", json={}))
    p = pj(c.get(f"/api/projects/{pid}"))["project"]
    assert sorted(x["name"] for x in p["data_entities"]) == ["가맹업소 정보", "여행 경비 환급 정보"]
    dat = {x["name"]: x["id"] for x in p["data_entities"]}
    fn = {x["name"]: x["id"] for x in p["functions"]}
    # 비전문가는 숫자 대신 업무 항목만 적는다(설계 단계 표 편집)
    pj(c.patch(f"/api/projects/{pid}/items/data_entities/{dat['여행 경비 환급 정보']}", json={"data": {"attributes": "신청자명, 연락처, 여행일자, 숙박업소명, 영수증 파일, 환급 계좌, 환급 금액, 처리 상태", "subgroups": ["심사 이력"]}}))
    pj(c.patch(f"/api/projects/{pid}/items/data_entities/{dat['가맹업소 정보']}", json={"data": {"attributes": "업소명, 주소, 업종, 사업자등록번호, 연락처"}}))
    pj(c.patch(f"/api/projects/{pid}/items/functions/{fn['여행 경비 환급을 온라인으로 신청']}", json={"data": {"inputs": "신청자명, 연락처, 여행일자, 숙박업소명, 영수증 파일, 환급 계좌"}}))

    r = pj(c.post(f"/api/projects/{pid}/ai/fp_candidates", json={}))
    pj(c.post(f"/api/projects/{pid}/proposals/{r['job']['result']['proposal_id']}/apply", json={}))
    p = pj(c.get(f"/api/projects/{pid}"))["project"]
    items = p["fp_items"]
    assert all(it["det"] is None and it["ftr_ret"] is None for it in items)  # 아무도 숫자를 넣지 않음
    got = sorted((it["fp_type"], it["name"]) for it in items)
    assert got == sorted([
        ("ILF", "여행 경비 환급 정보"), ("ILF", "가맹업소 정보"),
        ("EI", "여행 경비 환급을 온라인으로 신청"), ("EI", "환급 신청 승인"), ("EI", "환급 신청 반려"),
        ("EI", "가맹업소 정보 등록"), ("EI", "가맹업소 정보 수정"),
        ("EQ", "본인의 환급 신청 내역과 처리 상태를 조회"), ("EO", "월별 환급 현황 통계를 확인"),
        ("EI", "휴대전화 본인인증 기관과 연계하여 신청자 본인 확인"),
    ]), got

    # 업무 확인 전: 0 FP → '미산정', 금액 없음(0원을 견적으로 보여 주지 않음)
    fp = pj(c.get(f"/api/projects/{pid}/fp"))
    assert fp["basis"]["simple"]["basis"] == "empty"
    pv = pj(c.get(f"/api/projects/{pid}/estimate-preview"))
    assert pv["basis"]["basis"] == "empty" and pv["money"]["complete"] is False

    # 업무 확인: 있음 9건, 본인인증 연계는 '모름'(담당 부서 확인)
    auth = next(it for it in items if "본인인증" in it["name"])
    for it in items:
        data = {"status": "review", "uncertainty": "업무 확인 보류 — 담당 부서 확인 필요"} if it is auth else {"scope_confirmed": True}
        pj(c.patch(f"/api/projects/{pid}/items/fp_items/{it['id']}", json={"data": data}))
    expected = 2 * W["ILF"] + 5 * W["EI"] + W["EQ"] + W["EO"]  # 다른 9건, 본인인증 제외
    assert expected == Decimal("44.1")
    fp = pj(c.get(f"/api/projects/{pid}/fp"))
    assert Decimal(fp["simple"]["total_fp"]) == expected
    assert fp["basis"]["simple"]["basis"] == "partial" and fp["basis"]["simple"]["pending"]["not_confirmed"] == [auth["id"]]
    st = pj(c.get(f"/api/projects/{pid}"))["status"]
    assert any(x["category"] == "업무 결정 필요" and auth["id"] in x["ref"] for x in st["checklist"])

    # 담당 부서 답: 외부 본인인증 서비스를 쓰므로 이 시스템의 처리로 세지 않음 → '없음'
    pj(c.patch(f"/api/projects/{pid}/items/fp_items/{auth['id']}", json={"data": {"status": "excluded", "uncertainty": "업무 확인: 이번 사업에 없음"}}))
    fp = pj(c.get(f"/api/projects/{pid}/fp"))
    assert fp["basis"]["simple"]["basis"] == "estimated" and Decimal(fp["simple"]["total_fp"]) == expected
    assert fp["simple"]["complete"] is True  # 정통법 근거 부족이 간이법을 막지 않음

    # 정통법: 근거 목록에서 코드가 센 값(독립 계산: FP_RULES §4 복잡도표)
    res = {r["name"]: r for r in fp["items"]}
    a = res["여행 경비 환급 정보"]
    assert (a["det_used"], a["ftr_ret_used"], a["complexity"], a["detailed_weight"], a["complexity_source"]) == (8, 2, "L", 7, "derived")
    b = res["가맹업소 정보"]
    assert (b["det_used"], b["ftr_ret_used"], b["detailed_weight"]) == (5, 1, 7)
    e = res["여행 경비 환급을 온라인으로 신청"]
    assert (e["det_used"], e["ftr_ret_used"], e["complexity"], e["detailed_weight"]) == (6, 1, "L", 3)
    assert fp["basis"]["detailed"]["basis"] == "partial" and fp["basis"]["detailed"]["pending"]["detailed_missing"]
    assert not any("DET" in i for i in res["환급 신청 승인"]["issues"])  # 정통법 메모는 간이법 경고에 섞지 않음
    assert "DET" in res["환급 신청 승인"]["detailed_note"]

    # 재실행해도 늘지 않음
    r = pj(c.post(f"/api/projects/{pid}/ai/fp_candidates", json={}))
    if r["job"]["result"].get("proposal_id"):
        pj(c.post(f"/api/projects/{pid}/proposals/{r['job']['result']['proposal_id']}/apply", json={}))
    assert len(pj(c.get(f"/api/projects/{pid}"))["project"]["fp_items"]) == len(items)

    # 설정 저장 ≠ 견적. 기준 산정 실행 후에만 견적이 생긴다
    cs = pj(c.get(f"/api/projects/{pid}"))["project"]["cost_settings"]
    cs.update({"method": "simple", "integration_level": 2, "performance_level": 2, "compatibility_level": 2, "security_level": 3})
    d = pj(c.put(f"/api/projects/{pid}/cost-settings", json={**cs}))
    assert d["project"]["estimates"] == [] and any("기준 산정" in n["text"] for n in d["status"]["next_steps"])
    d = pj(c.post(f"/api/projects/{pid}/estimates", json={"label": "업무 확인 기준"}))
    est = d["project"]["estimates"][-1]
    m = est["result"]["money"]
    exp = independent_money(expected)
    assert {k: m[k] for k in exp} == exp
    assert est["result"]["basis"]["basis"] == "estimated" and any("추정" in w for w in est["warnings"])

    # 목표예산 시나리오: 기준 FP·항목 보존, 기준이 추정임을 경고
    d = pj(c.post(f"/api/projects/{pid}/estimates/{est['id']}/scenarios", json={"target_amount": 22000000, "includes_vat": True}))
    sc = d["project"]["estimates"][-1]["scenarios"][-1]
    assert Decimal(sc["result"]["base_total_fp"]) == expected and sc["result"]["total"] == 22000000
    assert sc["result"]["base_basis"] == "estimated" and any("추정" in w for w in sc["result"]["warnings"])

    # 엑셀이 실제 상태를 반영
    wb = openpyxl.load_workbook(io.BytesIO(c.get(f"/api/projects/{pid}/export.xlsx").content))
    simple = " ".join(_cells(wb, "FP_간이법"))
    assert "추정 산정" in simple and "확정 산정" not in simple
    assert "DET 미입력" not in simple and "정통법 근거 부족" not in simple  # 간이법 산출물에 정통법 오류를 섞지 않음
    assert "부분 산정" in " ".join(_cells(wb, "FP_정통법"))
    trace = " ".join(_cells(wb, "근거_변경이력"))
    assert "외부·기관 확인 필요" in trace and "미실행" in trace  # 연계 미확인, 문서 검토 미실행
    req = " ".join(_cells(wb, "요구사항"))
    assert "SFR-001" in req


def test_scenario_b_other_domain_idea_flow(client):
    """다른 업무(가상 공공 체육시설 대관). 구상 → 요구사항 → 설계 → FP 후보 → 업무 확인 → 추정 산정."""
    c = client
    pid = pj(c.post("/api/projects", json={"name": "가상 체육시설 대관 시스템", "overview": {"idea_text": "구민이 체육시설을 온라인으로 대관 신청하는 시스템", "boundary_name": "체육시설대관시스템"}}))["project"]["id"]
    feat = "체육시설 등록·수정\n대관 신청\n대관 신청 취소\n대관 승인·반려\n대관 내역 조회\n시설별 이용 통계"
    r = pj(c.post(f"/api/projects/{pid}/ai/requirements", json={"feature_text": feat}))
    pj(c.post(f"/api/projects/{pid}/proposals/{r['job']['result']['proposal_id']}/apply", json={}))
    r = pj(c.post(f"/api/projects/{pid}/ai/design", json={}))
    pj(c.post(f"/api/projects/{pid}/proposals/{r['job']['result']['proposal_id']}/apply", json={}))
    r = pj(c.post(f"/api/projects/{pid}/ai/fp_candidates", json={}))
    pj(c.post(f"/api/projects/{pid}/proposals/{r['job']['result']['proposal_id']}/apply", json={}))
    p = pj(c.get(f"/api/projects/{pid}"))["project"]
    names = [it["name"] for it in p["fp_items"]]
    assert len(names) == len(set(names))
    for it in p["fp_items"]:
        if it["fp_type"]:
            pj(c.patch(f"/api/projects/{pid}/items/fp_items/{it['id']}", json={"data": {"scope_confirmed": True}}))
    fp = pj(c.get(f"/api/projects/{pid}/fp"))
    typed = [it for it in p["fp_items"] if it["fp_type"]]
    assert Decimal(fp["simple"]["total_fp"]) == sum((W[it["fp_type"]] for it in typed), Decimal(0))
    assert fp["basis"]["simple"]["basis"] in ("estimated", "partial") and fp["simple"]["complete"]
    # 다른 언어가 섞인 이름은 표시되고 확인 목록에 남는다
    pj(c.patch(f"/api/projects/{pid}/items/fp_items/{typed[0]['id']}", json={"data": {"name": "施設の登録"}}))
    st = pj(c.get(f"/api/projects/{pid}"))["status"]
    assert any(x["category"] == "FP 기술 검토 필요" and "다른 언어" in x["text"] for x in st["checklist"])


def test_scenario_c_ai_rerun_duplicates_become_updates(app_factory):
    """AI 재실행: 같은 처리 → 갱신 변경안(빈 칸만), 비슷한 처리 → 추가하되 표시, 적용 시점에 이미 있으면 merged. 기존 항목은 지우지 않는다."""
    def it(name, **kw):
        return {"name": name, "fp_type": "EI", "rationale": "", "uncertainty": "", "det": None, "ftr_ret": None, "det_items": [], "ret_groups": [], "requirement_ids": [], "function_ids": ["FN-001"], "data_ids": [], **kw}

    first = {"items": [it("수료증 발급 신청", rationale="신청 등록", det=9, ftr_ret=2)]}
    again = {"items": [it("수료증 발급 신청", rationale="다른 근거", det_items=["과정명", "신청자"]), it("수료증 신청 내역 확인")]}
    prov = MockProvider()
    prov.responses = {"fp_candidates": [json.dumps(first, ensure_ascii=False), json.dumps(again, ensure_ascii=False), json.dumps(first, ensure_ascii=False)]}
    c = client_for(app_factory(provider=prov))
    pid = c.post("/api/projects", json={"name": "x", "sample": "education"}).json()["project"]["id"]
    n0 = len(pj(c.get(f"/api/projects/{pid}"))["project"]["fp_items"])
    j = c.post(f"/api/projects/{pid}/ai/fp_candidates", json={}).json()["job"]
    pj(c.post(f"/api/projects/{pid}/proposals/{j['result']['proposal_id']}/apply", json={}))
    p = pj(c.get(f"/api/projects/{pid}"))["project"]
    new = p["fp_items"][-1]
    assert len(p["fp_items"]) == n0 + 1 and new["name"] == "수료증 발급 신청" and new["det"] is None  # AI 숫자는 쓰지 않음
    j = c.post(f"/api/projects/{pid}/ai/fp_candidates", json={}).json()["job"]
    pr = next(x for x in pj(c.get(f"/api/projects/{pid}"))["project"]["proposals"] if x["id"] == j["result"]["proposal_id"])
    ops = {i["data"].get("name", i["target_id"]): i for i in pr["items"]}
    upd = next(i for i in pr["items"] if i["op"] == "update")
    assert upd["target_id"] == new["id"] and "rationale" not in upd["data"] and upd["data"]["det_items"] == ["과정명", "신청자"]
    assert any(i["op"] == "add" and "비슷" in i["reason"] for i in pr["items"]), ops
    # 세 번째 실행: 대기 중 변경안과도 겹치지 않게
    j3 = c.post(f"/api/projects/{pid}/ai/fp_candidates", json={}).json()["job"]
    pr3 = next((x for x in pj(c.get(f"/api/projects/{pid}"))["project"]["proposals"] if x["id"] == j3["result"].get("proposal_id")), None)
    assert pr3 is None or not any(i["op"] == "add" and i["data"].get("name") == "수료증 발급 신청" for i in pr3["items"])
    pj(c.post(f"/api/projects/{pid}/proposals/{pr['id']}/apply", json={}))
    p = pj(c.get(f"/api/projects/{pid}"))["project"]
    kept = next(x for x in p["fp_items"] if x["id"] == new["id"])
    assert kept["rationale"] == "신청 등록" and kept["det_items"] == ["과정명", "신청자"]  # 사용자·기존 값 유지, 빈 칸만 채움
    assert sum(1 for x in p["fp_items"] if x["name"] == "수료증 발급 신청") == 1


def test_apply_guard_marks_merged(client):
    """같은 이름의 추가 변경안을 두 번 적용해도 항목은 하나(두 번째는 merged)."""
    c = client
    pid = pj(c.post("/api/projects", json={"name": "x", "sample": "education"}))["project"]["id"]
    from app.services import proposals as P

    a = {"name": "새 처리", "fp_type": "EI"}
    assert P.match_fp(a, [{"name": "새  처리", "fp_type": "EI"}])[1] == "same"
    assert P.match_fp({"name": "과정 등록", "fp_type": "EI", "function_ids": ["FN-1"]}, [{"name": "과정 수정", "fp_type": "EI", "function_ids": ["FN-1"]}])[1] is None


def test_old_project_data_loads_with_defaults():
    """기존 저장 데이터(새 필드 없음)를 읽으면 기본값이 채워지고 업무 확인 전 상태가 된다(삭제·재설정 없음)."""
    raw = {"id": "P1", "name": "옛 사업", "fp_items": [{"id": "FP-001", "name": "신청", "fp_type": "EI", "status": "draft"}],
           "data_entities": [{"id": "DAT-001", "name": "신청 정보"}]}
    p = Project.model_validate(raw)
    assert p.fp_items[0].scope_confirmed is False and p.fp_items[0].det_items == [] and p.data_entities[0].subgroups == []
