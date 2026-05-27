"""Единый запуск учебного проекта.

В PyCharm можно открыть папку проекта и запустить этот файл. Он поднимает
локальный API-сервер в отдельном потоке и открывает графический клиент.
"""
from __future__ import annotations

import threading
import time
from contextlib import suppress

from radio_scheme_manager.api_client import ApiClient
from radio_scheme_manager.app_config import API_BASE_URL, HOST, PORT
from radio_scheme_manager.server import create_server
from radio_scheme_manager.ui import run_client


def main() -> None:
    server = create_server(HOST, PORT)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    try:
        run_client(ApiClient(API_BASE_URL))
    finally:
        with suppress(Exception):
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
