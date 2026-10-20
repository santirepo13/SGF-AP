"""ASGI entrypoint for SGF-AP."""

from api.sgfap_api import create_app

app = create_app()
