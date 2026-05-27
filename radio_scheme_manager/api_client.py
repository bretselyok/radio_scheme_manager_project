"""Клиент для обращения к локальному API."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping

from .app_config import API_BASE_URL


class ApiClientError(Exception):
    pass


class ApiClient:
    def __init__(self, base_url: str = API_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None
        self.current_user: dict[str, Any] | None = None

    def login(self, login: str, password: str) -> dict[str, Any]:
        result = self.post("/api/login", {"login": login, "password": password}, auth=False)
        self.token = result["token"]
        self.current_user = result["user"]
        return result

    def logout(self) -> None:
        if self.token:
            try:
                self.post("/api/logout", {})
            finally:
                self.token = None
                self.current_user = None

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        if params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
            separator = "&" if "?" in path else "?"
            path = f"{path}{separator}{query}"
        return self.request("GET", path)

    def post(self, path: str, data: Mapping[str, Any], auth: bool = True) -> Any:
        return self.request("POST", path, data, auth=auth)

    def put(self, path: str, data: Mapping[str, Any]) -> Any:
        return self.request("PUT", path, data)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

    def request(self, method: str, path: str, data: Mapping[str, Any] | None = None, auth: bool = True) -> Any:
        url = self.base_url + path
        body = None
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="ignore")
            try:
                payload = json.loads(raw)
                message = payload.get("error", raw)
            except json.JSONDecodeError:
                message = raw or str(exc)
            raise ApiClientError(message) from exc
        except urllib.error.URLError as exc:
            raise ApiClientError(f"Не удалось подключиться к API-серверу: {exc}") from exc

    def list_records(self, table: str, **filters: Any) -> list[dict[str, Any]]:
        return self.get(f"/api/{table}", filters)

    def get_record(self, table: str, record_id: int) -> dict[str, Any]:
        return self.get(f"/api/{table}/{record_id}")

    def create_record(self, table: str, data: Mapping[str, Any]) -> dict[str, Any]:
        return self.post(f"/api/{table}", data)

    def update_record(self, table: str, record_id: int, data: Mapping[str, Any]) -> dict[str, Any]:
        return self.put(f"/api/{table}/{record_id}", data)

    def delete_record(self, table: str, record_id: int) -> dict[str, Any]:
        return self.delete(f"/api/{table}/{record_id}")

    def dashboard(self) -> dict[str, Any]:
        return self.get("/api/dashboard")

    def export_report(self, report_type: str, **payload: Any) -> dict[str, Any]:
        return self.post(f"/api/reports/{report_type}", payload)

    def economics(self, project_id: int) -> dict[str, Any]:
        return self.get(f"/api/economics/{project_id}")

    def bom_summary(self, scheme_id: int) -> dict[str, Any]:
        return self.get(f"/api/bom/{scheme_id}/summary")

    def risk_matrix(self, project_id: int) -> dict[str, Any]:
        return self.get(f"/api/risks/{project_id}/matrix")

    def get_schematic(self, scheme_id: int) -> dict[str, Any]:
        return self.get(f"/api/schematic/{scheme_id}")

    def save_schematic(self, scheme_id: int, data: Mapping[str, Any]) -> dict[str, Any]:
        return self.put(f"/api/schematic/{scheme_id}", data)

    def export_schematic(self, scheme_id: int) -> dict[str, Any]:
        return self.post(f"/api/schematic/{scheme_id}/export", {})
