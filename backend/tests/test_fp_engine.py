"""FP 엔진 검증. 기대값은 구현 함수를 호출해 만들지 않고 FP_RULES의 표와 공식 양식의 계산 캐시값에서 직접 옮겼다."""
from decimal import Decimal

import pytest

from app.fp import engine
from app.models import FPItem, Project


def proj(items, boundary="대상시스템"):
    p = Project(id="P1", name="t")
    p.overview.boundary_name = boundary
    for i, kw in enumerate(items, 1):
        kw.setdefault("status", "confirmed")
        kw.setdefault("application", boundary if kw.get("fp_type") != "EIF" else "")
        kw.setdefault("name", f"항목{i}")
        kw.setdefault("requirement_ids", [])
        p.fp_items.append(FPItem(id=f"FP-{i:03d}", **kw))
    return p


# (유형, FTR/RET, DET, 기대 복잡도, 기대 가중치) — FP_RULES §4 표에서 직접 옮김(경계값 위주)
BOUNDARY_CASES = [
    ("EI", 1, 4, "L", 3), ("EI", 1, 15, "L", 3), ("EI", 1, 16, "A", 4), ("EI", 0, 16, "A", 4),
    ("EI", 2, 4, "L", 3), ("EI", 2, 5, "A", 4), ("EI", 2, 15, "A", 4), ("EI", 2, 16, "H", 6),
    ("EI", 3, 4, "A", 4), ("EI", 3, 5, "H", 6), ("EI", 9, 1, "A", 4),
    ("EO", 1, 19, "L", 4), ("EO", 1, 20, "A", 5), ("EO", 2, 5, "L", 4), ("EO", 2, 6, "A", 5), ("EO", 3, 19, "A", 5), ("EO", 3, 20, "H", 7), ("EO", 4, 5, "A", 5), ("EO", 4, 6, "H", 7),
    ("EQ", 1, 19, "L", 3), ("EQ", 1, 20, "A", 4), ("EQ", 2, 5, "L", 3), ("EQ", 3, 6, "A", 4), ("EQ", 2, 20, "H", 6), ("EQ", 4, 5, "A", 4), ("EQ", 4, 6, "H", 6),
    ("ILF", 1, 50, "L", 7), ("ILF", 1, 51, "A", 10), ("ILF", 2, 19, "L", 7), ("ILF", 2, 20, "A", 10), ("ILF", 5, 50, "A", 10), ("ILF", 5, 51, "H", 15), ("ILF", 6, 19, "A", 10), ("ILF", 6, 20, "H", 15),
    ("EIF", 1, 50, "L", 5), ("EIF", 1, 51, "A", 7), ("EIF", 2, 20, "A", 7), ("EIF", 5, 51, "H", 10), ("EIF", 6, 19, "A", 7), ("EIF", 6, 20, "H", 10),
]


@pytest.mark.parametrize("t,ftr,det,cx,w", BOUNDARY_CASES)
def test_detailed_boundaries(std, t, ftr, det, cx, w):
    p = proj([{"fp_type": t, "ftr_ret": ftr, "det": det}])
    r = engine.evaluate_items(p, std)[0]
    assert (r.complexity, r.detailed_weight) == (cx, w)


SIMPLE = {"ILF": Decimal("7.5"), "EIF": Decimal("5.4"), "EI": Decimal("4.0"), "EO": Decimal("5.2"), "EQ": Decimal("3.9")}


def test_simple_weights_differ_from_detailed_path(std):
    p = proj([{"fp_type": t} for t in SIMPLE])
    s = engine.summary(p, std)
    assert Decimal(s["simple"]["total_fp"]) == Decimal("26.0")  # 7.5+5.4+4+5.2+3.9
    # 정통법은 DET/FTR 없으면 확정 불가(같은 산식이 아님)
    assert s["detailed"]["complete"] is False
    assert s["detailed"]["total_fp"] == "0"
    assert len(s["detailed"]["missing_ids"]) == 5


def test_official_template_sample_19_rows(std):
    """2101 정통법·간이법 양식의 예시 19행과 양식 캐시값(간이 97.2, 정통 105, 복잡도열)을 비교."""
    rows = [("EIF", 10, 40), ("ILF", 1, 22), ("ILF", 4, 22), ("EIF", 1, 13), ("EI", 1, 27), ("EI", 1, 6), ("EI", 2, 33), ("EO", 2, 7), ("EQ", 1, 44), ("ILF", 1, 5), ("EQ", 1, 5), ("ILF", 1, 5), ("EI", 1, 4), ("EI", 1, 4), ("EI", 1, 4), ("EQ", 1, 4), ("ILF", 2, 30), ("EI", 2, 30), ("EI", 2, 30)]
    template_cx = ["H", "L", "A", "L", "A", "L", "H", "A", "A", "L", "L", "L", "L", "L", "L", "L", "A", "H", "H"]
    p = proj([{"fp_type": t, "ftr_ret": f, "det": d, "name": f"r{i}"} for i, (t, f, d) in enumerate(rows)])
    s = engine.summary(p, std)
    assert [x["complexity"] for x in s["items"]] == template_cx
    assert Decimal(s["simple"]["total_fp"]) == Decimal("97.2")
    assert s["detailed"]["total_fp"] == "105"
    assert s["detailed"]["by_type"]["ILF"]["fp"] == 41 and s["detailed"]["by_type"]["EI"]["fp"] == 34


def test_missing_and_assumed(std):
    p = proj([
        {"fp_type": "EI", "ftr_ret": 1, "det": None},
        {"fp_type": "ILF", "ftr_ret": 0, "det": 10},
        {"fp_type": "EQ", "ftr_ret": None, "det": 5, "assumed_complexity": "A", "assumption_note": "화면 확정 전 평균 가정"},
    ])
    s = engine.summary(p, std)
    srcs = [x["complexity_source"] for x in s["items"]]
    assert srcs == ["missing", "missing", "assumed"]
    assert s["detailed"]["total_fp"] == "4"  # 가정 EQ A = 4
    assert s["detailed"]["complete"] is False
    assert s["detailed"]["assumed_ids"] == ["FP-003"]


def test_unconfirmed_and_unclassified_excluded(std):
    p = proj([{"fp_type": "EI", "status": "draft"}, {"fp_type": None}, {"fp_type": "EQ"}, {"fp_type": "EO", "status": "excluded"}])
    s = engine.summary(p, std)
    assert Decimal(s["simple"]["total_fp"]) == Decimal("3.9")
    assert s["counts"]["unconfirmed"] == 1 and s["counts"]["unclassified"] == 1
    assert Decimal(s["tentative_simple_fp_including_unconfirmed"]) == Decimal("7.9")


def test_duplicate_role_suffix_and_ilf_eif(std):
    p = proj([
        {"fp_type": "EQ", "name": "신청 내역 조회"},
        {"fp_type": "EQ", "name": "(관리자) 신청 내역 조회"},
        {"fp_type": "ILF", "name": "직원 정보"},
        {"fp_type": "EIF", "name": "직원 정보"},
    ])
    s = engine.summary(p, std)
    assert "FP-002" in s["duplicate_ids"]
    assert {"FP-003", "FP-004"} <= set(s["duplicate_ids"])
    # 자동으로 빼지 않음 — 사용자가 판단(duplicate_of 지정 시에만 제외)
    assert Decimal(s["simple"]["total_fp"]) == Decimal("3.9") * 2 + Decimal("7.5") + Decimal("5.4")
    p.fp_items[1].duplicate_of = "FP-001"
    s2 = engine.summary(p, std)
    assert Decimal(s2["simple"]["total_fp"]) == Decimal("3.9") + Decimal("7.5") + Decimal("5.4")


def test_boundary_exclusion(std):
    p = proj([{"fp_type": "EI", "application": "다른시스템"}, {"fp_type": "EI"}, {"fp_type": "EIF", "application": "인사시스템"}])
    s = engine.summary(p, std)
    assert s["boundary_ids"] == ["FP-001"]
    assert Decimal(s["simple"]["total_fp"]) == Decimal("4.0") + Decimal("5.4")


def test_coverage_marks_nfr_and_unlinked(std):
    from app.models import Requirement

    p = proj([{"fp_type": "EI", "requirement_ids": ["REQ-001"]}])
    p.requirements = [Requirement(id="REQ-001", title="신청"), Requirement(id="REQ-002", title="통계"), Requirement(id="REQ-003", title="응답시간", kind="nonfunctional")]
    cov = engine.coverage(p, engine.evaluate_items(p, std))
    states = {r["requirement_id"]: r["state"] for r in cov["rows"]}
    assert states["REQ-001"] == "FP 연결"
    assert states["REQ-002"] == "FP 미연결"
    assert states["REQ-003"].startswith("FP 대상 아님")
