"""Слой доступа к данным.

В проекте используется SQLite, потому что база не требует отдельной установки и
удобна для демонстрации в аудитории. При переносе на PostgreSQL достаточно
заменить этот слой и оставить интерфейс API/GUI без существенных изменений.
"""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from .app_config import (
    DB_PATH,
    ROLE_ADMIN,
    ROLE_CONTROLLER,
    ROLE_ENGINEER,
    ROLE_MANAGER,
    ensure_directories,
)


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def hash_password(password: str) -> str:
    """Хеширует пароль с солью.

    Формат хранения: salt$hash. Для учебного проекта достаточно SHA-256, но в
    промышленной системе следует применять PBKDF2, bcrypt или Argon2.
    """
    salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, digest = stored_hash.split("$", 1)
    except ValueError:
        return False
    candidate = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return secrets.compare_digest(candidate, digest)


TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "users": (
        "login",
        "password_hash",
        "full_name",
        "role",
        "email",
        "phone",
        "department",
        "is_active",
        "created_at",
        "last_login",
    ),
    "projects": (
        "code",
        "title",
        "customer",
        "manager_id",
        "status",
        "priority",
        "planned_start",
        "planned_finish",
        "actual_start",
        "actual_finish",
        "description",
        "budget",
        "created_at",
        "updated_at",
    ),
    "stakeholders": (
        "project_id",
        "name",
        "role",
        "influence",
        "contact",
        "note",
    ),
    "schemes": (
        "project_id",
        "code",
        "title",
        "scheme_type",
        "version",
        "status",
        "author_id",
        "file_path",
        "description",
        "created_at",
        "updated_at",
    ),
    "components": (
        "part_number",
        "name",
        "category",
        "nominal",
        "unit",
        "footprint",
        "manufacturer",
        "price",
        "stock_qty",
        "reliability_mtbf",
        "datasheet_path",
        "created_at",
    ),
    "scheme_components": (
        "scheme_id",
        "component_id",
        "refdes",
        "quantity",
        "note",
    ),
    "scheme_nodes": (
        "scheme_id",
        "node_key",
        "component_id",
        "symbol_type",
        "refdes",
        "label",
        "x",
        "y",
        "rotation",
        "created_at",
        "updated_at",
    ),
    "scheme_wires": (
        "scheme_id",
        "wire_key",
        "net_name",
        "x1",
        "y1",
        "x2",
        "y2",
        "created_at",
        "updated_at",
    ),
    "requirements": (
        "project_id",
        "code",
        "title",
        "description",
        "category",
        "priority",
        "status",
        "source",
    ),
    "tasks": (
        "project_id",
        "title",
        "description",
        "assigned_to",
        "status",
        "priority",
        "start_date",
        "due_date",
        "progress",
        "parent_id",
    ),
    "tests": (
        "scheme_id",
        "requirement_id",
        "name",
        "method",
        "expected_result",
        "actual_result",
        "status",
        "tester_id",
        "executed_at",
    ),
    "risks": (
        "project_id",
        "title",
        "probability",
        "impact",
        "status",
        "response_plan",
    ),
    "documents": (
        "project_id",
        "scheme_id",
        "title",
        "doc_type",
        "file_path",
        "version",
        "uploaded_by",
        "created_at",
    ),
    "change_requests": (
        "project_id",
        "scheme_id",
        "title",
        "description",
        "status",
        "requested_by",
        "decision",
        "created_at",
    ),
    "economic_inputs": (
        "project_id",
        "hourly_rate",
        "dev_hours",
        "implementation_hours",
        "equipment_cost",
        "software_cost",
        "indirect_rate",
        "operation_cost_year",
        "effect_saving_year",
        "discount_rate",
        "lifetime_years",
    ),
    "audit_log": (
        "user_id",
        "action",
        "entity",
        "entity_id",
        "details",
        "created_at",
    ),
}

READ_ONLY_TABLES = {"audit_log"}


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


class DatabaseManager:
    """Объект для работы с SQLite и бизнесовыми CRUD-операциями."""

    def __init__(self, db_path: str | Path = DB_PATH) -> None:
        ensure_directories()
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Создает таблицы, индексы и тестовые данные при первом запуске."""
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    login TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    email TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    department TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_login TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    customer TEXT DEFAULT '',
                    manager_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    status TEXT DEFAULT 'Планирование',
                    priority TEXT DEFAULT 'Средний',
                    planned_start TEXT DEFAULT '',
                    planned_finish TEXT DEFAULT '',
                    actual_start TEXT DEFAULT '',
                    actual_finish TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    budget REAL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS stakeholders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    role TEXT DEFAULT '',
                    influence TEXT DEFAULT 'Среднее',
                    contact TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS schemes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    code TEXT NOT NULL,
                    title TEXT NOT NULL,
                    scheme_type TEXT DEFAULT 'Принципиальная электрическая схема',
                    version TEXT DEFAULT '1.0',
                    status TEXT DEFAULT 'Черновик',
                    author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    file_path TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(project_id, code, version)
                );

                CREATE TABLE IF NOT EXISTS components (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    part_number TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    category TEXT DEFAULT 'Прочее',
                    nominal TEXT DEFAULT '',
                    unit TEXT DEFAULT '',
                    footprint TEXT DEFAULT '',
                    manufacturer TEXT DEFAULT '',
                    price REAL DEFAULT 0,
                    stock_qty INTEGER DEFAULT 0,
                    reliability_mtbf REAL DEFAULT 0,
                    datasheet_path TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS scheme_components (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scheme_id INTEGER NOT NULL REFERENCES schemes(id) ON DELETE CASCADE,
                    component_id INTEGER NOT NULL REFERENCES components(id) ON DELETE RESTRICT,
                    refdes TEXT DEFAULT '',
                    quantity INTEGER DEFAULT 1,
                    note TEXT DEFAULT '',
                    UNIQUE(scheme_id, component_id, refdes)
                );

                CREATE TABLE IF NOT EXISTS scheme_nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scheme_id INTEGER NOT NULL REFERENCES schemes(id) ON DELETE CASCADE,
                    node_key TEXT NOT NULL,
                    component_id INTEGER REFERENCES components(id) ON DELETE SET NULL,
                    symbol_type TEXT DEFAULT 'generic',
                    refdes TEXT DEFAULT '',
                    label TEXT DEFAULT '',
                    x REAL DEFAULT 100,
                    y REAL DEFAULT 100,
                    rotation INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(scheme_id, node_key)
                );

                CREATE TABLE IF NOT EXISTS scheme_wires (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scheme_id INTEGER NOT NULL REFERENCES schemes(id) ON DELETE CASCADE,
                    wire_key TEXT NOT NULL,
                    net_name TEXT DEFAULT '',
                    x1 REAL DEFAULT 0,
                    y1 REAL DEFAULT 0,
                    x2 REAL DEFAULT 0,
                    y2 REAL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(scheme_id, wire_key)
                );

                CREATE TABLE IF NOT EXISTS requirements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    code TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    category TEXT DEFAULT 'Функциональное',
                    priority TEXT DEFAULT 'Средний',
                    status TEXT DEFAULT 'Собрано',
                    source TEXT DEFAULT '',
                    UNIQUE(project_id, code)
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    status TEXT DEFAULT 'Новая',
                    priority TEXT DEFAULT 'Средний',
                    start_date TEXT DEFAULT '',
                    due_date TEXT DEFAULT '',
                    progress INTEGER DEFAULT 0,
                    parent_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scheme_id INTEGER NOT NULL REFERENCES schemes(id) ON DELETE CASCADE,
                    requirement_id INTEGER REFERENCES requirements(id) ON DELETE SET NULL,
                    name TEXT NOT NULL,
                    method TEXT DEFAULT '',
                    expected_result TEXT DEFAULT '',
                    actual_result TEXT DEFAULT '',
                    status TEXT DEFAULT 'Не запускался',
                    tester_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    executed_at TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS risks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    probability INTEGER DEFAULT 1,
                    impact INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'Выявлен',
                    response_plan TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                    scheme_id INTEGER REFERENCES schemes(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    doc_type TEXT DEFAULT '',
                    file_path TEXT DEFAULT '',
                    version TEXT DEFAULT '1.0',
                    uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS change_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    scheme_id INTEGER REFERENCES schemes(id) ON DELETE SET NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    status TEXT DEFAULT 'Новая',
                    requested_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    decision TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS economic_inputs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
                    hourly_rate REAL DEFAULT 850,
                    dev_hours REAL DEFAULT 240,
                    implementation_hours REAL DEFAULT 60,
                    equipment_cost REAL DEFAULT 50000,
                    software_cost REAL DEFAULT 0,
                    indirect_rate REAL DEFAULT 0.20,
                    operation_cost_year REAL DEFAULT 120000,
                    effect_saving_year REAL DEFAULT 420000,
                    discount_rate REAL DEFAULT 0.12,
                    lifetime_years INTEGER DEFAULT 3
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    action TEXT NOT NULL,
                    entity TEXT NOT NULL,
                    entity_id INTEGER,
                    details TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
                CREATE INDEX IF NOT EXISTS idx_schemes_project ON schemes(project_id);
                CREATE INDEX IF NOT EXISTS idx_scheme_nodes_scheme ON scheme_nodes(scheme_id);
                CREATE INDEX IF NOT EXISTS idx_scheme_wires_scheme ON scheme_wires(scheme_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
                CREATE INDEX IF NOT EXISTS idx_requirements_project ON requirements(project_id);
                CREATE INDEX IF NOT EXISTS idx_tests_scheme ON tests(scheme_id);
                CREATE INDEX IF NOT EXISTS idx_risks_project ON risks(project_id);
                CREATE INDEX IF NOT EXISTS idx_docs_project ON documents(project_id);
                """
            )
        self.seed_demo_data()

    def seed_demo_data(self) -> None:
        """Заполняет базу демонстрационными данными.

        Метод можно вызывать повторно: данные добавляются только при пустой базе.
        """
        with self.connect() as conn:
            users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if users_count:
                return

            created = now()
            users = [
                (
                    "admin",
                    hash_password("admin123"),
                    "Администратор системы",
                    ROLE_ADMIN,
                    "admin@example.local",
                    "+7-900-000-00-01",
                    "Департамент информационных технологий",
                    1,
                    created,
                    "",
                ),
                (
                    "manager",
                    hash_password("manager123"),
                    "Руководитель проекта",
                    ROLE_MANAGER,
                    "manager@example.local",
                    "+7-900-000-00-02",
                    "Проектный офис",
                    1,
                    created,
                    "",
                ),
                (
                    "engineer",
                    hash_password("engineer123"),
                    "Инженер-схемотехник",
                    ROLE_ENGINEER,
                    "engineer@example.local",
                    "+7-900-000-00-03",
                    "Лаборатория радиоэлектронных средств",
                    1,
                    created,
                    "",
                ),
                (
                    "controller",
                    hash_password("control123"),
                    "Специалист контроля качества",
                    ROLE_CONTROLLER,
                    "control@example.local",
                    "+7-900-000-00-04",
                    "Служба качества",
                    1,
                    created,
                    "",
                ),
            ]
            conn.executemany(
                """
                INSERT INTO users(login, password_hash, full_name, role, email, phone, department,
                                  is_active, created_at, last_login)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                users,
            )

            manager_id = conn.execute("SELECT id FROM users WHERE login='manager'").fetchone()[0]
            engineer_id = conn.execute("SELECT id FROM users WHERE login='engineer'").fetchone()[0]
            controller_id = conn.execute("SELECT id FROM users WHERE login='controller'").fetchone()[0]

            conn.execute(
                """
                INSERT INTO projects(code, title, customer, manager_id, status, priority,
                                     planned_start, planned_finish, description, budget,
                                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "RSC-2026-01",
                    "Автоматизированная система разработки радиоэлектронных схем",
                    "Московский университет им. С.Ю. Витте",
                    manager_id,
                    "Разработка",
                    "Высокий",
                    "2026-02-01",
                    "2026-05-31",
                    "Проект направлен на централизацию проектной документации, контроль версий схем, "
                    "ведение элементной базы, планирование задач и оценку экономической эффективности.",
                    960000.0,
                    created,
                    created,
                ),
            )
            project_id = conn.execute("SELECT id FROM projects WHERE code='RSC-2026-01'").fetchone()[0]

            stakeholders = [
                (project_id, "Заказчик", "Потребитель результата", "Высокое", "customer@example.local", "Принимает итоговый продукт"),
                (project_id, "Руководитель проекта", "Менеджер", "Высокое", "manager@example.local", "Отвечает за сроки, бюджет и риски"),
                (project_id, "Инженер-схемотехник", "Исполнитель", "Среднее", "engineer@example.local", "Разрабатывает схемы и BOM"),
                (project_id, "Контроль качества", "Эксперт", "Среднее", "control@example.local", "Проверяет требования и тест-кейсы"),
            ]
            conn.executemany(
                "INSERT INTO stakeholders(project_id, name, role, influence, contact, note) VALUES (?, ?, ?, ?, ?, ?)",
                stakeholders,
            )

            schemes = [
                (
                    project_id,
                    "SCH-PSU-001",
                    "Модуль стабилизированного питания 5 В",
                    "Принципиальная электрическая схема",
                    "1.0",
                    "На согласовании",
                    engineer_id,
                    "",
                    "Схема питания контроллера с защитой от переполюсовки и фильтрацией помех.",
                    created,
                    created,
                ),
                (
                    project_id,
                    "SCH-CTRL-001",
                    "Контроллер измерительного узла",
                    "Функциональная схема",
                    "0.9",
                    "Черновик",
                    engineer_id,
                    "",
                    "Функциональная схема микроконтроллерного блока сбора данных.",
                    created,
                    created,
                ),
            ]
            conn.executemany(
                """
                INSERT INTO schemes(project_id, code, title, scheme_type, version, status, author_id,
                                    file_path, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                schemes,
            )

            components = [
                ("LM7805", "Линейный стабилизатор 5 В", "Микросхема", "5V", "шт", "TO-220", "STMicroelectronics", 95.0, 25, 250000.0, "", created),
                ("1N5819", "Диод Шоттки", "Диод", "40V 1A", "шт", "DO-41", "Vishay", 12.0, 200, 150000.0, "", created),
                ("R-10K-0603", "Резистор 10 кОм", "Резистор", "10k", "Ом", "0603", "Yageo", 0.8, 5000, 500000.0, "", created),
                ("C-100NF-0603", "Конденсатор 100 нФ", "Конденсатор", "100nF", "Ф", "0603", "Murata", 1.2, 4000, 400000.0, "", created),
                ("STM32F103C8T6", "Микроконтроллер STM32", "Микросхема", "72MHz", "шт", "LQFP-48", "STMicroelectronics", 420.0, 30, 200000.0, "", created),
                ("CONN-USB-C-16", "Разъем USB Type-C", "Разъем", "16 pin", "шт", "SMD", "GCT", 85.0, 45, 180000.0, "", created),
            ]
            conn.executemany(
                """
                INSERT INTO components(part_number, name, category, nominal, unit, footprint, manufacturer,
                                       price, stock_qty, reliability_mtbf, datasheet_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                components,
            )

            scheme_id = conn.execute("SELECT id FROM schemes WHERE code='SCH-PSU-001'").fetchone()[0]
            component_ids = {row["part_number"]: row["id"] for row in conn.execute("SELECT id, part_number FROM components")}
            bom = [
                (scheme_id, component_ids["LM7805"], "U1", 1, "Основной стабилизатор"),
                (scheme_id, component_ids["1N5819"], "D1", 1, "Защита от обратной полярности"),
                (scheme_id, component_ids["C-100NF-0603"], "C1,C2", 2, "Фильтрация входа и выхода"),
                (scheme_id, component_ids["R-10K-0603"], "R1", 1, "Подтяжка сигнала готовности"),
            ]
            conn.executemany(
                "INSERT INTO scheme_components(scheme_id, component_id, refdes, quantity, note) VALUES (?, ?, ?, ?, ?)",
                bom,
            )

            schematic_nodes = [
                (scheme_id, "n_power", None, "power", "V1", "Вход 7-12 В", 120, 180, 0, created, created),
                (scheme_id, "n_diode", component_ids["1N5819"], "diode", "D1", "Защита от переполюсовки", 260, 180, 0, created, created),
                (scheme_id, "n_reg", component_ids["LM7805"], "ic", "U1", "Стабилизатор 5 В", 430, 180, 0, created, created),
                (scheme_id, "n_cin", component_ids["C-100NF-0603"], "capacitor", "C1", "Входной фильтр", 360, 300, 0, created, created),
                (scheme_id, "n_cout", component_ids["C-100NF-0603"], "capacitor", "C2", "Выходной фильтр", 560, 300, 0, created, created),
                (scheme_id, "n_pullup", component_ids["R-10K-0603"], "resistor", "R1", "Подтяжка", 610, 180, 0, created, created),
                (scheme_id, "n_gnd", None, "ground", "GND", "Общий провод", 430, 420, 0, created, created),
            ]
            conn.executemany(
                """
                INSERT INTO scheme_nodes(scheme_id, node_key, component_id, symbol_type, refdes, label, x, y, rotation, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                schematic_nodes,
            )

            schematic_wires = [
                (scheme_id, "w_in", "+VIN", 180, 180, 200, 180, created, created),
                (scheme_id, "w_d1_u1", "+VIN", 320, 180, 365, 180, created, created),
                (scheme_id, "w_u1_out", "+5V", 495, 180, 550, 180, created, created),
                (scheme_id, "w_out", "+5V", 670, 180, 760, 180, created, created),
                (scheme_id, "w_cin_gnd", "GND", 360, 325, 430, 420, created, created),
                (scheme_id, "w_cout_gnd", "GND", 560, 325, 430, 420, created, created),
                (scheme_id, "w_u1_gnd", "GND", 430, 235, 430, 378, created, created),
            ]
            conn.executemany(
                """
                INSERT INTO scheme_wires(scheme_id, wire_key, net_name, x1, y1, x2, y2, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                schematic_wires,
            )

            requirements = [
                (project_id, "REQ-001", "Централизованное хранение схем", "Система должна хранить сведения о проектах, схемах и версиях документации.", "Функциональное", "Высокий", "Согласовано", "Опрос сотрудников"),
                (project_id, "REQ-002", "Ведение элементной базы", "Система должна позволять регистрировать элементы, параметры, стоимость и наличие.", "Функциональное", "Высокий", "Согласовано", "Анализ AS IS"),
                (project_id, "REQ-003", "Контроль требований и испытаний", "Каждая схема должна связываться с требованиями и тест-кейсами.", "Функциональное", "Средний", "В разработке", "IEEE 830"),
                (project_id, "REQ-004", "Формирование отчетов", "Система должна формировать документы по проекту, BOM и экономической эффективности.", "Функциональное", "Высокий", "Реализовано", "ГОСТ 34.602"),
                (project_id, "REQ-005", "Ролевой доступ", "В системе должны быть роли администратора, руководителя, инженера и контролера качества.", "Безопасность", "Высокий", "Реализовано", "Требования к ПО"),
            ]
            conn.executemany(
                """
                INSERT INTO requirements(project_id, code, title, description, category, priority, status, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                requirements,
            )

            tasks = [
                (project_id, "Провести обследование AS IS", "Описать текущий процесс разработки схем", manager_id, "Выполнена", "Высокий", "2026-02-01", "2026-02-10", 100, None),
                (project_id, "Разработать структуру базы данных", "Определить сущности проекта, схем, компонентов, BOM, требований и тестов", engineer_id, "Выполнена", "Высокий", "2026-02-11", "2026-02-20", 100, None),
                (project_id, "Реализовать серверное API", "Создать авторизацию и CRUD-операции", engineer_id, "В работе", "Высокий", "2026-02-21", "2026-03-05", 65, None),
                (project_id, "Разработать интерфейс пользователя", "Создать экран авторизации, справочники, формы и отчеты", engineer_id, "В работе", "Высокий", "2026-03-06", "2026-03-25", 55, None),
                (project_id, "Провести тестирование", "Сформировать тест-кейсы и протокол испытаний", controller_id, "Новая", "Средний", "2026-03-26", "2026-04-10", 0, None),
                (project_id, "Оценить экономическую эффективность", "Рассчитать TCO, NPV и срок окупаемости", manager_id, "В работе", "Средний", "2026-04-11", "2026-04-20", 35, None),
            ]
            conn.executemany(
                """
                INSERT INTO tasks(project_id, title, description, assigned_to, status, priority, start_date,
                                  due_date, progress, parent_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tasks,
            )

            req_map = {row["code"]: row["id"] for row in conn.execute("SELECT id, code FROM requirements")}
            tests = [
                (scheme_id, req_map["REQ-001"], "Проверка регистрации схемы", "Создать схему и открыть карточку", "Карточка сохраняется и отображается в списке", "Карточка создана", "Пройден", controller_id, created),
                (scheme_id, req_map["REQ-002"], "Проверка BOM", "Добавить компонент в схему", "Компонент появляется в перечне элементов", "Компонент добавлен", "Пройден", controller_id, created),
                (scheme_id, req_map["REQ-004"], "Экспорт перечня элементов", "Сформировать XLSX-отчет", "Файл XLSX создается в папке exports", "", "Не запускался", controller_id, ""),
            ]
            conn.executemany(
                """
                INSERT INTO tests(scheme_id, requirement_id, name, method, expected_result, actual_result,
                                  status, tester_id, executed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tests,
            )

            risks = [
                (project_id, "Неполнота исходных требований", 3, 4, "На контроле", "Проводить согласование требований с заказчиком и фиксировать изменения."),
                (project_id, "Ошибки ручного ввода параметров компонентов", 2, 3, "На контроле", "Использовать справочник и проверку обязательных полей."),
                (project_id, "Недостаток времени на внедрение", 3, 5, "Выявлен", "Сократить второстепенный функционал и сохранить критичные функции."),
                (project_id, "Сопротивление пользователей изменениям", 2, 4, "Выявлен", "Провести обучение и подготовить справку по системе."),
            ]
            conn.executemany(
                "INSERT INTO risks(project_id, title, probability, impact, status, response_plan) VALUES (?, ?, ?, ?, ?, ?)",
                risks,
            )

            documents = [
                (project_id, scheme_id, "Техническое задание", "ТЗ", "", "1.0", manager_id, created),
                (project_id, scheme_id, "Протокол согласования схемы", "Протокол", "", "0.1", controller_id, created),
            ]
            conn.executemany(
                """
                INSERT INTO documents(project_id, scheme_id, title, doc_type, file_path, version, uploaded_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                documents,
            )

            changes = [
                (project_id, scheme_id, "Добавить защиту от переполюсовки", "Заказчик потребовал защитный диод на входе питания.", "Согласована", manager_id, "Изменение включено в версию 1.0", created),
                (project_id, scheme_id, "Уточнить номиналы конденсаторов", "Необходимо проверить соответствие фильтрации уровню помех.", "Новая", controller_id, "", created),
            ]
            conn.executemany(
                """
                INSERT INTO change_requests(project_id, scheme_id, title, description, status, requested_by, decision, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                changes,
            )

            conn.execute(
                """
                INSERT INTO economic_inputs(project_id, hourly_rate, dev_hours, implementation_hours,
                                            equipment_cost, software_cost, indirect_rate, operation_cost_year,
                                            effect_saving_year, discount_rate, lifetime_years)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, 850.0, 420.0, 80.0, 65000.0, 0.0, 0.22, 145000.0, 520000.0, 0.12, 3),
            )

            settings = [
                ("organization", "Московский университет им. С.Ю. Витте", created),
                ("project_methodology", "Agile/Scrum с контрольными точками по ГОСТ 34.602", created),
                ("development_methodology", "Итерационная модель разработки", created),
                ("default_export_format", "docx", created),
                ("backup_enabled", "true", created),
                ("quality_threshold", "80", created),
            ]
            conn.executemany("INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)", settings)

            self.log_action(conn, None, "seed", "database", None, "Созданы демонстрационные данные")

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        with self.connect() as conn:
            cur = conn.execute(sql, tuple(params))
            return cur.lastrowid

    def query_all(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [row_to_dict(row) for row in rows if row is not None]

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
            return row_to_dict(row)

    def log_action(
        self,
        conn: sqlite3.Connection,
        user_id: int | None,
        action: str,
        entity: str,
        entity_id: int | None,
        details: str = "",
    ) -> None:
        conn.execute(
            "INSERT INTO audit_log(user_id, action, entity, entity_id, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, action, entity, entity_id, details, now()),
        )

    def authenticate(self, login: str, password: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE login=? AND is_active=1", (login,)).fetchone()
            if row is None:
                return None
            user = row_to_dict(row)
            if user is None or not verify_password(password, user["password_hash"]):
                return None
            token = secrets.token_urlsafe(32)
            expires = (datetime.now() + timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("INSERT INTO sessions(token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)", (token, user["id"], now(), expires))
            conn.execute("UPDATE users SET last_login=? WHERE id=?", (now(), user["id"]))
            self.log_action(conn, user["id"], "login", "users", user["id"], "Успешный вход")
            safe_user = {key: value for key, value in user.items() if key != "password_hash"}
            return {"token": token, "user": safe_user, "expires_at": expires}

    def get_user_by_token(self, token: str | None) -> dict[str, Any] | None:
        if not token:
            return None
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT u.* FROM sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token=? AND s.expires_at >= ? AND u.is_active=1
                """,
                (token, now()),
            ).fetchone()
            user = row_to_dict(row)
            if user:
                user.pop("password_hash", None)
            return user

    def logout(self, token: str) -> None:
        with self.connect() as conn:
            row = conn.execute("SELECT user_id FROM sessions WHERE token=?", (token,)).fetchone()
            user_id = row["user_id"] if row else None
            conn.execute("DELETE FROM sessions WHERE token=?", (token,))
            self.log_action(conn, user_id, "logout", "sessions", None, "Выход из системы")

    def list_records(
        self,
        table: str,
        filters: Mapping[str, Any] | None = None,
        order_by: str = "id DESC",
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        self._validate_table(table)
        filters = dict(filters or {})
        clauses: list[str] = []
        params: list[Any] = []
        allowed = {"id", *TABLE_COLUMNS[table]}
        for key, value in filters.items():
            if key not in allowed or value in (None, ""):
                continue
            clauses.append(f"{key} = ?")
            params.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        order_sql = self._safe_order(table, order_by)
        sql = f"SELECT * FROM {table}{where} ORDER BY {order_sql} LIMIT ?"
        params.append(limit)
        return self.query_all(sql, params)

    def get_record(self, table: str, record_id: int) -> dict[str, Any] | None:
        self._validate_table(table)
        return self.query_one(f"SELECT * FROM {table} WHERE id=?", (record_id,))

    def create_record(self, table: str, data: Mapping[str, Any], user_id: int | None = None) -> int:
        self._validate_table(table)
        if table in READ_ONLY_TABLES:
            raise ValueError(f"Таблица {table} доступна только для чтения")
        prepared = self._prepare_data(table, data, is_update=False)
        columns = list(prepared.keys())
        if not columns:
            raise ValueError("Нет данных для сохранения")
        placeholders = ", ".join("?" for _ in columns)
        sql = f"INSERT INTO {table}({', '.join(columns)}) VALUES ({placeholders})"
        with self.connect() as conn:
            cur = conn.execute(sql, [prepared[column] for column in columns])
            record_id = int(cur.lastrowid)
            self.log_action(conn, user_id, "create", table, record_id, str({k: prepared[k] for k in columns if k != 'password_hash'}))
            return record_id

    def update_record(self, table: str, record_id: int, data: Mapping[str, Any], user_id: int | None = None) -> None:
        self._validate_table(table)
        if table in READ_ONLY_TABLES:
            raise ValueError(f"Таблица {table} доступна только для чтения")
        prepared = self._prepare_data(table, data, is_update=True)
        if not prepared:
            raise ValueError("Нет данных для обновления")
        assignments = ", ".join(f"{column}=?" for column in prepared.keys())
        sql = f"UPDATE {table} SET {assignments} WHERE id=?"
        with self.connect() as conn:
            conn.execute(sql, [*prepared.values(), record_id])
            self.log_action(conn, user_id, "update", table, record_id, str({k: prepared[k] for k in prepared if k != 'password_hash'}))

    def delete_record(self, table: str, record_id: int, user_id: int | None = None) -> None:
        self._validate_table(table)
        if table in READ_ONLY_TABLES:
            raise ValueError(f"Таблица {table} доступна только для чтения")
        with self.connect() as conn:
            conn.execute(f"DELETE FROM {table} WHERE id=?", (record_id,))
            self.log_action(conn, user_id, "delete", table, record_id, "Удаление записи")

    def create_user(self, data: Mapping[str, Any], user_id: int | None = None) -> int:
        payload = dict(data)
        password = str(payload.pop("password", "change123"))
        payload["password_hash"] = hash_password(password)
        payload.setdefault("created_at", now())
        payload.setdefault("is_active", 1)
        return self.create_record("users", payload, user_id=user_id)

    def change_password(self, target_user_id: int, new_password: str, changed_by: int | None = None) -> None:
        password_hash = hash_password(new_password)
        with self.connect() as conn:
            conn.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash, target_user_id))
            self.log_action(conn, changed_by, "password_change", "users", target_user_id, "Изменение пароля")

    def list_projects_extended(self) -> list[dict[str, Any]]:
        return self.query_all(
            """
            SELECT p.*, u.full_name AS manager_name,
                   (SELECT COUNT(*) FROM schemes s WHERE s.project_id=p.id) AS schemes_count,
                   (SELECT COUNT(*) FROM tasks t WHERE t.project_id=p.id) AS tasks_count,
                   (SELECT AVG(progress) FROM tasks t WHERE t.project_id=p.id) AS average_progress
            FROM projects p
            LEFT JOIN users u ON u.id=p.manager_id
            ORDER BY p.id DESC
            """
        )

    def list_schemes_extended(self) -> list[dict[str, Any]]:
        return self.query_all(
            """
            SELECT s.*, p.code AS project_code, p.title AS project_title, u.full_name AS author_name,
                   (SELECT COUNT(*) FROM scheme_components sc WHERE sc.scheme_id=s.id) AS bom_positions,
                   (SELECT COALESCE(SUM(sc.quantity * c.price), 0)
                    FROM scheme_components sc JOIN components c ON c.id=sc.component_id
                    WHERE sc.scheme_id=s.id) AS bom_cost
            FROM schemes s
            JOIN projects p ON p.id=s.project_id
            LEFT JOIN users u ON u.id=s.author_id
            ORDER BY s.id DESC
            """
        )

    def list_bom_extended(self, scheme_id: int | None = None) -> list[dict[str, Any]]:
        clause = "WHERE sc.scheme_id=?" if scheme_id else ""
        params: tuple[Any, ...] = (scheme_id,) if scheme_id else ()
        return self.query_all(
            f"""
            SELECT sc.*, s.code AS scheme_code, c.part_number, c.name AS component_name, c.category,
                   c.nominal, c.footprint, c.price, c.stock_qty,
                   (sc.quantity * c.price) AS total_price
            FROM scheme_components sc
            JOIN schemes s ON s.id=sc.scheme_id
            JOIN components c ON c.id=sc.component_id
            {clause}
            ORDER BY s.code, sc.refdes
            """,
            params,
        )

    def list_tasks_extended(self) -> list[dict[str, Any]]:
        return self.query_all(
            """
            SELECT t.*, p.code AS project_code, u.full_name AS assigned_name,
                   CASE WHEN t.due_date<>'' AND t.due_date < date('now') AND t.status NOT IN ('Выполнена','Отменена') THEN 1 ELSE 0 END AS is_overdue
            FROM tasks t
            JOIN projects p ON p.id=t.project_id
            LEFT JOIN users u ON u.id=t.assigned_to
            ORDER BY t.due_date ASC, t.id DESC
            """
        )

    def list_requirements_extended(self) -> list[dict[str, Any]]:
        return self.query_all(
            """
            SELECT r.*, p.code AS project_code,
                   (SELECT COUNT(*) FROM tests ts WHERE ts.requirement_id=r.id) AS tests_count
            FROM requirements r
            JOIN projects p ON p.id=r.project_id
            ORDER BY r.project_id, r.code
            """
        )

    def list_tests_extended(self) -> list[dict[str, Any]]:
        return self.query_all(
            """
            SELECT ts.*, s.code AS scheme_code, r.code AS requirement_code, u.full_name AS tester_name
            FROM tests ts
            JOIN schemes s ON s.id=ts.scheme_id
            LEFT JOIN requirements r ON r.id=ts.requirement_id
            LEFT JOIN users u ON u.id=ts.tester_id
            ORDER BY ts.id DESC
            """
        )

    def list_risks_extended(self) -> list[dict[str, Any]]:
        return self.query_all(
            """
            SELECT r.*, p.code AS project_code, (r.probability * r.impact) AS score
            FROM risks r
            JOIN projects p ON p.id=r.project_id
            ORDER BY score DESC, r.id DESC
            """
        )

    def list_documents_extended(self) -> list[dict[str, Any]]:
        return self.query_all(
            """
            SELECT d.*, p.code AS project_code, s.code AS scheme_code, u.full_name AS uploader_name
            FROM documents d
            LEFT JOIN projects p ON p.id=d.project_id
            LEFT JOIN schemes s ON s.id=d.scheme_id
            LEFT JOIN users u ON u.id=d.uploaded_by
            ORDER BY d.id DESC
            """
        )

    def list_change_requests_extended(self) -> list[dict[str, Any]]:
        return self.query_all(
            """
            SELECT cr.*, p.code AS project_code, s.code AS scheme_code, u.full_name AS requester_name
            FROM change_requests cr
            JOIN projects p ON p.id=cr.project_id
            LEFT JOIN schemes s ON s.id=cr.scheme_id
            LEFT JOIN users u ON u.id=cr.requested_by
            ORDER BY cr.id DESC
            """
        )

    def get_schematic_data(self, scheme_id: int) -> dict[str, Any]:
        scheme = self.query_one(
            """
            SELECT s.*, p.code AS project_code, p.title AS project_title, u.full_name AS author_name
            FROM schemes s
            JOIN projects p ON p.id=s.project_id
            LEFT JOIN users u ON u.id=s.author_id
            WHERE s.id=?
            """,
            (scheme_id,),
        )
        if not scheme:
            raise ValueError("Схема не найдена")
        return {
            "scheme": scheme,
            "nodes": self.query_all("SELECT * FROM scheme_nodes WHERE scheme_id=? ORDER BY id", (scheme_id,)),
            "wires": self.query_all("SELECT * FROM scheme_wires WHERE scheme_id=? ORDER BY id", (scheme_id,)),
            "bom": self.list_bom_extended(scheme_id),
        }

    def save_schematic_data(
        self,
        scheme_id: int,
        nodes: list[Mapping[str, Any]],
        wires: list[Mapping[str, Any]],
        user_id: int | None = None,
    ) -> dict[str, int]:
        stamp = now()
        with self.connect() as conn:
            scheme = conn.execute("SELECT id FROM schemes WHERE id=?", (scheme_id,)).fetchone()
            if not scheme:
                raise ValueError("Схема не найдена")
            conn.execute("DELETE FROM scheme_wires WHERE scheme_id=?", (scheme_id,))
            conn.execute("DELETE FROM scheme_nodes WHERE scheme_id=?", (scheme_id,))
            for index, node in enumerate(nodes, start=1):
                node_key = str(node.get("node_key") or f"node_{index}")
                conn.execute(
                    """
                    INSERT INTO scheme_nodes(scheme_id, node_key, component_id, symbol_type, refdes, label,
                                             x, y, rotation, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scheme_id,
                        node_key,
                        node.get("component_id"),
                        node.get("symbol_type") or "generic",
                        node.get("refdes") or "",
                        node.get("label") or "",
                        float(node.get("x") or 100),
                        float(node.get("y") or 100),
                        int(node.get("rotation") or 0),
                        stamp,
                        stamp,
                    ),
                )
            for index, wire in enumerate(wires, start=1):
                wire_key = str(wire.get("wire_key") or f"wire_{index}")
                conn.execute(
                    """
                    INSERT INTO scheme_wires(scheme_id, wire_key, net_name, x1, y1, x2, y2, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scheme_id,
                        wire_key,
                        wire.get("net_name") or "",
                        float(wire.get("x1") or 0),
                        float(wire.get("y1") or 0),
                        float(wire.get("x2") or 0),
                        float(wire.get("y2") or 0),
                        stamp,
                        stamp,
                    ),
                )
            conn.execute("UPDATE schemes SET updated_at=? WHERE id=?", (stamp, scheme_id))
            self.log_action(conn, user_id, "save_schematic", "schemes", scheme_id, f"nodes={len(nodes)}, wires={len(wires)}")
        return {"nodes": len(nodes), "wires": len(wires)}

    def get_project_report_data(self, project_id: int) -> dict[str, Any]:
        project = self.query_one(
            """
            SELECT p.*, u.full_name AS manager_name
            FROM projects p LEFT JOIN users u ON u.id=p.manager_id
            WHERE p.id=?
            """,
            (project_id,),
        )
        if not project:
            raise ValueError("Проект не найден")
        return {
            "project": project,
            "stakeholders": self.query_all("SELECT * FROM stakeholders WHERE project_id=? ORDER BY id", (project_id,)),
            "schemes": self.query_all("SELECT * FROM schemes WHERE project_id=? ORDER BY code", (project_id,)),
            "requirements": self.query_all("SELECT * FROM requirements WHERE project_id=? ORDER BY code", (project_id,)),
            "tasks": self.query_all("SELECT * FROM tasks WHERE project_id=? ORDER BY start_date, id", (project_id,)),
            "risks": self.query_all("SELECT *, probability*impact AS score FROM risks WHERE project_id=? ORDER BY score DESC", (project_id,)),
            "economic": self.query_one("SELECT * FROM economic_inputs WHERE project_id=?", (project_id,)),
        }

    def get_dashboard_stats(self) -> dict[str, Any]:
        stats = self.query_one(
            """
            SELECT
                (SELECT COUNT(*) FROM projects) AS projects_total,
                (SELECT COUNT(*) FROM projects WHERE status NOT IN ('Завершен','Приостановлен')) AS projects_active,
                (SELECT COUNT(*) FROM schemes) AS schemes_total,
                (SELECT COUNT(*) FROM tasks) AS tasks_total,
                (SELECT COUNT(*) FROM tasks WHERE due_date<>'' AND due_date < date('now') AND status NOT IN ('Выполнена','Отменена')) AS tasks_overdue,
                (SELECT COUNT(*) FROM tests WHERE status='Не пройден') AS tests_failed,
                (SELECT COUNT(*) FROM risks WHERE probability*impact >= 12 AND status<>'Закрыт') AS risks_high,
                (SELECT COALESCE(SUM(budget),0) FROM projects) AS total_budget
            """
        )
        details = {
            "project_statuses": self.query_all("SELECT status, COUNT(*) AS count FROM projects GROUP BY status ORDER BY count DESC"),
            "task_statuses": self.query_all("SELECT status, COUNT(*) AS count FROM tasks GROUP BY status ORDER BY count DESC"),
            "test_statuses": self.query_all("SELECT status, COUNT(*) AS count FROM tests GROUP BY status ORDER BY count DESC"),
            "top_risks": self.query_all("SELECT title, probability*impact AS score FROM risks ORDER BY score DESC LIMIT 5"),
        }
        if stats is None:
            stats = {}
        stats["details"] = details
        return stats

    def search(self, term: str) -> dict[str, list[dict[str, Any]]]:
        like = f"%{term}%"
        return {
            "projects": self.query_all("SELECT * FROM projects WHERE code LIKE ? OR title LIKE ? OR description LIKE ?", (like, like, like)),
            "schemes": self.query_all("SELECT * FROM schemes WHERE code LIKE ? OR title LIKE ? OR description LIKE ?", (like, like, like)),
            "components": self.query_all("SELECT * FROM components WHERE part_number LIKE ? OR name LIKE ? OR category LIKE ?", (like, like, like)),
            "requirements": self.query_all("SELECT * FROM requirements WHERE code LIKE ? OR title LIKE ? OR description LIKE ?", (like, like, like)),
        }

    def _validate_table(self, table: str) -> None:
        if table not in TABLE_COLUMNS:
            raise ValueError(f"Недопустимая таблица: {table}")

    def _prepare_data(self, table: str, data: Mapping[str, Any], is_update: bool) -> dict[str, Any]:
        allowed = set(TABLE_COLUMNS[table])
        prepared = {key: value for key, value in data.items() if key in allowed}
        stamp = now()
        if table in {"projects", "schemes", "scheme_nodes", "scheme_wires"}:
            if not is_update:
                prepared.setdefault("created_at", stamp)
            prepared.setdefault("updated_at", stamp)
        if table in {"components", "documents", "change_requests"} and not is_update:
            prepared.setdefault("created_at", stamp)
        if table == "users" and not is_update:
            prepared.setdefault("created_at", stamp)
        if table == "settings":
            prepared.setdefault("updated_at", stamp)
        if table == "users" and "password" in data:
            prepared["password_hash"] = hash_password(str(data["password"]))
        if table == "tasks" and "progress" in prepared:
            try:
                progress = int(prepared["progress"])
            except (TypeError, ValueError):
                progress = 0
            prepared["progress"] = max(0, min(progress, 100))
        if table == "scheme_components" and "quantity" in prepared:
            try:
                prepared["quantity"] = max(1, int(prepared["quantity"]))
            except (TypeError, ValueError):
                prepared["quantity"] = 1
        if table == "risks":
            for field in ("probability", "impact"):
                if field in prepared:
                    try:
                        prepared[field] = max(1, min(5, int(prepared[field])))
                    except (TypeError, ValueError):
                        prepared[field] = 1
        return prepared

    def _safe_order(self, table: str, order_by: str) -> str:
        allowed = {"id", *TABLE_COLUMNS[table]}
        parts = order_by.replace(",", " ").split()
        if not parts:
            return "id DESC"
        column = parts[0]
        direction = parts[1].upper() if len(parts) > 1 else "ASC"
        if column not in allowed:
            column = "id"
        if direction not in {"ASC", "DESC"}:
            direction = "ASC"
        return f"{column} {direction}"
