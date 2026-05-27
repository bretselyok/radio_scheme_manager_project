"""Описание сущностей предметной области.

Dataclass-модели используются для документирования структуры данных и для
экспорта отчетов. Хранение выполняется в SQLite, но наличие моделей помогает
объяснить предметную область в ВКР и отделить бизнес-логику от интерфейса.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


@dataclass(slots=True)
class User:
    id: int | None = None
    login: str = ""
    full_name: str = ""
    role: str = "engineer"
    email: str = ""
    phone: str = ""
    department: str = ""
    is_active: int = 1
    created_at: str = ""
    last_login: str = ""

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "User":
        return cls(**{name: row.get(name) for name in cls.field_names() if name in row})

    @staticmethod
    def field_names() -> tuple[str, ...]:
        return tuple(User.__dataclass_fields__.keys())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Project:
    id: int | None = None
    code: str = ""
    title: str = ""
    customer: str = ""
    manager_id: int | None = None
    status: str = "Планирование"
    priority: str = "Средний"
    planned_start: str = ""
    planned_finish: str = ""
    actual_start: str = ""
    actual_finish: str = ""
    description: str = ""
    budget: float = 0.0
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Project":
        return cls(**{name: row.get(name) for name in cls.field_names() if name in row})

    @staticmethod
    def field_names() -> tuple[str, ...]:
        return tuple(Project.__dataclass_fields__.keys())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Stakeholder:
    id: int | None = None
    project_id: int | None = None
    name: str = ""
    role: str = ""
    influence: str = "Среднее"
    contact: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Scheme:
    id: int | None = None
    project_id: int | None = None
    code: str = ""
    title: str = ""
    scheme_type: str = "Принципиальная электрическая схема"
    version: str = "1.0"
    status: str = "Черновик"
    author_id: int | None = None
    file_path: str = ""
    description: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Component:
    id: int | None = None
    part_number: str = ""
    name: str = ""
    category: str = "Прочее"
    nominal: str = ""
    unit: str = ""
    footprint: str = ""
    manufacturer: str = ""
    price: float = 0.0
    stock_qty: int = 0
    reliability_mtbf: float = 0.0
    datasheet_path: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SchemeComponent:
    id: int | None = None
    scheme_id: int | None = None
    component_id: int | None = None
    refdes: str = ""
    quantity: int = 1
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Requirement:
    id: int | None = None
    project_id: int | None = None
    code: str = ""
    title: str = ""
    description: str = ""
    category: str = "Функциональное"
    priority: str = "Средний"
    status: str = "Собрано"
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Task:
    id: int | None = None
    project_id: int | None = None
    title: str = ""
    description: str = ""
    assigned_to: int | None = None
    status: str = "Новая"
    priority: str = "Средний"
    start_date: str = ""
    due_date: str = ""
    progress: int = 0
    parent_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TestCase:
    id: int | None = None
    scheme_id: int | None = None
    requirement_id: int | None = None
    name: str = ""
    method: str = ""
    expected_result: str = ""
    actual_result: str = ""
    status: str = "Не запускался"
    tester_id: int | None = None
    executed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Risk:
    id: int | None = None
    project_id: int | None = None
    title: str = ""
    probability: int = 1
    impact: int = 1
    status: str = "Выявлен"
    response_plan: str = ""

    @property
    def score(self) -> int:
        return int(self.probability) * int(self.impact)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["score"] = self.score
        return data


@dataclass(slots=True)
class Document:
    id: int | None = None
    project_id: int | None = None
    scheme_id: int | None = None
    title: str = ""
    doc_type: str = ""
    file_path: str = ""
    version: str = "1.0"
    uploaded_by: int | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ChangeRequest:
    id: int | None = None
    project_id: int | None = None
    scheme_id: int | None = None
    title: str = ""
    description: str = ""
    status: str = "Новая"
    requested_by: int | None = None
    decision: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EconomicInput:
    id: int | None = None
    project_id: int | None = None
    hourly_rate: float = 850.0
    dev_hours: float = 240.0
    implementation_hours: float = 60.0
    equipment_cost: float = 50000.0
    software_cost: float = 0.0
    indirect_rate: float = 0.20
    operation_cost_year: float = 120000.0
    effect_saving_year: float = 420000.0
    discount_rate: float = 0.12
    lifetime_years: int = 3

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DashboardStats:
    projects_total: int = 0
    projects_active: int = 0
    schemes_total: int = 0
    tasks_total: int = 0
    tasks_overdue: int = 0
    tests_failed: int = 0
    risks_high: int = 0
    total_budget: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
