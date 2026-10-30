"""정적 시연판 샘플 생성기(tools/demo_data.py) — 모델·계산 엔진·엑셀이 바뀌어도 샘플을 다시 만들고 검증할 수 있는지 확인."""
import json
import re

from tools import demo_data


def test_generate_and_check(tmp_path):
    out = tmp_path / "demo-data"
    man = demo_data.generate(out)
    assert demo_data.check(out) == []
    assert [s["pid"] for s in man["samples"]] == ["sampleA", "sampleB"]

    a = json.loads((out / "sampleA" / "project.json").read_text(encoding="utf-8"))
    b = json.loads((out / "sampleB" / "project.json").read_text(encoding="utf-8"))
    # A: 정상 완료 사례 — 미확정·대기 항목 없이 기준 산정·시나리오·검토까지
    ca = a["status"]["counts"]
    assert ca["fp_unconfirmed"] == ca["requirements_unconfirmed"] == ca["pending_proposals"] == ca["needs_review"] == 0
    assert a["status"]["next_steps"] == []
    est = a["project"]["estimates"][-1]
    assert est["complete"] and est["scenarios"]
    verdicts = {r["verdict"] for r in a["project"]["reviews"]}
    assert {"match", "diff", "check"} <= verdicts
    # B: 검토가 필요한 사례 — 미확정·미분류·중복 의심·확인 필요 연계·결정 대기 참고 항목
    cb = b["status"]["counts"]
    assert cb["fp_unconfirmed"] > 0 and cb["fp_unclassified"] > 0 and cb["fp_duplicates"] > 0 and cb["pending_proposals"] > 0
    assert any(r["decision"] == "pending" for r in b["project"]["reference_items"])
    assert {r["decision"] for r in b["project"]["reference_items"]} >= {"keep", "modify", "exclude"}
    assert all("확인 필요" in i["method"] for i in b["project"]["interfaces"])

    # 시연 표시·정적 경로·비밀값 없음
    system = json.loads((out / "system.json").read_text(encoding="utf-8"))
    assert system["ai"]["is_real_ai"] is False and [p["name"] for p in system["ai_profiles"]] == ["demo"]
    blob = "".join(f.read_text(encoding="utf-8") for f in out.rglob("*.json"))
    assert "demo-generator-" not in blob  # 생성기 임시 세션 키가 새지 않음
    assert not re.search(r"sk-[A-Za-z0-9_-]{16,}", blob)  # API 키 형태 없음
    assert "/api/" not in json.dumps(man)
    for s in man["samples"]:
        for f in list(s["xlsx"].values()) + list(s["originals"].values()):
            assert f.isascii() and (out / s["pid"] / f).exists()


def test_check_detects_tampering(tmp_path):
    out = tmp_path / "demo-data"
    demo_data.generate(out)
    fp = out / "sampleA" / "fp.json"
    d = json.loads(fp.read_text(encoding="utf-8"))
    d["simple"]["total_fp"] = "999.9"
    fp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    errs = demo_data.check(out)
    assert any("생성 후 바뀜" in e for e in errs) and any("FP 합계(simple)" in e for e in errs)
