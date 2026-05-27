"""Бизнес-логика приложения.

Здесь сосредоточены правила доступа, валидации и предметные операции. Такой
слой нужен, чтобы в ВКР можно было показать разделение архитектуры на: клиент,
сервер/API, сервисы, базу данных и модуль отчетности.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .app_config import ROLE_ADMIN, ROLE_CONTROLLER, ROLE_ENGINEER, ROLE_MANAGER
from .calculations import calculate_bom_cost, calculate_economic_effect, calculate_risk_score, risk_level
from .database import DatabaseManager, TABLE_COLUMNS
from .exporters import ReportBuilder
from .schematics import export_schematic_svg, normalize_node, normalize_wire


@dataclass(slots=True)
class Permission:
    can_read: bool = False
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False
    can_export: bool = False

    def allows(self, action: str) -> bool:
        return {
            "read": self.can_read,
            "create": self.can_create,
            "update": self.can_update,
            "delete": self.can_delete,
            "export": self.can_export,
        }.get(action, False)


ROLE_PERMISSIONS: dict[str, dict[str, Permission]] = {
    ROLE_ADMIN: {
        "*": Permission(True, True, True, True, True),
    },
    ROLE_MANAGER: {
        "projects": Permission(True, True, True, False, True),
        "stakeholders": Permission(True, True, True, True, True),
        "requirements": Permission(True, True, True, False, True),
        "tasks": Permission(True, True, True, True, True),
        "risks": Permission(True, True, True, True, True),
        "change_requests": Permission(True, True, True, False, True),
        "economic_inputs": Permission(True, True, True, False, True),
        "schemes": Permission(True, False, True, False, True),
        "documents": Permission(True, True, True, False, True),
        "components": Permission(True, False, False, False, True),
        "scheme_components": Permission(True, False, False, False, True),
        "scheme_nodes": Permission(True, False, False, False, True),
        "scheme_wires": Permission(True, False, False, False, True),
        "tests": Permission(True, False, False, False, True),
        "users": Permission(True, False, False, False, False),
        "audit_log": Permission(True, False, False, False, False),
        "settings": Permission(True, False, False, False, False),
    },
    ROLE_ENGINEER: {
        "projects": Permission(True, False, False, False, False),
        "stakeholders": Permission(True, False, False, False, False),
        "requirements": Permission(True, False, False, False, False),
        "tasks": Permission(True, False, True, False, False),
        "schemes": Permission(True, True, True, False, True),
        "components": Permission(True, True, True, False, True),
        "scheme_components": Permission(True, True, True, True, True),
        "scheme_nodes": Permission(True, True, True, True, True),
        "scheme_wires": Permission(True, True, True, True, True),
        "documents": Permission(True, True, True, False, True),
        "change_requests": Permission(True, True, True, False, False),
        "tests": Permission(True, False, False, False, False),
        "risks": Permission(True, False, False, False, False),
        "economic_inputs": Permission(True, False, False, False, False),
    },
    ROLE_CONTROLLER: {
        "projects": Permission(True, False, False, False, False),
        "stakeholders": Permission(True, False, False, False, False),
        "requirements": Permission(True, False, True, False, False),
        "tasks": Permission(True, False, True, False, False),
        "schemes": Permission(True, False, True, False, True),
        "components": Permission(True, False, False, False, True),
        "scheme_components": Permission(True, False, False, False, True),
        "scheme_nodes": Permission(True, False, False, False, True),
        "scheme_wires": Permission(True, False, False, False, True),
        "tests": Permission(True, True, True, True, True),
        "documents": Permission(True, True, True, False, True),
        "change_requests": Permission(True, True, True, False, False),
        "risks": Permission(True, True, True, False, False),
        "economic_inputs": Permission(True, False, False, False, False),
    },
}

EXTENDED_LISTS = {
    "projects": "list_projects_extended",
    "schemes": "list_schemes_extended",
    "scheme_components": "list_bom_extended",
    "tasks": "list_tasks_extended",
    "requirements": "list_requirements_extended",
    "tests": "list_tests_extended",
    "risks": "list_risks_extended",
    "documents": "list_documents_extended",
    "change_requests": "list_change_requests_extended",
}


class AccessDenied(Exception):
    pass


class ValidationError(Exception):
    pass


def get_permission(role: str, table: str) -> Permission:
    role_map = ROLE_PERMISSIONS.get(role, {})
    return role_map.get(table) or role_map.get("*") or Permission()


def require_permission(user: Mapping[str, Any], table: str, action: str) -> None:
    role = str(user.get("role", ""))
    permission = get_permission(role, table)
    if not permission.allows(action):
        raise AccessDenied(f"Роль '{role}' не имеет права выполнить действие '{action}' для '{table}'")


class ApplicationService:
    """Фасад серверной части приложения."""

    def __init__(self, db: DatabaseManager | None = None, reports: ReportBuilder | None = None) -> None:
        self.db = db or DatabaseManager()
        self.reports = reports or ReportBuilder()

    def initialize(self) -> None:
        self.db.init_schema()

    def login(self, login: str, password: str) -> dict[str, Any]:
        result = self.db.authenticate(login, password)
        if not result:
            raise AccessDenied("Неверный логин или пароль")
        return result

    def get_user(self, token: str | None) -> dict[str, Any]:
        user = self.db.get_user_by_token(token)
        if not user:
            raise AccessDenied("Сессия не найдена или истекла")
        return user

    def logout(self, token: str | None) -> dict[str, str]:
        if token:
            self.db.logout(token)
        return {"message": "Выход выполнен"}

    def dashboard(self, user: Mapping[str, Any]) -> dict[str, Any]:
        return self.db.get_dashboard_stats()

    def list_records(self, user: Mapping[str, Any], table: str, filters: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        self._validate_table(table)
        require_permission(user, table, "read")
        if table in EXTENDED_LISTS and not filters:
            method = getattr(self.db, EXTENDED_LISTS[table])
            rows = method()
        elif table == "settings":
            rows = self.db.query_all("SELECT key, value, updated_at FROM settings ORDER BY key")
        else:
            rows = self.db.list_records(table, filters=filters)
        if table == "users":
            for row in rows:
                row.pop("password_hash", None)
        return rows

    def get_record(self, user: Mapping[str, Any], table: str, record_id: int) -> dict[str, Any]:
        self._validate_table(table)
        require_permission(user, table, "read")
        record = self.db.get_record(table, record_id)
        if not record:
            raise ValidationError("Запись не найдена")
        if table == "users":
            record.pop("password_hash", None)
        return record

    def create_record(self, user: Mapping[str, Any], table: str, data: Mapping[str, Any]) -> dict[str, Any]:
        self._validate_table(table)
        require_permission(user, table, "create")
        prepared = self.validate_payload(table, data)
        if table == "users":
            record_id = self.db.create_user(prepared, user_id=int(user["id"]))
        elif table == "settings":
            self.set_setting(user, str(prepared["key"]), str(prepared.get("value", "")))
            record_id = 0
        else:
            record_id = self.db.create_record(table, prepared, user_id=int(user["id"]))
        return {"id": record_id, "message": "Запись создана"}

    def update_record(self, user: Mapping[str, Any], table: str, record_id: int, data: Mapping[str, Any]) -> dict[str, Any]:
        self._validate_table(table)
        require_permission(user, table, "update")
        prepared = self.validate_payload(table, data, update=True)
        if table == "settings":
            self.set_setting(user, str(data.get("key", record_id)), str(data.get("value", "")))
        elif table == "users" and "password" in prepared:
            new_password = str(prepared.pop("password"))
            self.db.change_password(record_id, new_password, changed_by=int(user["id"]))
            if prepared:
                self.db.update_record(table, record_id, prepared, user_id=int(user["id"]))
        else:
            self.db.update_record(table, record_id, prepared, user_id=int(user["id"]))
        return {"id": record_id, "message": "Запись обновлена"}

    def delete_record(self, user: Mapping[str, Any], table: str, record_id: int) -> dict[str, Any]:
        self._validate_table(table)
        require_permission(user, table, "delete")
        self.db.delete_record(table, record_id, user_id=int(user["id"]))
        return {"id": record_id, "message": "Запись удалена"}

    def set_setting(self, user: Mapping[str, Any], key: str, value: str) -> dict[str, str]:
        require_permission(user, "settings", "update")
        if not key.strip():
            raise ValidationError("Ключ настройки не может быть пустым")
        from .database import now

        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, value, now()),
            )
            self.db.log_action(conn, int(user["id"]), "set_setting", "settings", None, f"{key}={value}")
        return {"message": "Настройка сохранена"}

    def search(self, user: Mapping[str, Any], term: str) -> dict[str, Any]:
        if not term.strip():
            raise ValidationError("Введите строку поиска")
        return self.db.search(term.strip())

    def economics(self, user: Mapping[str, Any], project_id: int) -> dict[str, Any]:
        require_permission(user, "economic_inputs", "read")
        data = self.db.query_one("SELECT * FROM economic_inputs WHERE project_id=?", (project_id,))
        if not data:
            raise ValidationError("Для проекта не заполнены экономические показатели")
        result = calculate_economic_effect(data)
        return {"input": data, "result": result.to_dict()}

    def bom_summary(self, user: Mapping[str, Any], scheme_id: int) -> dict[str, Any]:
        require_permission(user, "scheme_components", "read")
        rows = self.db.list_bom_extended(scheme_id)
        return calculate_bom_cost(rows)

    def risk_matrix(self, user: Mapping[str, Any], project_id: int) -> dict[str, Any]:
        require_permission(user, "risks", "read")
        rows = self.db.query_all("SELECT * FROM risks WHERE project_id=? ORDER BY probability*impact DESC", (project_id,))
        matrix: dict[str, list[dict[str, Any]]] = {"Низкий": [], "Средний": [], "Высокий": [], "Критический": []}
        for row in rows:
            score = calculate_risk_score(row.get("probability"), row.get("impact"))
            enriched = dict(row)
            enriched["score"] = score
            enriched["level"] = risk_level(score)
            matrix[enriched["level"]].append(enriched)
        return {"project_id": project_id, "matrix": matrix, "items": rows}

    def get_schematic(self, user: Mapping[str, Any], scheme_id: int) -> dict[str, Any]:
        require_permission(user, "schemes", "read")
        require_permission(user, "scheme_nodes", "read")
        require_permission(user, "scheme_wires", "read")
        return self.db.get_schematic_data(scheme_id)

    def save_schematic(self, user: Mapping[str, Any], scheme_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
        require_permission(user, "schemes", "update")
        require_permission(user, "scheme_nodes", "update")
        require_permission(user, "scheme_wires", "update")
        raw_nodes = payload.get("nodes") or []
        raw_wires = payload.get("wires") or []
        if not isinstance(raw_nodes, list) or not isinstance(raw_wires, list):
            raise ValidationError("Схема должна содержать списки nodes и wires")
        nodes = [normalize_node(item) for item in raw_nodes if isinstance(item, Mapping)]
        wires = [normalize_wire(item) for item in raw_wires if isinstance(item, Mapping)]
        result = self.db.save_schematic_data(scheme_id, nodes, wires, user_id=int(user["id"]))
        return {"message": "Схема сохранена", **result}

    def export_schematic(self, user: Mapping[str, Any], scheme_id: int) -> dict[str, Any]:
        require_permission(user, "schemes", "read")
        require_permission(user, "scheme_nodes", "export")
        require_permission(user, "scheme_wires", "export")
        data = self.db.get_schematic_data(scheme_id)
        path = export_schematic_svg(data["scheme"], data["nodes"], data["wires"], self.reports.export_dir)
        return {"path": str(path), "message": "SVG-схема сформирована"}

    def export_report(self, user: Mapping[str, Any], report_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        require_permission(user, "projects", "export")
        project_id = int(payload.get("project_id") or 1)
        path = None
        if report_type == "project_passport":
            data = self.db.get_project_report_data(project_id)
            path = self.reports.project_passport(data)
        elif report_type == "economic":
            data = self.db.get_project_report_data(project_id)
            path = self.reports.economic_report(data)
        elif report_type == "manager_summary":
            path = self.reports.manager_summary(self.db.get_dashboard_stats())
        elif report_type == "bom":
            require_permission(user, "scheme_components", "export")
            scheme_id = int(payload.get("scheme_id") or 1)
            scheme = self.db.get_record("schemes", scheme_id)
            if not scheme:
                raise ValidationError("Схема не найдена")
            rows = self.db.list_bom_extended(scheme_id)
            path = self.reports.bom_report(scheme, rows)
        elif report_type == "tests":
            require_permission(user, "tests", "export")
            scheme_id = int(payload.get("scheme_id") or 1)
            scheme = self.db.get_record("schemes", scheme_id)
            if not scheme:
                raise ValidationError("Схема не найдена")
            tests = [row for row in self.db.list_tests_extended() if row.get("scheme_id") == scheme_id]
            path = self.reports.tests_report(scheme, tests)
        else:
            raise ValidationError("Неизвестный тип отчета")
        return {"path": str(path), "message": "Отчет сформирован"}

    def validate_payload(self, table: str, data: Mapping[str, Any], update: bool = False) -> dict[str, Any]:
        prepared = dict(data)
        if table == "projects":
            self._require(prepared, "code", "Код проекта", update)
            self._require(prepared, "title", "Наименование проекта", update)
        elif table == "schemes":
            self._require(prepared, "project_id", "Проект", update)
            self._require(prepared, "code", "Код схемы", update)
            self._require(prepared, "title", "Наименование схемы", update)
        elif table == "components":
            self._require(prepared, "part_number", "Артикул", update)
            self._require(prepared, "name", "Наименование компонента", update)
        elif table == "scheme_components":
            self._require(prepared, "scheme_id", "Схема", update)
            self._require(prepared, "component_id", "Компонент", update)
        elif table == "scheme_nodes":
            self._require(prepared, "scheme_id", "Схема", update)
            self._require(prepared, "node_key", "Ключ элемента схемы", update)
            self._require(prepared, "symbol_type", "Тип условного обозначения", update)
        elif table == "scheme_wires":
            self._require(prepared, "scheme_id", "Схема", update)
            self._require(prepared, "wire_key", "Ключ проводника", update)
        elif table == "requirements":
            self._require(prepared, "project_id", "Проект", update)
            self._require(prepared, "code", "Код требования", update)
            self._require(prepared, "title", "Наименование требования", update)
        elif table == "tasks":
            self._require(prepared, "project_id", "Проект", update)
            self._require(prepared, "title", "Название задачи", update)
        elif table == "tests":
            self._require(prepared, "scheme_id", "Схема", update)
            self._require(prepared, "name", "Название проверки", update)
        elif table == "risks":
            self._require(prepared, "project_id", "Проект", update)
            self._require(prepared, "title", "Название риска", update)
        elif table == "documents":
            self._require(prepared, "title", "Название документа", update)
        elif table == "users":
            self._require(prepared, "login", "Логин", update)
            self._require(prepared, "full_name", "ФИО", update)
            self._require(prepared, "role", "Роль", update)
        elif table == "settings":
            self._require(prepared, "key", "Ключ настройки", update)
        return prepared

    def _validate_table(self, table: str) -> None:
        if table != "settings" and table not in TABLE_COLUMNS:
            raise ValidationError(f"Недопустимая таблица: {table}")

    def _require(self, data: Mapping[str, Any], key: str, label: str, update: bool) -> None:
        if update and key not in data:
            return
        value = data.get(key)
        if value is None or str(value).strip() == "":
            raise ValidationError(f"Поле '{label}' обязательно для заполнения")
