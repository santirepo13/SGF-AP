"""FastAPI application factory and application-lifecycle management."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from api.config import PostgresConnectionProvider, load_api_config, load_database_config
from api.dependencies import ConfiguredPermissionChecker, prepare_application_dependencies
from api.errors.http import register_http_error_handlers
from api.http.adapter import HttpOperationAdapter
from api.http.authentication import BasicAuthenticationMiddleware
from api.middleware.base import CorrelationIdGenerator, IdentityProvider, PermissionChecker
from api.security import AccessTokenProvider, PasswordRecoveryStore
from api.notifications import ResendPasswordRecoveryNotifier
from api.routes import register_routers

logger = logging.getLogger("sgf_ap.api")


def create_app(
    *,
    identity_provider: IdentityProvider | None = None,
    permission_checker: PermissionChecker | None = None,
    correlation_ids: CorrelationIdGenerator | None = None,
) -> FastAPI:
    """Build SGF-AP without opening runtime resources during import."""

    _configure_logging()
    application = FastAPI(title="SGF-AP", lifespan=lifespan)
    application.state.identity_provider = identity_provider
    application.state.permission_checker = permission_checker
    application.state.correlation_ids = correlation_ids
    application.add_middleware(BasicAuthenticationMiddleware)
    _configure_openapi_security(application)
    register_http_error_handlers(application)
    register_routers(application)
    return application


def _configure_openapi_security(application: FastAPI) -> None:
    """Declare the server-side HTTP Basic scheme used by protected routes."""

    def openapi_schema():
        if application.openapi_schema:
            return application.openapi_schema
        schema = get_openapi(
            title=application.title,
            version=getattr(application, "version", "0.1.0"),
            description=application.description,
            routes=application.routes,
            tags=application.openapi_tags,
        )
        components = schema.setdefault("components", {})
        schemes = components.setdefault("securitySchemes", {})
        schemes.setdefault("HTTPBasic", {"type": "http", "scheme": "basic"})
        schemes.setdefault("UserAccessToken", {"type": "apiKey", "in": "header", "name": "User-Access-Token"})
        application.openapi_schema = schema
        return schema

    application.openapi = openapi_schema  # type: ignore[method-assign]


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Initialize shared resources and release startup resources safely."""

    provider: PostgresConnectionProvider | None = None
    readiness_connection = None
    logger.info("api_startup_started")
    try:
        application.state.api_config = load_api_config()
        if application.state.api_config.actor is not None:
            if getattr(application.state, "permission_checker", None) is None:
                application.state.permission_checker = ConfiguredPermissionChecker(application.state.api_config)
        access_token_provider = AccessTokenProvider(application.state.api_config.access_token)
        recovery_config = application.state.api_config.password_recovery
        password_recovery_store = None
        password_recovery_notifier = None
        if recovery_config is not None and recovery_config.enabled:
            password_recovery_store = PasswordRecoveryStore(
                recovery_config.proof_secret,
                code_ttl_seconds=recovery_config.code_ttl_seconds,
                grant_ttl_seconds=recovery_config.grant_ttl_seconds,
                max_verify_attempts=recovery_config.max_verify_attempts,
                resend_wait_seconds=recovery_config.resend_wait_seconds,
            )
            password_recovery_notifier = ResendPasswordRecoveryNotifier(
                api_key=recovery_config.resend_api_key or "",
                from_email=recovery_config.resend_from_email or "",
                timeout_seconds=recovery_config.resend_timeout_seconds,
            )
            logger.info("password_recovery_provider_enabled sender=%s", recovery_config.resend_from_email)
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
        application.state.dependencies = prepare_application_dependencies(
            provider,
            identity_provider=getattr(application.state, "identity_provider", None),
            permission_checker=getattr(application.state, "permission_checker", None),
            correlation_ids=getattr(application.state, "correlation_ids", None),
            access_token_provider=access_token_provider,
            password_recovery_store=password_recovery_store,
            password_recovery_notifier=password_recovery_notifier,
            password_recovery_code_ttl_seconds=(recovery_config.code_ttl_seconds if recovery_config is not None else 600),
        )
        application.state.http_adapter = HttpOperationAdapter()
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

    for name in ("http_adapter", "dependencies", "db_provider", "db_config", "api_config"):
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
