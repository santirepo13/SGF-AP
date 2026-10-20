"""FastAPI application factory and application-lifecycle management."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from typing import AsyncIterator

from fastapi import FastAPI

from api.config import PostgresConnectionProvider, load_database_config
from api.dependencies import prepare_application_dependencies
from api.routes import register_routers

logger = logging.getLogger("sgf_ap.api")


def create_app() -> FastAPI:
    """Build SGF-AP without opening runtime resources during import."""

    _configure_logging()
    application = FastAPI(title="SGF-AP", lifespan=lifespan)
    register_routers(application)
    return application


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Initialize shared resources and release startup resources safely."""

    provider: PostgresConnectionProvider | None = None
    readiness_connection = None
    logger.info("api_startup_started")
    try:
        logger.info("database_configuration_loading")
        config = load_database_config()
        provider = PostgresConnectionProvider(config)
        logger.info("database_provider_prepared")

        readiness_connection = provider.connect()
        logger.info("database_readiness_check_started")
        with readiness_connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            if cursor.fetchone()[0] != 1:
                raise RuntimeError("database readiness query returned an invalid result")
        logger.info("database_readiness_check_succeeded")

        application.state.db_config = config
        application.state.db_provider = provider
        application.state.dependencies = prepare_application_dependencies(provider)
        logger.info("application_dependencies_prepared")
    except BaseException:
        logger.exception("api_startup_failed")
        _release_application_resources(application)
        raise
    finally:
        if readiness_connection is not None:
            _close_startup_connection(readiness_connection)

    logger.info("api_startup_ready")
    try:
        yield
    finally:
        logger.info("api_shutdown_started")
        _release_application_resources(application)
        logger.info("api_shutdown_finished")


def _close_startup_connection(connection: object) -> None:
    try:
        connection.close()
        logger.info("database_readiness_connection_closed")
    except BaseException:
        logger.exception("database_readiness_connection_close_failed")


def _release_application_resources(application: FastAPI) -> None:
    """Release only application-scoped values; request connections close per operation."""

    for name in ("dependencies", "db_provider", "db_config"):
        if hasattr(application.state, name):
            try:
                delattr(application.state, name)
            except BaseException:
                logger.exception("application_resource_release_failed", extra={"resource": name})


def _configure_logging() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
