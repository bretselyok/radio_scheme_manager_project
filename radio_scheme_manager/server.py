"""Локальный HTTP-сервер приложения.

Сервер использует только стандартную библиотеку Python. Он предоставляет REST-
подобный API для настольного клиента и демонстрирует клиент-серверную
архитектуру, требуемую в ВКР.
"""
from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from .app_config import HOST, PORT
from .services import AccessDenied, ApplicationService, ValidationError

LOGGER = logging.getLogger(__name__)


class JsonResponse:
    def __init__(self, data: Any, status: int = 200) -> None:
        self.data = data
        self.status = status


class ApiHandler(BaseHTTPRequestHandler):
    service: ApplicationService = ApplicationService()

    def log_message(self, format: str, *args: Any) -> None:
        LOGGER.debug(format, *args)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json({}, HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def do_PUT(self) -> None:  # noqa: N802
        self._dispatch("PUT")

    def do_DELETE(self) -> None:  # noqa: N802
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        try:
            response = self._route(method)
            self._send_json(response.data, response.status)
        except AccessDenied as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.FORBIDDEN)
        except ValidationError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - финальный защитный обработчик
            LOGGER.exception("Unhandled API error")
            self._send_json({"error": f"Внутренняя ошибка сервера: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _route(self, method: str) -> JsonResponse:
        parsed = urlparse(self.path)
        path = parsed.path.strip("/")
        parts = path.split("/") if path else []
        query = parse_qs(parsed.query)
        body = self._read_json()

        if parts == ["api", "login"] and method == "POST":
            return JsonResponse(self.service.login(str(body.get("login", "")), str(body.get("password", ""))))

        token = self._token_from_headers()
        user = self.service.get_user(token)

        if parts == ["api", "logout"] and method == "POST":
            return JsonResponse(self.service.logout(token))
        if parts == ["api", "me"] and method == "GET":
            return JsonResponse(user)
        if parts == ["api", "dashboard"] and method == "GET":
            return JsonResponse(self.service.dashboard(user))
        if parts == ["api", "search"] and method == "GET":
            term = query.get("term", [""])[0]
            return JsonResponse(self.service.search(user, term))
        if len(parts) == 3 and parts[:2] == ["api", "economics"] and method == "GET":
            return JsonResponse(self.service.economics(user, int(parts[2])))
        if len(parts) == 4 and parts[:2] == ["api", "bom"] and parts[3] == "summary" and method == "GET":
            return JsonResponse(self.service.bom_summary(user, int(parts[2])))
        if len(parts) == 4 and parts[:2] == ["api", "risks"] and parts[3] == "matrix" and method == "GET":
            return JsonResponse(self.service.risk_matrix(user, int(parts[2])))
        if len(parts) == 3 and parts[:2] == ["api", "reports"] and method == "POST":
            return JsonResponse(self.service.export_report(user, parts[2], body))
        if len(parts) == 3 and parts[:2] == ["api", "schematic"]:
            scheme_id = int(parts[2])
            if method == "GET":
                return JsonResponse(self.service.get_schematic(user, scheme_id))
            if method == "PUT":
                return JsonResponse(self.service.save_schematic(user, scheme_id, body))
        if len(parts) == 4 and parts[:2] == ["api", "schematic"] and parts[3] == "export" and method == "POST":
            return JsonResponse(self.service.export_schematic(user, int(parts[2])))

        if len(parts) >= 2 and parts[0] == "api":
            table = parts[1]
            if len(parts) == 2:
                if method == "GET":
                    filters = {key: values[0] for key, values in query.items() if values}
                    return JsonResponse(self.service.list_records(user, table, filters=filters))
                if method == "POST":
                    return JsonResponse(self.service.create_record(user, table, body), HTTPStatus.CREATED)
            if len(parts) == 3:
                record_id = int(parts[2])
                if method == "GET":
                    return JsonResponse(self.service.get_record(user, table, record_id))
                if method == "PUT":
                    return JsonResponse(self.service.update_record(user, table, record_id, body))
                if method == "DELETE":
                    return JsonResponse(self.service.delete_record(user, table, record_id))

        raise ValidationError("Маршрут API не найден")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError("Некорректный JSON-запрос") from exc

    def _token_from_headers(self) -> str | None:
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth.removeprefix("Bearer ").strip()
        return self.headers.get("X-Auth-Token")

    def _send_json(self, data: Any, status: int | HTTPStatus = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, X-Auth-Token, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if int(status) != HTTPStatus.NO_CONTENT:
            self.wfile.write(payload)


def create_server(host: str = HOST, port: int = PORT, service: ApplicationService | None = None) -> ThreadingHTTPServer:
    service = service or ApplicationService()
    service.initialize()
    handler_class = type("ConfiguredApiHandler", (ApiHandler,), {"service": service})
    return ThreadingHTTPServer((host, port), handler_class)


def run_server(host: str = HOST, port: int = PORT) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = create_server(host, port)
    LOGGER.info("API-сервер запущен: http://%s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Остановка сервера")
    finally:
        server.server_close()
