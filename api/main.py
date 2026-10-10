"""Minimal SGF-AP application entrypoint without business routes."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from api.config import PostgresConnectionProvider, load_database_config
from api.errors import ApplicationError

logger = logging.getLogger("sgf_ap.api")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    logger.addHandler(_handler)
logger.propagate = False


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Load configuration, verify PostgreSQL and close it on shutdown."""
    logger.info("api_startup_started")
    try:
        logger.info("database_configuration_loading")
        config = load_database_config()
        logger.info(
            "database_configuration_loaded",
            extra={"db_host": config.host, "db_port": config.port, "db_name": config.name, "db_user": config.user},
        )
        provider = PostgresConnectionProvider(config)
        logger.info("database_connection_opening")
        connection = provider.connect()
        logger.info("database_connection_opened")
        with connection.cursor() as cursor:
            logger.info("database_readiness_query_started")
            cursor.execute("SELECT 1")
            if cursor.fetchone()[0] != 1:
                raise RuntimeError("database readiness query returned an invalid result")
        logger.info("database_readiness_query_succeeded")
        application.state.db_config = config
        application.state.db_provider = provider
        application.state.db_connection = connection
        logger.info("api_startup_ready")
    except ApplicationError as exc:
        logger.exception("api_startup_failed", extra={"error_code": exc.code.value})
        raise RuntimeError(f"database startup failed: {exc.code.value}") from None
    except Exception as exc:
        logger.exception("api_startup_failed", extra={"error_type": type(exc).__name__})
        raise RuntimeError("database startup failed") from None

    try:
        yield
    finally:
        logger.info("api_shutdown_started")
        try:
            connection.close()
            logger.info("database_connection_closed")
        except Exception:
            logger.exception("database_connection_close_failed")
        logger.info("api_shutdown_finished")


app = FastAPI(
    title="SGF-AP",
    lifespan=lifespan,
)