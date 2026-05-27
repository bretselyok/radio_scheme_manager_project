"""Общие настройки проекта.

Файл можно редактировать перед запуском в PyCharm. По умолчанию база данных
создается в папке data рядом с корнем проекта, а экспортируемые отчеты - в
папке exports.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
DATA_DIR: Final[Path] = PROJECT_ROOT / "data"
EXPORT_DIR: Final[Path] = PROJECT_ROOT / "exports"
DB_PATH: Final[Path] = DATA_DIR / "radio_schemes.db"
HOST: Final[str] = "127.0.0.1"
PORT: Final[int] = 8765
API_BASE_URL: Final[str] = f"http://{HOST}:{PORT}"
DATE_FORMAT: Final[str] = "%Y-%m-%d"
DATETIME_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

ROLE_ADMIN: Final[str] = "admin"
ROLE_MANAGER: Final[str] = "manager"
ROLE_ENGINEER: Final[str] = "engineer"
ROLE_CONTROLLER: Final[str] = "controller"

ALL_ROLES: Final[tuple[str, ...]] = (
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_ENGINEER,
    ROLE_CONTROLLER,
)

PROJECT_STATUSES: Final[tuple[str, ...]] = (
    "Черновик",
    "Планирование",
    "Разработка",
    "Тестирование",
    "Внедрение",
    "Завершен",
    "Приостановлен",
)

SCHEME_STATUSES: Final[tuple[str, ...]] = (
    "Черновик",
    "На согласовании",
    "Требует доработки",
    "Утверждена",
    "Архив",
)

TASK_STATUSES: Final[tuple[str, ...]] = (
    "Новая",
    "В работе",
    "На проверке",
    "Выполнена",
    "Отменена",
)

REQUIREMENT_STATUSES: Final[tuple[str, ...]] = (
    "Собрано",
    "Согласовано",
    "В разработке",
    "Реализовано",
    "Отклонено",
)

TEST_STATUSES: Final[tuple[str, ...]] = (
    "Не запускался",
    "Пройден",
    "Не пройден",
    "Блокирован",
)

RISK_STATUSES: Final[tuple[str, ...]] = (
    "Выявлен",
    "На контроле",
    "Снижен",
    "Закрыт",
)

PRIORITIES: Final[tuple[str, ...]] = (
    "Низкий",
    "Средний",
    "Высокий",
    "Критический",
)

SCHEME_TYPES: Final[tuple[str, ...]] = (
    "Принципиальная электрическая схема",
    "Структурная схема",
    "Функциональная схема",
    "Монтажная схема",
    "Печатная плата",
)

COMPONENT_CATEGORIES: Final[tuple[str, ...]] = (
    "Резистор",
    "Конденсатор",
    "Диод",
    "Транзистор",
    "Микросхема",
    "Разъем",
    "Катушка индуктивности",
    "Источник питания",
    "Прочее",
)

REPORT_TYPES: Final[tuple[str, ...]] = (
    "Паспорт проекта",
    "Перечень элементов",
    "Отчет по испытаниям",
    "Экономическая эффективность",
    "Сводный отчет руководителя",
)


@dataclass(frozen=True)
class RuntimeConfig:
    """Параметры запуска сервера и клиента."""

    host: str = HOST
    port: int = PORT
    db_path: Path = DB_PATH
    data_dir: Path = DATA_DIR
    export_dir: Path = EXPORT_DIR

    @property
    def api_base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


def ensure_directories() -> None:
    """Создает служебные каталоги проекта."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
