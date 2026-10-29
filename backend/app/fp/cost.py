"""개발비 계산(FP_RULES §5)과 목표예산 시나리오(FP_RULES §6).

모든 금액·비율은 Decimal. 끝수 처리는 Rounding 설정(단위·절사/반올림)으로 정해진 지점에서만 한다.
"""
from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, localcontext
from typing import Any

from ..models import CostSettings, Overview

PHASE_KEYS = ("analysis", "design", "implementation", "test")
PHASE_LABELS = {"analysis": "분석", "design": "설계", "implementation": "구현", "test": "시험"}


class CostError(ValueError):
    pass


def rnd(x: Decimal, unit: int, mode: str) -> int:
    u = Decimal(unit)
    q = (x / u).to_integral_value(rounding=ROUND_DOWN if mode == "down" else ROUND_HALF_UP)
    return int(q * u)


def rounding_label(unit: int, mode: str) -> str:
    unit_s = {1: "원 미만", 10: "10원 미만", 100: "100원 미만", 1000: "1,000원 미만"}[unit]
    return f"{unit_s} {'절사' if mode == 'down' else '반올림'}"


def size_factor(std: dict[str, Any], fp: Decimal) -> Decimal:
    sf = std["size_factor"]
    if fp < Decimal(sf["below_fp"]):
        return Decimal(sf["below_value"])
    if fp > Decimal(sf["above_fp"]):
        return Decimal(sf["above_value"])
    with localcontext() as ctx:
        ctx.prec = 28
        return Decimal(sf["a"]) * (fp.ln() - Decimal(sf["b"])) ** 2 + Decimal(sf["c"])


def size_note(fp: Decimal) -> str:
    if fp < 500:
        return "500FP 미만 고정값"
    if fp > 3000:
        return "3,000FP 초과 고정값"
    return "0.4057×(ln FP−7.1978)²+0.8878"


def factor_values(std: dict[str, Any], settings: CostSettings) -> list[dict[str, Any]]:
    ft = std["factor_tables"]
    out = []
    for key, level in (
        ("integration", settings.integration_level),
        ("performance", settings.performance_level),
        ("compatibility", settings.compatibility_level),
        ("security", settings.security_level),
    ):
        label_text, value = ft[key]["levels"][str(level)]
        out.append({"key": key, "label": ft[key]["label"], "level": level, "level_text": label_text, "value": Decimal(value)})
    return out


def phase_multiplier(overview: Overview) -> tuple[Decimal | None, str, list[str]]:
    included = [k for k in PHASE_KEYS if getattr(overview.phases, k)]
    if not included:
        return None, "포함 단계 없음", ["포함 단계가 하나도 선택되지 않았습니다."]
    if len(included) == len(PHASE_KEYS):
        return Decimal(1), "분석·설계·구현·시험 전 단계 포함(비율 1.0)", []
    warnings = []
    total = Decimal(0)
    for k in included:
        v = getattr(overview.phase_ratios, k)
        if v in (None, ""):
            warnings.append(f"{PHASE_LABELS[k]} 단계 비율 미입력(공식 단계별 비율 미확인 — 사용자 입력 필요)")
            continue
        dv = Decimal(str(v))
        if dv < 0 or dv > 1:
            raise CostError("단계 비율은 0~1 사이여야 합니다.")
        total += dv
    if warnings:
        return None, "일부 단계 포함(비율 미입력)", warnings
    if total <= 0 or total > 1:
        raise CostError("포함 단계 비율 합계는 0 초과 1 이하여야 합니다.")
    names = "·".join(PHASE_LABELS[k] for k in included)
    return total, f"{names} 단계만 포함(사용자 입력 비율 합 {total}, 공식 비율 미확인)", ["단계 비율은 사용자 입력값이며 공식 기준 미확인"]


def compute_cost(std: dict[str, Any], settings: CostSettings, overview: Overview, total_fp: Decimal) -> dict[str, Any]:
    unit, mode = settings.rounding.unit, settings.rounding.mode
    warnings: list[str] = []
    std_price = int(std["unit_price"]["value"])
    unit_price = settings.unit_price if settings.unit_price is not None else std_price
    if unit_price <= 0:
        raise CostError("FP당 단가는 양수여야 합니다.")
    if settings.unit_price is not None and settings.unit_price != std_price:
        warnings.append(f"FP당 단가를 기준값({std_price:,}원)이 아닌 사용자 입력값({unit_price:,}원)으로 적용")
    profit_rate = Decimal(settings.profit_rate) if settings.profit_rate not in (None, "") else Decimal(std["profit_rate"]["value"])
    if profit_rate < 0 or profit_rate > 1:
        raise CostError("이윤율은 0~1 사이여야 합니다.")
    if std["profit_rate"].get("status") != "user_defined" and settings.profit_rate in (None, ""):
        warnings.append(f"이윤율 {profit_rate}는 양식 예시값(공식 기준 미확인) — 확인 필요")
    vat_rate = Decimal(settings.vat_rate)
    for d in settings.direct_expenses:
        if d.amount < 0:
            raise CostError("직접경비는 음수일 수 없습니다.")
        if any(w in (d.name + d.basis) for w in ("장비", "서버 구매", "하드웨어 구매", "HW 구매")):
            warnings.append(f"직접경비 '{d.name}'가 장비 구매비로 보입니다 — 장비 구매비는 개발비에 포함하지 않습니다(확인 필요)")

    size = size_factor(std, total_fp)
    factors = factor_values(std, settings)
    pm, phase_text, phase_warn = phase_multiplier(overview)
    warnings += phase_warn

    product = size
    for f in factors:
        product *= f["value"]

    direct = sum(d.amount for d in settings.direct_expenses)
    basis_lines = [
        f"총 기능점수 {total_fp} FP × FP당 단가 {unit_price:,}원",
        f"× 규모 보정 {size:.6f} ({size_note(total_fp)})",
    ] + [f"× {f['label']} {f['value']} ({f['level_text']})" for f in factors]
    if pm is None:
        return {
            "complete": False,
            "warnings": warnings + ["단계 비율이 정해지지 않아 금액을 확정 계산하지 않았습니다."],
            "total_fp": str(total_fp),
            "unit_price": unit_price,
            "size_factor": str(size),
            "factors": [{**f, "value": str(f["value"])} for f in factors],
            "phase_text": phase_text,
        }
    basis_lines.append(f"× 단계 비율 {pm} ({phase_text})")

    dev_cost_raw = total_fp * Decimal(unit_price) * product * pm
    dev_cost = rnd(dev_cost_raw, unit, mode)
    profit_raw = Decimal(dev_cost) * profit_rate
    profit = rnd(profit_raw, unit, mode)
    supply = dev_cost + profit + direct
    vat = rnd(Decimal(supply) * vat_rate, unit, mode)
    total = supply + vat
    rl = rounding_label(unit, mode)
    basis_lines += [
        f"= 개발원가(보정 후) {dev_cost_raw:.4f} → {rl} {dev_cost:,}원",
        f"이윤 = {dev_cost:,} × {profit_rate} = {profit_raw:.4f} → {profit:,}원",
        f"직접경비 합계 {direct:,}원",
        f"SW개발비(부가세 별도) = {dev_cost:,} + {profit:,} + {direct:,} = {supply:,}원",
        f"부가세 = {supply:,} × {vat_rate} → {rl} {vat:,}원",
        f"총액(부가세 포함) = {total:,}원",
    ]
    return {
        "complete": True,
        "warnings": warnings,
        "total_fp": str(total_fp),
        "unit_price": unit_price,
        "unit_price_source": "user" if settings.unit_price is not None else "standard",
        "size_factor": str(size),
        "factors": [{**f, "value": str(f["value"])} for f in factors],
        "factor_product": str(product),
        "phase_multiplier": str(pm),
        "phase_text": phase_text,
        "dev_cost_raw": str(dev_cost_raw),
        "dev_cost": dev_cost,
        "profit_rate": str(profit_rate),
        "profit": profit,
        "direct_expenses": [d.model_dump() for d in settings.direct_expenses],
        "direct_total": direct,
        "supply": supply,
        "vat_rate": str(vat_rate),
        "vat": vat,
        "total": total,
        "rounding": {"unit": unit, "mode": mode, "label": rl},
        "basis": basis_lines,
        "equipment_excluded": True,
    }


def _supply_for_vat_inclusive(target: int, vat_rate: Decimal, unit: int, mode: str) -> tuple[int, int]:
    """S + rnd(S×vat) = target 인 정수 S. 없으면 가장 가까운 S와 차이를 반환."""
    s0 = int((Decimal(target) / (1 + vat_rate)).to_integral_value(rounding=ROUND_DOWN))
    best: tuple[int, int] | None = None
    for s in range(max(0, s0 - 3 * unit - 3), s0 + 3 * unit + 4):
        diff = target - (s + rnd(Decimal(s) * vat_rate, unit, mode))
        if diff == 0:
            return s, 0
        if best is None or abs(diff) < abs(best[1]) or (abs(diff) == abs(best[1]) and diff > 0):
            best = (s, diff)
    assert best is not None
    return best


def target_scenario(base: dict[str, Any], target_amount: int, includes_vat: bool) -> dict[str, Any]:
    """기준 견적 결과(base)를 보존한 채 목표 금액에 맞춘 참고 구성을 만든다."""
    if not base.get("complete"):
        raise CostError("기준 산정이 완료되지 않아 목표예산 시나리오를 만들 수 없습니다.")
    if target_amount <= 0:
        raise CostError("목표 금액은 양수여야 합니다.")
    unit, mode = base["rounding"]["unit"], base["rounding"]["mode"]
    vat_rate = Decimal(base["vat_rate"])
    p = Decimal(base["profit_rate"])
    direct = int(base["direct_total"])
    vat_method = "rate"
    if includes_vat:
        supply_t, vat_residual = _supply_for_vat_inclusive(target_amount, vat_rate, unit, mode)
        if vat_residual:
            # 세율 방식으로 정확히 맞출 수 없으면 역산 방식: 공급가액 = 목표액÷(1+세율) 끝수 절사, 부가세 = 목표액 − 공급가액
            supply_t = int((Decimal(target_amount) / (1 + vat_rate)).to_integral_value(rounding=ROUND_DOWN))
            vat_method = "inverse"
    else:
        supply_t, vat_residual = target_amount, 0
    if supply_t <= direct:
        raise CostError("목표 공급가액이 직접경비보다 작거나 같아 구성할 수 없습니다.")
    c_t_raw = (Decimal(supply_t) - direct) / (1 + p)
    base_raw = Decimal(base["dev_cost_raw"])
    if base_raw <= 0:
        raise CostError("기준 개발원가가 0이어서 조정률을 계산할 수 없습니다(확정 FP 없음).")
    r = c_t_raw / base_raw
    c_t = rnd(c_t_raw, unit, mode)
    p_t = rnd(Decimal(c_t) * p, unit, mode)
    adjust = supply_t - (c_t + p_t + direct)
    vat_by_rate = rnd(Decimal(supply_t) * vat_rate, unit, mode)
    vat_t = target_amount - supply_t if vat_method == "inverse" else vat_by_rate
    total_t = supply_t + vat_t
    base_total = int(base["total"])
    base_supply = int(base["supply"])
    total_fp = Decimal(base["total_fp"])
    warnings = []
    if r < 1:
        warnings.append("목표 금액이 기준 산정보다 낮습니다. 요구 기능은 그대로 유지되며, 조정률은 공식 산정 결과가 아닌 참고값입니다.")
    if vat_method == "inverse":
        warnings.append(f"공급가액×세율({vat_by_rate:,}원)로는 목표액과 정확히 맞출 수 없어 부가세를 역산(목표액 − 공급가액 = {vat_t:,}원)했습니다. 차이 {vat_t - vat_by_rate:+,}원.")
    if adjust:
        warnings.append(f"원 단위 일치를 위해 끝수조정 {adjust:+,}원을 별도 행으로 표시합니다.")
    return {
        "kind": "target_budget_reference",
        "label": "목표예산 시나리오(참고 견적, 공식 측정값 아님)",
        "target_amount": target_amount,
        "target_includes_vat": includes_vat,
        "base_total": base_total,
        "base_supply": base_supply,
        "difference_total": total_t - base_total,
        "difference_supply": supply_t - base_supply,
        "adjustment_ratio": str(r),
        "adjustment_ratio_display": f"{(r * 100):.4f}%",
        "base_total_fp": str(total_fp),
        "equivalent_fp": str(total_fp * r),
        "equivalent_unit_price": str(Decimal(base["unit_price"]) * r),
        "dev_cost_raw": str(c_t_raw),
        "dev_cost": c_t,
        "profit": p_t,
        "direct_total": direct,
        "rounding_adjustment": adjust,
        "supply": supply_t,
        "vat": vat_t,
        "total": total_t,
        "vat_method": vat_method,
        "vat_method_text": "공급가액×세율" if vat_method == "rate" else "역산(공급가액 = 목표액÷1.1 끝수 절사, 부가세 = 목표액 − 공급가액)",
        "vat_by_rate": vat_by_rate,
        "vat_residual": vat_t - vat_by_rate,
        "matches_target": (total_t == target_amount) if includes_vat else (supply_t == target_amount),
        "method_text": "단일 조정률 r = (목표 공급가액 − 직접경비) ÷ (1+이윤율) ÷ 기준 개발원가(반올림 전). "
        "기준 FP·분류·가중치는 바꾸지 않고, 환산 FP(기준FP×r)와 환산 단가(단가×r)는 예산 대응 참고값으로만 표시.",
        "warnings": warnings,
    }
