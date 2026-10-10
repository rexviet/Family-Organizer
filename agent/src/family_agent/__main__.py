"""Chạy: python -m family_agent  (cổng 3100, chỉ trong mạng compose — không publish port)."""

from __future__ import annotations

import logging

import uvicorn

from family_agent.app import create_app
from family_agent.settings import load_settings

HOST = "0.0.0.0"  # noqa: S104 — trong container; compose không có `ports:` nên chỉ app gọi được
PORT = 3100


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = load_settings()
    uvicorn.run(
        create_app(settings),
        host=HOST,
        port=PORT,
        access_log=False,
        server_header=False,
        proxy_headers=False,
        log_config=None,  # giữ cấu hình logging ở trên (một dòng JSON/lượt)
    )


if __name__ == "__main__":
    main()
