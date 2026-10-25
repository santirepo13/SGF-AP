"""HTTP translation of SGF-AP's public error contracts."""

from fastapi import FastAPI

from .status_mapping import status_for_error_code


def register_http_error_handlers(app: FastAPI) -> None:
    """Register handlers lazily to avoid response-handler import cycles."""

    from .exception_handlers import register_http_error_handlers as register

    register(app)


__all__ = ["register_http_error_handlers", "status_for_error_code"]
