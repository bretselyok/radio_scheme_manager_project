"""Расчетные функции для проекта.

Модуль используется в экономической части ВКР и в отчетах системы. Формулы
сделаны простыми и прозрачными, чтобы их можно было перенести в текст работы:
капитальные затраты, эксплуатационные затраты, экономический эффект, NPV, ROI,
срок окупаемости, риск-скор и ориентировочная стоимость перечня элементов.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from math import isfinite
from typing import Any, Iterable, Mapping


@dataclass(slots=True)
class EconomicResult:
    development_salary: float
    implementation_salary: float
    payroll_total: float
    social_charges: float
    indirect_costs: float
    capital_costs: float
    annual_operation_cost: float
    annual_effect: float
    annual_net_cashflow: float
    npv: float
    roi_percent: float
    payback_years: float | None
    discounted_payback_years: float | None
    profitability_index: float
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        if isfinite(result):
            return result
    except (TypeError, ValueError):
        pass
    return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def calculate_economic_effect(data: Mapping[str, Any]) -> EconomicResult:
    """Выполняет расчет эффективности внедрения АИС.

    Параметры ожидаются в рублях и человеко-часах. Расчет можно показать в
    разделе ВКР, где обосновывается экономическая целесообразность разработки.
    """
    hourly_rate = safe_float(data.get("hourly_rate"), 850.0)
    dev_hours = safe_float(data.get("dev_hours"), 240.0)
    implementation_hours = safe_float(data.get("implementation_hours"), 60.0)
    equipment_cost = safe_float(data.get("equipment_cost"), 0.0)
    software_cost = safe_float(data.get("software_cost"), 0.0)
    indirect_rate = safe_float(data.get("indirect_rate"), 0.2)
    operation_cost_year = safe_float(data.get("operation_cost_year"), 0.0)
    effect_saving_year = safe_float(data.get("effect_saving_year"), 0.0)
    discount_rate = safe_float(data.get("discount_rate"), 0.12)
    lifetime_years = max(1, safe_int(data.get("lifetime_years"), 3))
    social_rate = safe_float(data.get("social_rate"), 0.30)

    development_salary = hourly_rate * dev_hours
    implementation_salary = hourly_rate * implementation_hours
    payroll_total = development_salary + implementation_salary
    social_charges = payroll_total * social_rate
    indirect_costs = payroll_total * indirect_rate
    capital_costs = payroll_total + social_charges + indirect_costs + equipment_cost + software_cost
    annual_operation_cost = operation_cost_year
    annual_effect = effect_saving_year
    annual_net_cashflow = annual_effect - annual_operation_cost
    npv = -capital_costs
    discounted_accumulated = -capital_costs
    discounted_payback_years: float | None = None
    for year in range(1, lifetime_years + 1):
        discounted = annual_net_cashflow / ((1 + discount_rate) ** year)
        npv += discounted
        previous = discounted_accumulated
        discounted_accumulated += discounted
        if discounted_payback_years is None and discounted_accumulated >= 0:
            fraction = 0.0 if discounted == 0 else abs(previous) / discounted
            discounted_payback_years = (year - 1) + fraction
    roi_percent = ((annual_net_cashflow * lifetime_years - capital_costs) / capital_costs * 100) if capital_costs else 0.0
    payback_years = capital_costs / annual_net_cashflow if annual_net_cashflow > 0 else None
    discounted_inflows = npv + capital_costs
    profitability_index = discounted_inflows / capital_costs if capital_costs else 0.0
    if npv > 0 and annual_net_cashflow > 0:
        recommendation = "Проект экономически целесообразен: ожидаемый дисконтированный эффект превышает вложения."
    elif annual_net_cashflow > 0:
        recommendation = "Проект дает положительный годовой эффект, но требует уточнения срока окупаемости и ставки дисконтирования."
    else:
        recommendation = "Проект требует пересмотра затрат или источников эффекта, так как чистый денежный поток не положителен."
    return EconomicResult(
        development_salary=round(development_salary, 2),
        implementation_salary=round(implementation_salary, 2),
        payroll_total=round(payroll_total, 2),
        social_charges=round(social_charges, 2),
        indirect_costs=round(indirect_costs, 2),
        capital_costs=round(capital_costs, 2),
        annual_operation_cost=round(annual_operation_cost, 2),
        annual_effect=round(annual_effect, 2),
        annual_net_cashflow=round(annual_net_cashflow, 2),
        npv=round(npv, 2),
        roi_percent=round(roi_percent, 2),
        payback_years=round(payback_years, 2) if payback_years is not None else None,
        discounted_payback_years=round(discounted_payback_years, 2) if discounted_payback_years is not None else None,
        profitability_index=round(profitability_index, 3),
        recommendation=recommendation,
    )


def calculate_bom_cost(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    total_quantity = 0
    total_cost = 0.0
    positions = 0
    lacking: list[str] = []
    for row in rows:
        positions += 1
        quantity = max(0, safe_int(row.get("quantity"), 0))
        price = safe_float(row.get("price"), 0.0)
        stock = safe_int(row.get("stock_qty"), 0)
        total_quantity += quantity
        total_cost += quantity * price
        if stock < quantity:
            label = str(row.get("part_number") or row.get("component_name") or row.get("component_id"))
            lacking.append(label)
    return {
        "positions": positions,
        "total_quantity": total_quantity,
        "total_cost": round(total_cost, 2),
        "lacking_components": lacking,
        "has_stock_problems": bool(lacking),
    }


def calculate_task_progress(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows_list = list(rows)
    if not rows_list:
        return {"average_progress": 0, "done": 0, "in_work": 0, "overdue": 0, "total": 0}
    total = len(rows_list)
    progress_values = [safe_int(row.get("progress"), 0) for row in rows_list]
    done = sum(1 for row in rows_list if row.get("status") == "Выполнена")
    in_work = sum(1 for row in rows_list if row.get("status") == "В работе")
    overdue = sum(1 for row in rows_list if row.get("is_overdue") in (1, True, "1"))
    return {
        "average_progress": round(sum(progress_values) / total, 1),
        "done": done,
        "in_work": in_work,
        "overdue": overdue,
        "total": total,
    }


def calculate_requirement_coverage(requirements: Iterable[Mapping[str, Any]], tests: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    requirements_list = list(requirements)
    tests_list = list(tests)
    requirement_ids = {row.get("id") for row in requirements_list}
    covered_ids = {row.get("requirement_id") for row in tests_list if row.get("requirement_id")}
    covered = len(requirement_ids & covered_ids)
    total = len(requirement_ids)
    passed = sum(1 for row in tests_list if row.get("status") == "Пройден")
    failed = sum(1 for row in tests_list if row.get("status") == "Не пройден")
    percent = round((covered / total) * 100, 1) if total else 0.0
    return {
        "requirements_total": total,
        "covered": covered,
        "coverage_percent": percent,
        "tests_total": len(tests_list),
        "tests_passed": passed,
        "tests_failed": failed,
    }


def calculate_risk_score(probability: Any, impact: Any) -> int:
    p = max(1, min(5, safe_int(probability, 1)))
    i = max(1, min(5, safe_int(impact, 1)))
    return p * i


def risk_level(score: int) -> str:
    if score >= 16:
        return "Критический"
    if score >= 10:
        return "Высокий"
    if score >= 5:
        return "Средний"
    return "Низкий"


def calculate_quality_index(requirement_coverage: Mapping[str, Any], risk_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    coverage = safe_float(requirement_coverage.get("coverage_percent"), 0.0)
    passed = safe_float(requirement_coverage.get("tests_passed"), 0.0)
    tests_total = safe_float(requirement_coverage.get("tests_total"), 0.0)
    pass_rate = (passed / tests_total * 100) if tests_total else 0.0
    risks = list(risk_rows)
    high_risk_count = sum(1 for row in risks if calculate_risk_score(row.get("probability"), row.get("impact")) >= 12)
    risk_penalty = min(30.0, high_risk_count * 7.5)
    quality_index = max(0.0, min(100.0, coverage * 0.45 + pass_rate * 0.45 + (100 - risk_penalty) * 0.10))
    return {
        "coverage_percent": round(coverage, 1),
        "pass_rate": round(pass_rate, 1),
        "high_risk_count": high_risk_count,
        "quality_index": round(quality_index, 1),
    }


def make_project_recommendations(stats: Mapping[str, Any]) -> list[str]:
    recommendations: list[str] = []
    if safe_int(stats.get("tasks_overdue"), 0) > 0:
        recommendations.append("Есть просроченные задачи: требуется актуализировать календарный план и перераспределить ресурсы.")
    if safe_int(stats.get("tests_failed"), 0) > 0:
        recommendations.append("Есть непройденные испытания: необходимо провести анализ причин и оформить корректирующие действия.")
    if safe_int(stats.get("risks_high"), 0) > 0:
        recommendations.append("Выявлены существенные риски: следует уточнить план реагирования и назначить ответственных.")
    if not recommendations:
        recommendations.append("Критических отклонений не обнаружено, проект может выполняться по утвержденному плану.")
    return recommendations
