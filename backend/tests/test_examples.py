"""저장소 examples/의 모의데이터가 실제 앱 경로에서 쓰이는지(AI 호출 없음)."""
from app.services import examples


def _up(c, pid, name, kind):
    data, ctype = examples.read(name)
    r = c.post(f"/api/projects/{pid}/documents", files={"file": (name.rsplit("/", 1)[-1], data, ctype.split(";")[0])}, data={"kind": kind})
    assert r.status_code == 200, r.text
    return r.json()["document"]


def test_example_files_listed_and_downloadable(client):
    files = client.get("/api/examples").json()["files"]
    assert {f["case"] for f in files} == {"A", "B", "C"}
    for f in files:
        r = client.get(f"/api/examples/{f['name']}")
        assert r.status_code == 200 and r.content, f["name"]
        assert "attachment" in r.headers["content-disposition"]
    assert client.get("/api/examples/../README.md").status_code == 404
    assert client.get("/api/examples/C-review/vendor_fp.csv").status_code == 404  # 허용 목록만


def test_example_b_reference_flow_keeps_source(client):
    c = client
    pid = c.post("/api/projects", json={"name": "[예제] 참고문서", "overview": {"start_mode": "document"}}).json()["project"]["id"]
    d = _up(c, pid, "B-reference/reference_task_order.txt", "reference")
    assert d["file_name"] == "reference_task_order.txt"
    j = c.post(f"/api/projects/{pid}/documents/{d['id']}/analyze", json={}).json()["job"]
    assert j["status"] == "succeeded" and not j.get("usage")  # 샘플 규칙(AI 호출 없음)
    refs = c.get(f"/api/projects/{pid}").json()["project"]["reference_items"]
    org = {r["text"][:7]: r["org_specific"] for r in refs}
    assert any("budget" in v for v in org.values()) and any("product" in v for v in org.values())  # 예산·특정 제품 표시
    r = next(x for x in refs if x["text"].startswith("SFR-001"))
    c.post(f"/api/projects/{pid}/reference-items/{r['id']}/decide", json={"decision": "keep"})
    p = c.get(f"/api/projects/{pid}").json()["project"]
    req = next(x for x in p["requirements"] if x["original_text"].startswith("SFR-001"))
    src = next(s for s in p["sources"] if s["id"] in req["source_ids"])
    assert src["file_name"] == "reference_task_order.txt" and src["location"].endswith("줄")


def test_example_c_review_detects_planted_issues(client):
    """기대 확인 목록(examples/C-review/expected_findings.md)의 '탐지 가능' 항목이 실제 검토 엔진 결과에 나타나는지."""
    c = client
    pid = c.post("/api/projects", json={"name": "[예제] 기존 문서 검토", "overview": {"start_mode": "review"}}).json()["project"]["id"]
    for name, _, case, _, kind in examples.FILES:
        if case == "C" and kind:
            _up(c, pid, name, kind)
    p = c.post(f"/api/projects/{pid}/review/run", json={}).json()["project"]
    got = {(f["category"], f["verdict"]) for f in p["reviews"]}
    text = " ".join(f"{f['category']} {f['verdict']} {f['original_value']} {f['compared_value']}" for f in p["reviews"])
    assert ("요구사항 누락", "diff") in got and "SFR-005" in text
    assert ("FP 가중치", "diff") in got and "과정별 통계" in text
    assert ("FP 중복", "check") in got
    assert ("FP 합계", "diff") in got and "48.2" in text
    assert ("부가세", "diff") in got
    assert ("단가", "match") in got and ("금액 산식", "match") in got and ("합계", "match") in got
    assert ("장비 포함 여부", "check") in got
    assert ("범위 불명확", "check") in got and ("연계 조건", "check") in got and ("성능·보안", "check") in got
