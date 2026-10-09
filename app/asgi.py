"""ASGI entry point: `uvicorn app.asgi:app`."""

import logging

from app.main import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = create_app()
