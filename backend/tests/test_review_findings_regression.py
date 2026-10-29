"""PR #1 리뷰 지적 회귀 테스트: 복원 경로 조작, 비교 못 한 FP 가중치, 이윤율/이윤 구분."""
import json

from app.services import backup
from tests import fixtures_gen as fg
from tests.test_documents import up


def test_restore_rejects_crafted_stored_name(client, tmp_path):
    c = client
    pid = c.post("/api/projects", json={"name": "백업"}).json()["project"]["id"]
    up(c, pid, "a.txt", "SFR-001 신청 기능을 제공하여야 한다".encode())
    victim = tmp_path / "victim.txt"
    victim.write_text("지우면 안 됨")
    data = json.loads(c.get(f"/api/projects/{pid}/backup.json").content)
    for bad in (str(victim), "../../app.db", "DOC-001.txt/../../x"):
        data["project"]["documents"][0]["stored_name"] = bad
        body = {k: data[k] for k in ("project", "changes", "snapshots", "doc_chunks")}
        data["sha256"] = backup._digest(body)  # 체크섬은 누구나 다시 계산할 수 있음
        r = c.post("/api/projects/restore", files={"file": ("b.json", json.dumps(data).encode(), "application/json")})
        assert r.status_code == 422, bad
    assert victim.exists()


def test_fp_rows_without_weights_are_not_reported_as_match(client):
    c = client
    pid = c.post("/api/projects", json={"name": "검토"}).json()["project"]["id"]
    rows = [["단위프로세스명", "FP유형", "가중치"], ["신청 등록", "EI", None], ["신청 조회", "EQ", None]]
    up(c, pid, "FP.xlsx", fg.xlsx_bytes({"FP": rows}), "vendor_fp")
    f = c.post(f"/api/projects/{pid}/review/run", json={}).json()["project"]["reviews"]
    fp = [x for x in f if x["category"] == "FP 가중치"]
    assert not any(x["verdict"] == "match" for x in fp)
    assert any(x["verdict"] == "insufficient" and "2행" in x["reason"] for x in fp)


def test_profit_rate_row_not_read_as_profit_amount(client):
    c = client
    pid = c.post("/api/projects", json={"name": "금액"}).json()["project"]["id"]
    rows = [["구분", "값"], ["개발원가", 1000000], ["이윤율", 0.2], ["이윤", 200000], ["직접경비", 0], ["소프트웨어 개발비(부가세 별도)", 1200000], ["부가가치세", 120000], ["총액", 1320000]]
    up(c, pid, "금액.xlsx", fg.xlsx_bytes({"개발비": rows}), "vendor_cost")
    f = c.post(f"/api/projects/{pid}/review/run", json={}).json()["project"]["reviews"]
    profit = next(x for x in f if x["category"] == "이윤")
    assert "200,000" in profit["original_value"] and "20.00%" in profit["compared_value"]
    sums = [x for x in f if x["category"] == "합계"]
    assert sums and all(x["verdict"] == "match" for x in sums)
