"""개발비·목표예산 검증. 기대값은 손계산(주석)과 공식 양식 캐시값에서 가져왔다."""
from decimal import Decimal

import pytest

from app.fp import cost
from app.models import CostSettings, DirectExpense, Overview


def test_size_factor(std):
    assert cost.size_factor(std, Decimal("499.9")) == Decimal("1.28")
    assert cost.size_factor(std, Decimal("3000.1")) == Decimal("1.153")
    # 손계산: ln(1000)=6.907755279, −7.1978=−0.290044721, 제곱=0.084125940, ×0.4057=0.034129894, +0.8878=0.921929894
    assert abs(cost.size_factor(std, Decimal(1000)) - Decimal("0.921929894")) < Decimal("1e-8")
    # 경계 500: 0.4057×(6.214608098−7.1978)²+0.8878 = 0.4057×0.966665 + 0.8878 = 1.279977…
    assert abs(cost.size_factor(std, Decimal(500)) - Decimal("1.27997")) < Decimal("1e-5")


def test_official_template_dev_cost(std):
    """2101 정통법 양식: 105FP × 605,784 × 1.28 × 0.88 × 0.91 × 0.94 × 1.00 = 61,287,087.801139206(양식 캐시값)."""
    s = CostSettings(integration_level=1, performance_level=1, compatibility_level=1, security_level=2, profit_rate="0.25")
    r = cost.compute_cost(std, s, Overview(), Decimal(105))
    assert abs(Decimal(r["dev_cost_raw"]) - Decimal("61287087.801139206")) < Decimal("0.000001")
    # 양식 이윤 25% 캐시값 15,321,771.95 → 원 미만 절사 규칙에서는 개발원가 61,287,087 기준 15,321,771
    assert r["dev_cost"] == 61287087 and r["profit"] == 15321771


def test_education_hand_calc(std):
    """손계산: 61.4×605,784=37,195,137.6 ×1.28=47,609,776.128 ×0.88=41,896,602.99264 ×0.91=38,125,908.7233 ×0.94=35,838,354.1999
    → 개발원가 35,838,354, 이윤(20%) 7,167,670(.8 절사), 공급가 43,006,024, VAT 4,300,602(.4 절사), 총 47,306,626"""
    r = cost.compute_cost(std, CostSettings(), Overview(), Decimal("61.4"))
    assert (r["dev_cost"], r["profit"], r["supply"], r["vat"], r["total"]) == (35838354, 7167670, 43006024, 4300602, 47306626)
    assert r["equipment_excluded"] is True
    assert any("이윤율" in w and "확인" in w for w in r["warnings"])


def test_rounding_modes_and_direct(std):
    s = CostSettings(rounding={"unit": 1000, "mode": "half_up"}, direct_expenses=[DirectExpense(id="DE-1", name="교육 교재", basis="30부", amount=450000)])
    r = cost.compute_cost(std, s, Overview(), Decimal("61.4"))
    # 35,838,354.1999 → 천원 반올림 35,838,000 / 이윤 35,838,000×0.2=7,167,600 → 7,168,000
    # 공급 35,838,000+7,168,000+450,000=43,456,000 / VAT 4,345,600 → 4,346,000 / 총 47,802,000
    assert (r["dev_cost"], r["profit"], r["supply"], r["vat"], r["total"]) == (35838000, 7168000, 43456000, 4346000, 47802000)


def test_equipment_warning(std):
    s = CostSettings(direct_expenses=[DirectExpense(id="d", name="서버 구매", basis="", amount=1000)])
    r = cost.compute_cost(std, s, Overview(), Decimal(10))
    assert any("장비 구매비" in w for w in r["warnings"])


def test_phase_ratio(std):
    ov = Overview(phases={"analysis": True, "design": True, "implementation": False, "test": False})
    r = cost.compute_cost(std, CostSettings(), ov, Decimal(100))
    assert r["complete"] is False
    ov.phase_ratios.analysis, ov.phase_ratios.design = "0.3", "0.3"
    r = cost.compute_cost(std, CostSettings(), ov, Decimal(100))
    full = cost.compute_cost(std, CostSettings(), Overview(), Decimal(100))
    assert Decimal(r["dev_cost_raw"]) == Decimal(full["dev_cost_raw"]) * Decimal("0.6")


def test_target_scenario_exact(std):
    base = cost.compute_cost(std, CostSettings(), Overview(), Decimal("61.4"))
    sc = cost.target_scenario(base, 80_000_000, True)
    # 손계산: S0=floor(80,000,000/1.1)=72,727,272 → 72,727,272+7,272,727=79,999,999(불일치), 72,727,273+7,272,727=80,000,000(일치)
    assert sc["supply"] == 72_727_273 and sc["vat"] == 7_272_727 and sc["total"] == 80_000_000
    # 개발원가 72,727,273/1.2=60,606,060.83→60,606,060, 이윤 12,121,212, 끝수조정 72,727,273−72,727,272=1
    assert (sc["dev_cost"], sc["profit"], sc["rounding_adjustment"]) == (60_606_060, 12_121_212, 1)
    assert sc["matches_target"] is True and sc["vat_method"] == "rate"
    r = Decimal(sc["adjustment_ratio"])
    assert abs(r - Decimal("60606060.8333333333") / Decimal(base["dev_cost_raw"])) < Decimal("1e-15")
    assert sc["base_total_fp"] == "61.4"  # 기준 FP 보존
    assert abs(Decimal(sc["equivalent_fp"]) - Decimal("61.4") * r) < Decimal("1e-15")
    assert sc["supply"] + sc["vat"] == sc["total"]
    assert sc["dev_cost"] + sc["profit"] + sc["direct_total"] + sc["rounding_adjustment"] == sc["supply"]


def test_target_scenario_lower_and_unreachable(std):
    base = cost.compute_cost(std, CostSettings(), Overview(), Decimal("61.4"))
    low = cost.target_scenario(base, 30_000_000, True)
    assert Decimal(low["adjustment_ratio"]) < 1 and any("기준 산정보다 낮" in w for w in low["warnings"])
    # S + floor(S/10) 은 120,000,000을 만들 수 없음(109,090,909→119,999,999 / 109,090,910→120,000,001)
    # → 역산: 공급가액 floor(120,000,000/1.1)=109,090,909, 부가세 10,909,091(세율 방식 10,909,090과 +1원 차이 공개)
    inv = cost.target_scenario(base, 120_000_000, True)
    assert inv["vat_method"] == "inverse" and inv["matches_target"] is True
    assert (inv["supply"], inv["vat"], inv["vat_by_rate"], inv["vat_residual"]) == (109_090_909, 10_909_091, 10_909_090, 1)
    assert any("역산" in w for w in inv["warnings"])
    ex = cost.target_scenario(base, 50_000_000, False)
    assert ex["supply"] == 50_000_000 and ex["vat"] == 5_000_000


def test_target_errors(std):
    s = CostSettings(direct_expenses=[DirectExpense(id="d", name="교재", amount=5_000_000)])
    base = cost.compute_cost(std, s, Overview(), Decimal("61.4"))
    with pytest.raises(cost.CostError):
        cost.target_scenario(base, 4_000_000, False)
