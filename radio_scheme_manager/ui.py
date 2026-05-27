"""Графический интерфейс пользователя.

Интерфейс реализован на Tkinter, поэтому проект не требует установки сторонних
библиотек. В окнах реализованы основные функции, которые требуются для ВКР:
10+ форм, роли пользователей, админ-панель, личный кабинет, справка,
управление проектами, схемами, компонентами, испытаниями и отчетами.
"""
from __future__ import annotations

import os
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Iterable, Mapping

from .api_client import ApiClient, ApiClientError
from .schematic_ui import SchemeDesignerFrame
from .services import get_permission
from .app_config import (
    ALL_ROLES,
    COMPONENT_CATEGORIES,
    PRIORITIES,
    PROJECT_STATUSES,
    REPORT_TYPES,
    RISK_STATUSES,
    SCHEME_STATUSES,
    SCHEME_TYPES,
    TASK_STATUSES,
    TEST_STATUSES,
    REQUIREMENT_STATUSES,
)


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    kind: str = "entry"
    choices: tuple[str, ...] = ()
    required: bool = False
    readonly: bool = False
    width: int = 36


@dataclass(frozen=True)
class ViewSpec:
    table: str
    title: str
    columns: tuple[tuple[str, str, int], ...]
    fields: tuple[FieldSpec, ...]
    help_text: str = ""
    readonly: bool = False


VIEW_SPECS: dict[str, ViewSpec] = {
    "projects": ViewSpec(
        table="projects",
        title="Проекты разработки радиоэлектронных схем",
        columns=(
            ("id", "ID", 55),
            ("code", "Код", 120),
            ("title", "Наименование", 300),
            ("customer", "Заказчик", 220),
            ("status", "Статус", 120),
            ("priority", "Приоритет", 100),
            ("planned_finish", "План. окончание", 120),
            ("average_progress", "Средний прогресс", 130),
        ),
        fields=(
            FieldSpec("code", "Код проекта", required=True),
            FieldSpec("title", "Наименование", required=True, width=50),
            FieldSpec("customer", "Заказчик", width=50),
            FieldSpec("manager_id", "ID руководителя", kind="int"),
            FieldSpec("status", "Статус", kind="choice", choices=PROJECT_STATUSES),
            FieldSpec("priority", "Приоритет", kind="choice", choices=PRIORITIES),
            FieldSpec("planned_start", "Плановое начало", kind="date"),
            FieldSpec("planned_finish", "Плановое окончание", kind="date"),
            FieldSpec("actual_start", "Фактическое начало", kind="date"),
            FieldSpec("actual_finish", "Фактическое окончание", kind="date"),
            FieldSpec("budget", "Бюджет, руб.", kind="float"),
            FieldSpec("description", "Описание", kind="text", width=56),
        ),
        help_text="Карточка проекта фиксирует цель автоматизации, заказчика, сроки, бюджет и статус.",
    ),
    "stakeholders": ViewSpec(
        table="stakeholders",
        title="Стейкхолдеры проекта",
        columns=(
            ("id", "ID", 55),
            ("project_id", "Проект", 75),
            ("name", "Имя/группа", 220),
            ("role", "Роль", 180),
            ("influence", "Влияние", 100),
            ("contact", "Контакт", 180),
        ),
        fields=(
            FieldSpec("project_id", "ID проекта", kind="int", required=True),
            FieldSpec("name", "Имя/группа", required=True),
            FieldSpec("role", "Роль"),
            FieldSpec("influence", "Влияние", kind="choice", choices=("Низкое", "Среднее", "Высокое")),
            FieldSpec("contact", "Контакт"),
            FieldSpec("note", "Примечание", kind="text"),
        ),
        help_text="Форма помогает показать в ВКР анализ заинтересованных сторон проекта.",
    ),
    "schemes": ViewSpec(
        table="schemes",
        title="Радиоэлектронные схемы",
        columns=(
            ("id", "ID", 55),
            ("project_code", "Проект", 110),
            ("code", "Код схемы", 130),
            ("title", "Наименование", 280),
            ("scheme_type", "Тип", 220),
            ("version", "Версия", 80),
            ("status", "Статус", 150),
            ("bom_cost", "Стоимость BOM", 120),
        ),
        fields=(
            FieldSpec("project_id", "ID проекта", kind="int", required=True),
            FieldSpec("code", "Код схемы", required=True),
            FieldSpec("title", "Наименование", required=True, width=50),
            FieldSpec("scheme_type", "Тип схемы", kind="choice", choices=SCHEME_TYPES),
            FieldSpec("version", "Версия"),
            FieldSpec("status", "Статус", kind="choice", choices=SCHEME_STATUSES),
            FieldSpec("author_id", "ID автора", kind="int"),
            FieldSpec("file_path", "Файл схемы", kind="file", width=50),
            FieldSpec("description", "Описание", kind="text", width=56),
        ),
        help_text="Карточка схемы хранит версию, статус согласования и путь к файлу проекта.",
    ),
    "components": ViewSpec(
        table="components",
        title="Элементная база",
        columns=(
            ("id", "ID", 55),
            ("part_number", "Артикул", 150),
            ("name", "Наименование", 260),
            ("category", "Категория", 140),
            ("nominal", "Номинал", 100),
            ("footprint", "Корпус", 100),
            ("price", "Цена", 80),
            ("stock_qty", "Остаток", 90),
        ),
        fields=(
            FieldSpec("part_number", "Артикул", required=True),
            FieldSpec("name", "Наименование", required=True, width=50),
            FieldSpec("category", "Категория", kind="choice", choices=COMPONENT_CATEGORIES),
            FieldSpec("nominal", "Номинал"),
            FieldSpec("unit", "Единица измерения"),
            FieldSpec("footprint", "Корпус"),
            FieldSpec("manufacturer", "Производитель"),
            FieldSpec("price", "Цена", kind="float"),
            FieldSpec("stock_qty", "Остаток", kind="int"),
            FieldSpec("reliability_mtbf", "Наработка на отказ, ч", kind="float"),
            FieldSpec("datasheet_path", "Datasheet", kind="file", width=50),
        ),
        help_text="Справочник компонентов снижает ошибки ручного выбора элементной базы.",
    ),
    "scheme_components": ViewSpec(
        table="scheme_components",
        title="Перечень элементов схемы / BOM",
        columns=(
            ("id", "ID", 55),
            ("scheme_code", "Схема", 130),
            ("refdes", "Поз. обозн.", 110),
            ("part_number", "Артикул", 150),
            ("component_name", "Компонент", 240),
            ("quantity", "Кол-во", 80),
            ("price", "Цена", 80),
            ("total_price", "Сумма", 90),
        ),
        fields=(
            FieldSpec("scheme_id", "ID схемы", kind="int", required=True),
            FieldSpec("component_id", "ID компонента", kind="int", required=True),
            FieldSpec("refdes", "Позиционное обозначение"),
            FieldSpec("quantity", "Количество", kind="int"),
            FieldSpec("note", "Примечание", kind="text"),
        ),
        help_text="BOM связывает схемы с элементной базой и используется для расчета стоимости.",
    ),
    "requirements": ViewSpec(
        table="requirements",
        title="Требования к системе и схемам",
        columns=(
            ("id", "ID", 55),
            ("project_code", "Проект", 110),
            ("code", "Код", 100),
            ("title", "Требование", 300),
            ("category", "Категория", 140),
            ("priority", "Приоритет", 100),
            ("status", "Статус", 130),
            ("tests_count", "Тесты", 70),
        ),
        fields=(
            FieldSpec("project_id", "ID проекта", kind="int", required=True),
            FieldSpec("code", "Код требования", required=True),
            FieldSpec("title", "Наименование", required=True, width=50),
            FieldSpec("description", "Описание", kind="text", width=56),
            FieldSpec("category", "Категория", kind="choice", choices=("Функциональное", "Нефункциональное", "Безопасность", "Интерфейс", "Отчетность")),
            FieldSpec("priority", "Приоритет", kind="choice", choices=PRIORITIES),
            FieldSpec("status", "Статус", kind="choice", choices=REQUIREMENT_STATUSES),
            FieldSpec("source", "Источник"),
        ),
        help_text="Форма обеспечивает трассируемость требований, что удобно для описания по IEEE 830/29148.",
    ),
    "tasks": ViewSpec(
        table="tasks",
        title="План работ и контроль исполнения",
        columns=(
            ("id", "ID", 55),
            ("project_code", "Проект", 110),
            ("title", "Задача", 300),
            ("assigned_name", "Исполнитель", 180),
            ("status", "Статус", 120),
            ("priority", "Приоритет", 100),
            ("due_date", "Срок", 100),
            ("progress", "Прогресс", 90),
            ("is_overdue", "Проср.", 70),
        ),
        fields=(
            FieldSpec("project_id", "ID проекта", kind="int", required=True),
            FieldSpec("title", "Задача", required=True, width=50),
            FieldSpec("description", "Описание", kind="text", width=56),
            FieldSpec("assigned_to", "ID исполнителя", kind="int"),
            FieldSpec("status", "Статус", kind="choice", choices=TASK_STATUSES),
            FieldSpec("priority", "Приоритет", kind="choice", choices=PRIORITIES),
            FieldSpec("start_date", "Дата начала", kind="date"),
            FieldSpec("due_date", "Срок", kind="date"),
            FieldSpec("progress", "Прогресс 0-100", kind="int"),
            FieldSpec("parent_id", "ID родительской задачи", kind="int"),
        ),
        help_text="Задачи используются для календарного планирования и мониторинга проекта.",
    ),
    "tests": ViewSpec(
        table="tests",
        title="Испытания и контроль качества",
        columns=(
            ("id", "ID", 55),
            ("scheme_code", "Схема", 130),
            ("requirement_code", "Требование", 120),
            ("name", "Проверка", 260),
            ("status", "Статус", 120),
            ("tester_name", "Тестировщик", 170),
            ("executed_at", "Дата", 150),
        ),
        fields=(
            FieldSpec("scheme_id", "ID схемы", kind="int", required=True),
            FieldSpec("requirement_id", "ID требования", kind="int"),
            FieldSpec("name", "Название проверки", required=True, width=50),
            FieldSpec("method", "Методика", kind="text", width=56),
            FieldSpec("expected_result", "Ожидаемый результат", kind="text", width=56),
            FieldSpec("actual_result", "Фактический результат", kind="text", width=56),
            FieldSpec("status", "Статус", kind="choice", choices=TEST_STATUSES),
            FieldSpec("tester_id", "ID тестировщика", kind="int"),
            FieldSpec("executed_at", "Дата выполнения"),
        ),
        help_text="Тест-кейсы доказывают проверяемость требований и качество разработанной схемы.",
    ),
    "risks": ViewSpec(
        table="risks",
        title="Риски проекта",
        columns=(
            ("id", "ID", 55),
            ("project_code", "Проект", 110),
            ("title", "Риск", 320),
            ("probability", "Вероятн.", 90),
            ("impact", "Влияние", 80),
            ("score", "Оценка", 80),
            ("status", "Статус", 120),
        ),
        fields=(
            FieldSpec("project_id", "ID проекта", kind="int", required=True),
            FieldSpec("title", "Риск", required=True, width=50),
            FieldSpec("probability", "Вероятность 1-5", kind="int"),
            FieldSpec("impact", "Влияние 1-5", kind="int"),
            FieldSpec("status", "Статус", kind="choice", choices=RISK_STATUSES),
            FieldSpec("response_plan", "План реагирования", kind="text", width=56),
        ),
        help_text="Матрица рисков нужна для описания мониторинга и контроля проекта.",
    ),
    "documents": ViewSpec(
        table="documents",
        title="Документы и файлы проекта",
        columns=(
            ("id", "ID", 55),
            ("project_code", "Проект", 110),
            ("scheme_code", "Схема", 130),
            ("title", "Документ", 260),
            ("doc_type", "Тип", 100),
            ("version", "Версия", 80),
            ("file_path", "Файл", 260),
            ("created_at", "Дата", 150),
        ),
        fields=(
            FieldSpec("project_id", "ID проекта", kind="int"),
            FieldSpec("scheme_id", "ID схемы", kind="int"),
            FieldSpec("title", "Название", required=True, width=50),
            FieldSpec("doc_type", "Тип документа"),
            FieldSpec("file_path", "Путь к файлу", kind="file", width=50),
            FieldSpec("version", "Версия"),
            FieldSpec("uploaded_by", "ID загрузившего", kind="int"),
        ),
        help_text="Форма демонстрирует доступ к файловой системе и централизованное хранение документов.",
    ),
    "change_requests": ViewSpec(
        table="change_requests",
        title="Заявки на изменения",
        columns=(
            ("id", "ID", 55),
            ("project_code", "Проект", 110),
            ("scheme_code", "Схема", 130),
            ("title", "Заявка", 280),
            ("status", "Статус", 130),
            ("requester_name", "Инициатор", 170),
            ("created_at", "Дата", 150),
        ),
        fields=(
            FieldSpec("project_id", "ID проекта", kind="int", required=True),
            FieldSpec("scheme_id", "ID схемы", kind="int"),
            FieldSpec("title", "Название", required=True, width=50),
            FieldSpec("description", "Описание", kind="text", width=56),
            FieldSpec("status", "Статус", kind="choice", choices=("Новая", "На рассмотрении", "Согласована", "Отклонена", "Выполнена")),
            FieldSpec("requested_by", "ID инициатора", kind="int"),
            FieldSpec("decision", "Решение", kind="text", width=56),
        ),
        help_text="Заявки на изменения показывают управление конфигурацией и версиями схем.",
    ),
    "users": ViewSpec(
        table="users",
        title="Панель администратора: пользователи и роли",
        columns=(
            ("id", "ID", 55),
            ("login", "Логин", 140),
            ("full_name", "ФИО", 240),
            ("role", "Роль", 120),
            ("email", "Email", 180),
            ("department", "Подразделение", 220),
            ("is_active", "Активен", 80),
        ),
        fields=(
            FieldSpec("login", "Логин", required=True),
            FieldSpec("password", "Пароль", kind="password"),
            FieldSpec("full_name", "ФИО", required=True, width=50),
            FieldSpec("role", "Роль", kind="choice", choices=ALL_ROLES),
            FieldSpec("email", "Email"),
            FieldSpec("phone", "Телефон"),
            FieldSpec("department", "Подразделение", width=50),
            FieldSpec("is_active", "Активен 1/0", kind="int"),
        ),
        help_text="Администратор создает учетные записи и назначает роли доступа.",
    ),
    "audit_log": ViewSpec(
        table="audit_log",
        title="Журнал действий пользователей",
        columns=(
            ("id", "ID", 55),
            ("user_id", "Пользователь", 110),
            ("action", "Действие", 140),
            ("entity", "Сущность", 150),
            ("entity_id", "ID записи", 90),
            ("details", "Детали", 400),
            ("created_at", "Дата", 150),
        ),
        fields=(),
        help_text="Журнал аудита фиксирует входы, создание, изменение и удаление записей.",
        readonly=True,
    ),
    "economic_inputs": ViewSpec(
        table="economic_inputs",
        title="Экономические параметры проекта",
        columns=(
            ("id", "ID", 55),
            ("project_id", "Проект", 80),
            ("hourly_rate", "Ставка", 100),
            ("dev_hours", "Разработка, ч", 120),
            ("implementation_hours", "Внедрение, ч", 120),
            ("equipment_cost", "Оборудование", 120),
            ("operation_cost_year", "Эксплуатация/год", 130),
            ("effect_saving_year", "Эффект/год", 120),
            ("lifetime_years", "Период", 80),
        ),
        fields=(
            FieldSpec("project_id", "ID проекта", kind="int", required=True),
            FieldSpec("hourly_rate", "Ставка специалиста, руб/ч", kind="float"),
            FieldSpec("dev_hours", "Трудоемкость разработки, ч", kind="float"),
            FieldSpec("implementation_hours", "Трудоемкость внедрения, ч", kind="float"),
            FieldSpec("equipment_cost", "Оборудование, руб", kind="float"),
            FieldSpec("software_cost", "ПО, руб", kind="float"),
            FieldSpec("indirect_rate", "Косвенные расходы, доля", kind="float"),
            FieldSpec("operation_cost_year", "Эксплуатационные затраты в год", kind="float"),
            FieldSpec("effect_saving_year", "Экономический эффект в год", kind="float"),
            FieldSpec("discount_rate", "Ставка дисконтирования", kind="float"),
            FieldSpec("lifetime_years", "Срок полезного использования, лет", kind="int"),
        ),
        help_text="На основе этих данных система рассчитывает TCO, NPV, ROI и срок окупаемости.",
    ),
}


class BusyCursor:
    def __init__(self, widget: tk.Widget) -> None:
        self.widget = widget
        self.old_cursor = widget.cget("cursor")

    def __enter__(self) -> None:
        self.widget.configure(cursor="watch")
        self.widget.update_idletasks()

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.widget.configure(cursor=self.old_cursor)
        self.widget.update_idletasks()


class RecordDialog(tk.Toplevel):
    def __init__(self, master: tk.Widget, title: str, fields: Iterable[FieldSpec], initial: Mapping[str, Any] | None = None) -> None:
        super().__init__(master)
        self.title(title)
        self.resizable(True, True)
        self.result: dict[str, Any] | None = None
        self.fields = list(fields)
        self.initial = dict(initial or {})
        self.widgets: dict[str, tk.Widget] = {}
        self.transient(master)
        self.grab_set()
        self._build()
        self.bind("<Return>", lambda _event: self._on_save())
        self.bind("<Escape>", lambda _event: self._on_cancel())
        self.update_idletasks()
        self.geometry(f"{max(520, self.winfo_reqwidth())}x{min(720, max(360, self.winfo_reqheight()))}")

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        for row, field in enumerate(self.fields):
            label = field.label + (" *" if field.required else "")
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="nw", padx=(0, 8), pady=4)
            value = self.initial.get(field.name, "")
            widget = self._make_widget(frame, field, value)
            widget.grid(row=row, column=1, sticky="ew", pady=4)
            frame.grid_columnconfigure(1, weight=1)
            self.widgets[field.name] = widget
        buttons = ttk.Frame(frame)
        buttons.grid(row=len(self.fields), column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Сохранить", command=self._on_save).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="Отмена", command=self._on_cancel).pack(side=tk.LEFT, padx=4)

    def _make_widget(self, master: tk.Widget, field: FieldSpec, value: Any) -> tk.Widget:
        if field.kind == "choice":
            widget = ttk.Combobox(master, values=field.choices, width=field.width)
            widget.set(str(value or (field.choices[0] if field.choices else "")))
            if field.readonly:
                widget.configure(state="disabled")
            return widget
        if field.kind == "text":
            text = tk.Text(master, height=5, width=field.width, wrap="word")
            text.insert("1.0", str(value or ""))
            return text
        if field.kind == "file":
            outer = ttk.Frame(master)
            entry = ttk.Entry(outer, width=field.width)
            entry.insert(0, str(value or ""))
            if field.readonly:
                entry.configure(state="disabled")
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            browse_button = ttk.Button(outer, text="Обзор", command=lambda: self._choose_file(entry))
            browse_button.pack(side=tk.LEFT, padx=(4, 0))
            if field.readonly:
                browse_button.configure(state="disabled")
            return outer
        show = "*" if field.kind == "password" else ""
        entry = ttk.Entry(master, width=field.width, show=show)
        entry.insert(0, str(value or ""))
        if field.readonly:
            entry.configure(state="disabled")
        return entry

    def _choose_file(self, entry: ttk.Entry) -> None:
        path = filedialog.askopenfilename(title="Выберите файл")
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)

    def _extract_value(self, field: FieldSpec, widget: tk.Widget) -> Any:
        if field.kind == "text" and isinstance(widget, tk.Text):
            return widget.get("1.0", tk.END).strip()
        if field.kind == "file" and isinstance(widget, ttk.Frame):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Entry):
                    return child.get().strip()
            return ""
        if isinstance(widget, ttk.Combobox):
            return widget.get().strip()
        if isinstance(widget, ttk.Entry):
            value = widget.get().strip()
            if field.kind == "int":
                return int(value) if value else None
            if field.kind == "float":
                return float(value.replace(",", ".")) if value else None
            return value
        return ""

    def _on_save(self) -> None:
        try:
            data: dict[str, Any] = {}
            for field in self.fields:
                value = self._extract_value(field, self.widgets[field.name])
                if field.required and (value is None or str(value).strip() == ""):
                    raise ValueError(f"Поле '{field.label}' обязательно для заполнения")
                if value not in (None, ""):
                    data[field.name] = value
            self.result = data
            self.destroy()
        except ValueError as exc:
            messagebox.showerror("Ошибка ввода", str(exc), parent=self)

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()


class LoginFrame(ttk.Frame):
    def __init__(self, app: "ApplicationWindow") -> None:
        super().__init__(app, padding=24)
        self.app = app
        self.login_var = tk.StringVar(value="admin")
        self.password_var = tk.StringVar(value="admin123")
        self._build()

    def _build(self) -> None:
        card = ttk.Frame(self, padding=24)
        card.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        title = ttk.Label(card, text="АС управления разработкой радиоэлектронных схем", font=("Segoe UI", 14, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=(0, 16))
        ttk.Label(card, text="Логин").grid(row=1, column=0, sticky="e", padx=8, pady=4)
        ttk.Entry(card, textvariable=self.login_var, width=28).grid(row=1, column=1, pady=4)
        ttk.Label(card, text="Пароль").grid(row=2, column=0, sticky="e", padx=8, pady=4)
        ttk.Entry(card, textvariable=self.password_var, width=28, show="*").grid(row=2, column=1, pady=4)
        ttk.Button(card, text="Войти", command=self._login).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 4))
        hint = "Тестовые пользователи: admin/admin123, manager/manager123, engineer/engineer123, controller/control123"
        ttk.Label(card, text=hint, wraplength=420, justify=tk.CENTER).grid(row=4, column=0, columnspan=2, pady=(8, 0))

    def _login(self) -> None:
        try:
            with BusyCursor(self.app):
                self.app.client.login(self.login_var.get(), self.password_var.get())
            self.app.show_workspace()
        except ApiClientError as exc:
            messagebox.showerror("Ошибка входа", str(exc), parent=self)


class DashboardFrame(ttk.Frame):
    def __init__(self, app: "ApplicationWindow") -> None:
        super().__init__(app.content, padding=12)
        self.app = app
        self.labels: dict[str, ttk.Label] = {}
        self.tree = ttk.Treeview(self, columns=("name", "value"), show="headings", height=8)
        self._build()
        self.refresh()

    def _build(self) -> None:
        ttk.Label(self, text="Панель управления проектом", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))
        grid = ttk.Frame(self)
        grid.pack(fill=tk.X)
        metrics = [
            ("projects_total", "Всего проектов"),
            ("projects_active", "Активных проектов"),
            ("schemes_total", "Схем"),
            ("tasks_total", "Задач"),
            ("tasks_overdue", "Просрочено"),
            ("tests_failed", "Не пройдено тестов"),
            ("risks_high", "Высоких рисков"),
            ("total_budget", "Бюджет, руб."),
        ]
        for index, (key, text) in enumerate(metrics):
            card = ttk.LabelFrame(grid, text=text, padding=10)
            card.grid(row=index // 4, column=index % 4, sticky="ew", padx=4, pady=4)
            label = ttk.Label(card, text="0", font=("Segoe UI", 14, "bold"))
            label.pack(anchor="center")
            self.labels[key] = label
            grid.grid_columnconfigure(index % 4, weight=1)
        lower = ttk.Frame(self)
        lower.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        left = ttk.LabelFrame(lower, text="Срезы состояния", padding=8)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        self.tree.heading("name", text="Показатель")
        self.tree.heading("value", text="Значение")
        self.tree.column("name", width=260)
        self.tree.column("value", width=140)
        self.tree.pack(fill=tk.BOTH, expand=True)
        right = ttk.LabelFrame(lower, text="Рекомендации", padding=8)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        self.recommendations = tk.Text(right, height=12, wrap="word")
        self.recommendations.pack(fill=tk.BOTH, expand=True)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(toolbar, text="Обновить", command=self.refresh).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Сводный отчет", command=self.export_summary).pack(side=tk.LEFT, padx=6)

    def refresh(self) -> None:
        try:
            stats = self.app.client.dashboard()
            for key, label in self.labels.items():
                label.configure(text=str(stats.get(key, 0)))
            self.tree.delete(*self.tree.get_children())
            details = stats.get("details", {})
            for group_name, rows in details.items():
                self.tree.insert("", tk.END, values=(group_name, ""))
                for row in rows:
                    text = row.get("status") or row.get("title") or row.get("name") or "Показатель"
                    value = row.get("count") or row.get("score") or ""
                    self.tree.insert("", tk.END, values=("  " + str(text), value))
            self.recommendations.delete("1.0", tk.END)
            recs = []
            if stats.get("tasks_overdue", 0):
                recs.append("- Есть просроченные задачи: актуализируйте календарный план.")
            if stats.get("tests_failed", 0):
                recs.append("- Есть непройденные испытания: оформите корректирующие действия.")
            if stats.get("risks_high", 0):
                recs.append("- Есть высокие риски: назначьте ответственных за план реагирования.")
            if not recs:
                recs.append("- Критических отклонений не обнаружено.")
            self.recommendations.insert("1.0", "\n".join(recs))
        except ApiClientError as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)

    def export_summary(self) -> None:
        try:
            result = self.app.client.export_report("manager_summary")
            messagebox.showinfo("Отчет сформирован", result.get("path", ""), parent=self)
        except ApiClientError as exc:
            messagebox.showerror("Ошибка экспорта", str(exc), parent=self)


class GenericListFrame(ttk.Frame):
    def __init__(self, app: "ApplicationWindow", spec: ViewSpec) -> None:
        super().__init__(app.content, padding=12)
        self.app = app
        self.spec = spec
        self.rows: list[dict[str, Any]] = []
        self.search_var = tk.StringVar()
        self._build()
        self.refresh()

    def _build(self) -> None:
        title = ttk.Label(self, text=self.spec.title, font=("Segoe UI", 14, "bold"))
        title.pack(anchor="w")
        if self.spec.help_text:
            ttk.Label(self, text=self.spec.help_text, wraplength=900).pack(anchor="w", pady=(2, 8))
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(toolbar, text="Обновить", command=self.refresh).pack(side=tk.LEFT)
        role = str((self.app.client.current_user or {}).get("role", ""))
        permission = get_permission(role, self.spec.table)
        if not self.spec.readonly:
            add_button = ttk.Button(toolbar, text="Добавить", command=self.add_record)
            add_button.pack(side=tk.LEFT, padx=4)
            edit_button = ttk.Button(toolbar, text="Изменить", command=self.edit_record)
            edit_button.pack(side=tk.LEFT, padx=4)
            delete_button = ttk.Button(toolbar, text="Удалить", command=self.delete_record)
            delete_button.pack(side=tk.LEFT, padx=4)
            if not permission.can_create:
                add_button.configure(state="disabled")
            if not permission.can_update:
                edit_button.configure(state="disabled")
            if not permission.can_delete:
                delete_button.configure(state="disabled")
        ttk.Label(toolbar, text="Поиск на форме:").pack(side=tk.LEFT, padx=(16, 4))
        ttk.Entry(toolbar, textvariable=self.search_var, width=28).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Найти", command=self.apply_filter).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="Сброс", command=self.reset_filter).pack(side=tk.LEFT)
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(container, columns=[name for name, _title, _width in self.spec.columns], show="headings")
        for name, title, width in self.spec.columns:
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width, anchor="w")
        y_scroll = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.tree.yview)
        x_scroll = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", lambda _event: self.edit_record())
        status = ttk.Frame(self)
        status.pack(fill=tk.X, pady=(6, 0))
        self.count_label = ttk.Label(status, text="")
        self.count_label.pack(side=tk.LEFT)
        if self.spec.table in {"scheme_components", "tests", "projects", "economic_inputs"}:
            report_permission_table = "projects" if self.spec.table in {"projects", "economic_inputs"} else self.spec.table
            report_button = ttk.Button(status, text="Сформировать отчет", command=self.quick_report)
            report_button.pack(side=tk.RIGHT)
            if not get_permission(role, report_permission_table).can_export:
                report_button.configure(state="disabled")

    def refresh(self) -> None:
        try:
            with BusyCursor(self.app):
                self.rows = self.app.client.list_records(self.spec.table)
            self._fill_tree(self.rows)
        except ApiClientError as exc:
            messagebox.showerror("Ошибка загрузки", str(exc), parent=self)

    def _fill_tree(self, rows: list[dict[str, Any]]) -> None:
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            values = [row.get(name, "") for name, _title, _width in self.spec.columns]
            self.tree.insert("", tk.END, values=values)
        self.count_label.configure(text=f"Записей: {len(rows)}")

    def apply_filter(self) -> None:
        term = self.search_var.get().lower().strip()
        if not term:
            self._fill_tree(self.rows)
            return
        filtered = []
        for row in self.rows:
            if any(term in str(value).lower() for value in row.values()):
                filtered.append(row)
        self._fill_tree(filtered)

    def reset_filter(self) -> None:
        self.search_var.set("")
        self._fill_tree(self.rows)

    def selected_record_id(self) -> int | None:
        item = self.tree.focus()
        if not item:
            return None
        values = self.tree.item(item, "values")
        if not values:
            return None
        try:
            return int(values[0])
        except (TypeError, ValueError):
            return None

    def add_record(self) -> None:
        if not self.app.can(self.spec.table, "create"):
            messagebox.showwarning("Доступ ограничен", "Текущая роль не позволяет добавлять записи в этом разделе.", parent=self)
            return
        dialog = RecordDialog(self, f"Добавить: {self.spec.title}", self.spec.fields)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        try:
            self.app.client.create_record(self.spec.table, dialog.result)
            self.refresh()
        except ApiClientError as exc:
            messagebox.showerror("Ошибка сохранения", str(exc), parent=self)

    def edit_record(self) -> None:
        record_id = self.selected_record_id()
        if record_id is None or self.spec.readonly:
            return
        if not self.app.can(self.spec.table, "update"):
            messagebox.showwarning("Доступ ограничен", "Текущая роль не позволяет изменять записи в этом разделе.", parent=self)
            return
        try:
            record = self.app.client.get_record(self.spec.table, record_id)
        except ApiClientError as exc:
            messagebox.showerror("Ошибка загрузки", str(exc), parent=self)
            return
        dialog = RecordDialog(self, f"Изменить: {self.spec.title}", self.spec.fields, record)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        try:
            self.app.client.update_record(self.spec.table, record_id, dialog.result)
            self.refresh()
        except ApiClientError as exc:
            messagebox.showerror("Ошибка сохранения", str(exc), parent=self)

    def delete_record(self) -> None:
        record_id = self.selected_record_id()
        if record_id is None:
            return
        if not self.app.can(self.spec.table, "delete"):
            messagebox.showwarning("Доступ ограничен", "Текущая роль не позволяет удалять записи в этом разделе.", parent=self)
            return
        if not messagebox.askyesno("Удаление", "Удалить выбранную запись?", parent=self):
            return
        try:
            self.app.client.delete_record(self.spec.table, record_id)
            self.refresh()
        except ApiClientError as exc:
            messagebox.showerror("Ошибка удаления", str(exc), parent=self)

    def quick_report(self) -> None:
        try:
            if self.spec.table == "projects":
                record_id = self.selected_record_id() or 1
                result = self.app.client.export_report("project_passport", project_id=record_id)
            elif self.spec.table == "economic_inputs":
                record_id = self.selected_record_id() or 1
                row = next((item for item in self.rows if item.get("id") == record_id), None)
                project_id = row.get("project_id") if row else 1
                result = self.app.client.export_report("economic", project_id=project_id)
            elif self.spec.table == "scheme_components":
                record_id = self.selected_record_id() or 1
                row = next((item for item in self.rows if item.get("id") == record_id), None)
                scheme_id = row.get("scheme_id") if row else 1
                result = self.app.client.export_report("bom", scheme_id=scheme_id)
            elif self.spec.table == "tests":
                record_id = self.selected_record_id() or 1
                row = next((item for item in self.rows if item.get("id") == record_id), None)
                scheme_id = row.get("scheme_id") if row else 1
                result = self.app.client.export_report("tests", scheme_id=scheme_id)
            else:
                result = self.app.client.export_report("manager_summary")
            messagebox.showinfo("Отчет сформирован", result.get("path", ""), parent=self)
        except ApiClientError as exc:
            messagebox.showerror("Ошибка экспорта", str(exc), parent=self)


class ProfileFrame(ttk.Frame):
    def __init__(self, app: "ApplicationWindow") -> None:
        super().__init__(app.content, padding=12)
        self.app = app
        self._build()

    def _build(self) -> None:
        user = self.app.client.current_user or {}
        ttk.Label(self, text="Личный кабинет пользователя", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))
        fields = [
            ("ФИО", user.get("full_name", "")),
            ("Логин", user.get("login", "")),
            ("Роль", user.get("role", "")),
            ("Email", user.get("email", "")),
            ("Телефон", user.get("phone", "")),
            ("Подразделение", user.get("department", "")),
            ("Последний вход", user.get("last_login", "")),
        ]
        table = ttk.Frame(self)
        table.pack(anchor="nw", fill=tk.X)
        for row, (label, value) in enumerate(fields):
            ttk.Label(table, text=label + ":", width=20).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Label(table, text=str(value)).grid(row=row, column=1, sticky="w", pady=3)
        ttk.Label(
            self,
            text="Личный кабинет нужен для выполнения требования о пользовательском профиле и ролевом доступе.",
            wraplength=820,
        ).pack(anchor="w", pady=(16, 0))


class SettingsFrame(ttk.Frame):
    def __init__(self, app: "ApplicationWindow") -> None:
        super().__init__(app.content, padding=12)
        self.app = app
        self.rows: list[dict[str, Any]] = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        ttk.Label(self, text="Настройки системы", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(self, text="Панель содержит более пяти пунктов настройки: организация, методологии, экспорт, резервное копирование, пороги качества.").pack(anchor="w", pady=(2, 8))
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(toolbar, text="Обновить", command=self.refresh).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Изменить", command=self.edit_setting).pack(side=tk.LEFT, padx=4)
        self.tree = ttk.Treeview(self, columns=("key", "value", "updated_at"), show="headings")
        for name, title, width in (("key", "Ключ", 240), ("value", "Значение", 480), ("updated_at", "Обновлено", 160)):
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", lambda _event: self.edit_setting())

    def refresh(self) -> None:
        try:
            self.rows = self.app.client.list_records("settings")
            self.tree.delete(*self.tree.get_children())
            for row in self.rows:
                self.tree.insert("", tk.END, values=(row.get("key"), row.get("value"), row.get("updated_at")))
        except ApiClientError as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)

    def edit_setting(self) -> None:
        if not self.app.can("settings", "update"):
            messagebox.showwarning("Доступ ограничен", "Настройки может изменять только администратор.", parent=self)
            return
        item = self.tree.focus()
        if not item:
            return
        key, value, _updated = self.tree.item(item, "values")
        dialog = RecordDialog(self, "Изменить настройку", (FieldSpec("key", "Ключ", readonly=True), FieldSpec("value", "Значение", kind="text", width=60)), {"key": key, "value": value})
        self.wait_window(dialog)
        if dialog.result is None:
            return
        try:
            self.app.client.update_record("settings", 0, dialog.result)
            self.refresh()
        except ApiClientError as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)


class ReportsFrame(ttk.Frame):
    def __init__(self, app: "ApplicationWindow") -> None:
        super().__init__(app.content, padding=12)
        self.app = app
        self.report_var = tk.StringVar(value="project_passport")
        self.project_id_var = tk.StringVar(value="1")
        self.scheme_id_var = tk.StringVar(value="1")
        self.output_var = tk.StringVar(value="")
        self._build()

    def _build(self) -> None:
        ttk.Label(self, text="Формирование отчетов", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))
        ttk.Label(self, text="Приложение формирует DOCX и XLSX без сторонних библиотек. Отчеты сохраняются в папке exports.").pack(anchor="w", pady=(0, 10))
        form = ttk.Frame(self)
        form.pack(anchor="nw")
        report_choices = (
            ("Паспорт проекта", "project_passport"),
            ("Перечень элементов XLSX", "bom"),
            ("Отчет по испытаниям", "tests"),
            ("Экономическая эффективность", "economic"),
            ("Сводка руководителя", "manager_summary"),
        )
        self.report_map = dict(report_choices)
        ttk.Label(form, text="Тип отчета").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        combo = ttk.Combobox(form, values=[name for name, _code in report_choices], width=36)
        combo.set("Паспорт проекта")
        combo.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        combo.bind("<<ComboboxSelected>>", lambda _event: self.report_var.set(self.report_map.get(combo.get(), "project_passport")))
        ttk.Label(form, text="ID проекта").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(form, textvariable=self.project_id_var, width=12).grid(row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(form, text="ID схемы").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(form, textvariable=self.scheme_id_var, width=12).grid(row=2, column=1, sticky="w", padx=4, pady=4)
        ttk.Button(form, text="Сформировать", command=self.export).grid(row=3, column=0, columnspan=2, sticky="ew", padx=4, pady=(12, 4))
        ttk.Label(self, textvariable=self.output_var, wraplength=900).pack(anchor="w", pady=(12, 0))

    def export(self) -> None:
        try:
            report_type = self.report_var.get()
            payload = {
                "project_id": int(self.project_id_var.get() or 1),
                "scheme_id": int(self.scheme_id_var.get() or 1),
            }
            result = self.app.client.export_report(report_type, **payload)
            self.output_var.set("Сформирован файл: " + result.get("path", ""))
            messagebox.showinfo("Отчет", result.get("path", ""), parent=self)
        except (ValueError, ApiClientError) as exc:
            messagebox.showerror("Ошибка экспорта", str(exc), parent=self)


class EconomicsFrame(ttk.Frame):
    def __init__(self, app: "ApplicationWindow") -> None:
        super().__init__(app.content, padding=12)
        self.app = app
        self.project_id_var = tk.StringVar(value="1")
        self.text = tk.Text(self, wrap="word", height=18)
        self._build()

    def _build(self) -> None:
        ttk.Label(self, text="Расчет экономической эффективности", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 8))
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X)
        ttk.Label(toolbar, text="ID проекта:").pack(side=tk.LEFT)
        ttk.Entry(toolbar, textvariable=self.project_id_var, width=10).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="Рассчитать", command=self.calculate).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="DOCX-отчет", command=self.export).pack(side=tk.LEFT, padx=4)
        self.text.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.calculate()

    def calculate(self) -> None:
        try:
            project_id = int(self.project_id_var.get() or 1)
            data = self.app.client.economics(project_id)
            result = data["result"]
            self.text.delete("1.0", tk.END)
            lines = ["Результаты расчета:"]
            labels = {
                "development_salary": "Оплата труда разработки",
                "implementation_salary": "Оплата труда внедрения",
                "payroll_total": "ФОТ",
                "social_charges": "Начисления на ФОТ",
                "indirect_costs": "Косвенные расходы",
                "capital_costs": "Капитальные затраты",
                "annual_operation_cost": "Эксплуатационные затраты/год",
                "annual_effect": "Экономический эффект/год",
                "annual_net_cashflow": "Чистый денежный поток/год",
                "npv": "NPV",
                "roi_percent": "ROI, %",
                "payback_years": "Срок окупаемости, лет",
                "discounted_payback_years": "Дисконтированный срок окупаемости, лет",
                "profitability_index": "Индекс прибыльности",
                "recommendation": "Вывод",
            }
            for key, label in labels.items():
                lines.append(f"{label}: {result.get(key)}")
            self.text.insert("1.0", "\n".join(lines))
        except (ValueError, ApiClientError) as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)

    def export(self) -> None:
        try:
            project_id = int(self.project_id_var.get() or 1)
            result = self.app.client.export_report("economic", project_id=project_id)
            messagebox.showinfo("Отчет", result.get("path", ""), parent=self)
        except (ValueError, ApiClientError) as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)


class HelpFrame(ttk.Frame):
    def __init__(self, app: "ApplicationWindow") -> None:
        super().__init__(app.content, padding=12)
        self.app = app
        self._build()

    def _build(self) -> None:
        ttk.Label(self, text="Справка по системе", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))
        text = tk.Text(self, wrap="word")
        text.pack(fill=tk.BOTH, expand=True)
        content = """
Назначение системы

Автоматизированная система предназначена для управления разработкой радиоэлектронных схем. Она поддерживает проектный подход: хранит проекты, схемы, элементную базу, перечни элементов, требования, задачи, испытания, риски, документы и заявки на изменения.

Основные формы

1. Панель управления - сводные показатели проекта.
2. Проекты - паспорт автоматизации и контроль статуса.
3. Стейкхолдеры - участники и заинтересованные стороны.
4. Схемы - карточки радиоэлектронных схем и версии.
5. Элементная база - справочник компонентов.
6. BOM - перечень элементов схемы.
7. Требования - функциональные и нефункциональные требования.
8. Задачи - план работ, исполнители и прогресс.
9. Испытания - проверка требований и качества.
10. Риски - матрица вероятности и влияния.
11. Документы - доступ к файловой системе и документация проекта.
12. Заявки на изменения - управление изменениями и версиями.
13. Пользователи - роли и учетные записи.
14. Настройки - методология, экспорт, резервное копирование и пороги качества.
15. Отчеты - DOCX/XLSX документы для ВКР и демонстрации.

Роли пользователей

admin/admin123 - полный доступ и панель администратора.
manager/manager123 - управление проектом, задачами, рисками, требованиями и отчетами.
engineer/engineer123 - работа со схемами, визуальным редактором, элементной базой, BOM и документами.
controller/control123 - контроль качества, испытания, риски, документы и просмотр схем.

В разделе «Схемотехника -> Редактор схем» можно собрать принципиальную схему из условных обозначений, соединить элементы проводниками, сохранить компоновку в базе данных и экспортировать ее в SVG.

Как использовать в ВКР

В главе 1 можно описать проблему: разрозненное хранение схем, отсутствие единого подхода к версиям и элементной базе. В главе 2 - показать модель TO BE, архитектуру клиент-серверной системы, структуру БД и роли. В главе 3 - привести экранные формы, тестирование, расчет экономической эффективности и сформированные отчеты.
"""
        text.insert("1.0", content.strip())
        text.configure(state="disabled")


class SearchFrame(ttk.Frame):
    def __init__(self, app: "ApplicationWindow") -> None:
        super().__init__(app.content, padding=12)
        self.app = app
        self.term_var = tk.StringVar()
        self.tree = ttk.Treeview(self, columns=("group", "id", "code", "title"), show="headings")
        self._build()

    def _build(self) -> None:
        ttk.Label(self, text="Глобальный поиск", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 8))
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Entry(toolbar, textvariable=self.term_var, width=40).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Найти", command=self.search).pack(side=tk.LEFT, padx=4)
        for name, title, width in (("group", "Раздел", 140), ("id", "ID", 60), ("code", "Код/артикул", 150), ("title", "Наименование/описание", 500)):
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width)
        self.tree.pack(fill=tk.BOTH, expand=True)

    def search(self) -> None:
        try:
            result = self.app.client.get("/api/search", {"term": self.term_var.get()})
            self.tree.delete(*self.tree.get_children())
            for group, rows in result.items():
                for row in rows:
                    code = row.get("code") or row.get("part_number") or ""
                    title = row.get("title") or row.get("name") or row.get("description") or ""
                    self.tree.insert("", tk.END, values=(group, row.get("id"), code, title))
        except ApiClientError as exc:
            messagebox.showerror("Ошибка поиска", str(exc), parent=self)


class ApplicationWindow(tk.Tk):
    def __init__(self, client: ApiClient | None = None) -> None:
        super().__init__()
        self.client = client or ApiClient()
        self.title("АС разработки радиоэлектронных схем")
        self.geometry("1220x760")
        self.minsize(980, 620)
        self.content: ttk.Frame | None = None
        self.current_frame: tk.Widget | None = None
        self.status_var = tk.StringVar(value="Не выполнен вход")
        self._build_base()
        self.show_login()

    def _build_base(self) -> None:
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def show_login(self) -> None:
        self._clear_all()
        self.status_var.set("Не выполнен вход")
        frame = LoginFrame(self)
        frame.pack(fill=tk.BOTH, expand=True)
        self.current_frame = frame

    def show_workspace(self) -> None:
        self._clear_all()
        self._build_menu()
        self.content = ttk.Frame(self)
        self.content.pack(fill=tk.BOTH, expand=True)
        user = self.client.current_user or {}
        self.status_var.set(f"Пользователь: {user.get('full_name')} | Роль: {user.get('role')}")
        self.show_dashboard()

    def _clear_all(self) -> None:
        self.config(menu=tk.Menu(self))
        for child in self.winfo_children():
            if child is not self.status_bar:
                child.destroy()
        self.content = None
        self.current_frame = None

    def can(self, table: str, action: str = "read") -> bool:
        user = self.client.current_user or {}
        role = str(user.get("role", ""))
        return get_permission(role, table).allows(action)

    def _add_menu_command_if_allowed(self, menu: tk.Menu, label: str, table: str, command: Callable[[], None], action: str = "read") -> None:
        if self.can(table, action):
            menu.add_command(label=label, command=command)

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        project_menu = tk.Menu(menu, tearoff=0)
        project_menu.add_command(label="Панель управления", command=self.show_dashboard)
        self._add_menu_command_if_allowed(project_menu, "Проекты", "projects", lambda: self.show_view("projects"))
        self._add_menu_command_if_allowed(project_menu, "Стейкхолдеры", "stakeholders", lambda: self.show_view("stakeholders"))
        self._add_menu_command_if_allowed(project_menu, "Требования", "requirements", lambda: self.show_view("requirements"))
        self._add_menu_command_if_allowed(project_menu, "Задачи", "tasks", lambda: self.show_view("tasks"))
        self._add_menu_command_if_allowed(project_menu, "Риски", "risks", lambda: self.show_view("risks"))
        menu.add_cascade(label="Проект", menu=project_menu)

        scheme_menu = tk.Menu(menu, tearoff=0)
        self._add_menu_command_if_allowed(scheme_menu, "Схемы", "schemes", lambda: self.show_view("schemes"))
        self._add_menu_command_if_allowed(scheme_menu, "Редактор схем", "scheme_nodes", self.show_scheme_designer)
        self._add_menu_command_if_allowed(scheme_menu, "Элементная база", "components", lambda: self.show_view("components"))
        self._add_menu_command_if_allowed(scheme_menu, "BOM / перечень элементов", "scheme_components", lambda: self.show_view("scheme_components"))
        self._add_menu_command_if_allowed(scheme_menu, "Испытания", "tests", lambda: self.show_view("tests"))
        self._add_menu_command_if_allowed(scheme_menu, "Документы", "documents", lambda: self.show_view("documents"))
        self._add_menu_command_if_allowed(scheme_menu, "Заявки на изменения", "change_requests", lambda: self.show_view("change_requests"))
        menu.add_cascade(label="Схемотехника", menu=scheme_menu)

        manage_menu = tk.Menu(menu, tearoff=0)
        manage_menu.add_command(label="Личный кабинет", command=self.show_profile)
        self._add_menu_command_if_allowed(manage_menu, "Пользователи и роли", "users", lambda: self.show_view("users"))
        self._add_menu_command_if_allowed(manage_menu, "Настройки", "settings", self.show_settings)
        self._add_menu_command_if_allowed(manage_menu, "Журнал действий", "audit_log", lambda: self.show_view("audit_log"))
        menu.add_cascade(label="Управление", menu=manage_menu)

        report_menu = tk.Menu(menu, tearoff=0)
        if self.can("economic_inputs", "read"):
            report_menu.add_command(label="Экономическая эффективность", command=self.show_economics)
        if self.can("projects", "export"):
            report_menu.add_command(label="Отчеты DOCX/XLSX", command=self.show_reports)
        self._add_menu_command_if_allowed(report_menu, "Экономические параметры", "economic_inputs", lambda: self.show_view("economic_inputs"))
        menu.add_cascade(label="Отчеты", menu=report_menu)

        help_menu = tk.Menu(menu, tearoff=0)
        help_menu.add_command(label="Глобальный поиск", command=self.show_search)
        help_menu.add_command(label="Справка по системе", command=self.show_help)
        help_menu.add_separator()
        help_menu.add_command(label="Выйти из учетной записи", command=self.logout)
        menu.add_cascade(label="Справка", menu=help_menu)
        self.config(menu=menu)

    def _set_frame(self, frame: tk.Widget) -> None:
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.current_frame = frame
        frame.pack(fill=tk.BOTH, expand=True)

    def show_dashboard(self) -> None:
        self._ensure_content()
        self._set_frame(DashboardFrame(self))

    def show_view(self, name: str) -> None:
        self._ensure_content()
        self._set_frame(GenericListFrame(self, VIEW_SPECS[name]))

    def show_scheme_designer(self) -> None:
        self._ensure_content()
        self._set_frame(SchemeDesignerFrame(self))

    def show_profile(self) -> None:
        self._ensure_content()
        self._set_frame(ProfileFrame(self))

    def show_settings(self) -> None:
        self._ensure_content()
        self._set_frame(SettingsFrame(self))

    def show_reports(self) -> None:
        self._ensure_content()
        self._set_frame(ReportsFrame(self))

    def show_economics(self) -> None:
        self._ensure_content()
        self._set_frame(EconomicsFrame(self))

    def show_help(self) -> None:
        self._ensure_content()
        self._set_frame(HelpFrame(self))

    def show_search(self) -> None:
        self._ensure_content()
        self._set_frame(SearchFrame(self))

    def _ensure_content(self) -> None:
        if self.content is None:
            self.content = ttk.Frame(self)
            self.content.pack(fill=tk.BOTH, expand=True)

    def logout(self) -> None:
        try:
            self.client.logout()
        except ApiClientError:
            pass
        self.show_login()

    def on_close(self) -> None:
        try:
            self.client.logout()
        except Exception:
            pass
        self.destroy()


def run_client(client: ApiClient | None = None) -> None:
    app = ApplicationWindow(client)
    app.mainloop()
