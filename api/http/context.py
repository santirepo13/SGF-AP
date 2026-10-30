"""Request-scoped execution context, correlation, and actor integration."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Protocol

from fastapi import Request

from api.contracts import ActorContext, ExecutionContext
from api.errors import ApplicationError
from api.middleware.base import CorrelationIdGenerator
from api.middleware.context_middleware import UuidCorrelationIdGenerator

_CORRELATION_HEADER = "X-Correlation-ID"
_USER_ACCESS_TOKEN_HEADER = "user-access-token"
_CURRENT_ACTOR: ContextVar[ActorContext | None] = ContextVar("sgfap_request_actor", default=None)


class RequestIdentityProvider:
    """Pipeline identity provider backed by a request-local context variable."""

    def resolve(self) -> ActorContext | None:
        return _CURRENT_ACTOR.get()


class RequestIdentityResolver(Protocol):
    """Trusted server-side identity source used before entering the pipeline."""

    def resolve(self) -> ActorContext | None: ...


def correlation_id_for_request(
    request: Request,
    correlation_ids: CorrelationIdGenerator | None = None,
) -> str:
    """Get or create the correlation identifier available to every HTTP error path."""

    current = getattr(request.state, "correlation_id", None)
    if isinstance(current, str) and current:
        return current

    supplied = request.headers.get(_CORRELATION_HEADER)
    correlation_id = supplied.strip() if supplied and _is_safe_correlation_id(supplied.strip()) else None
    correlation_id = correlation_id or (correlation_ids or UuidCorrelationIdGenerator()).generate()
    request.state.correlation_id = correlation_id
    return correlation_id


def get_request_correlation_id(request: Request) -> str:
    """FastAPI dependency that exposes the request correlation identifier."""

    return correlation_id_for_request(request)


def user_access_token_for_request(request: Request, *, correlation_id: str | None = None) -> str | None:
    """Extract one exact user access-token header without normalizing it."""

    raw_headers = getattr(getattr(request, "scope", None), "get", lambda *_: ())("headers", ())
    values: list[str] = []
    if isinstance(raw_headers, (list, tuple)):
        for item in raw_headers:
            if not isinstance(item, tuple) or len(item) != 2:
                continue
            name, value = item
            if isinstance(name, bytes) and name.lower() == _USER_ACCESS_TOKEN_HEADER.encode("ascii"):
                try:
                    values.append(value.decode("latin-1") if isinstance(value, bytes) else str(value))
                except UnicodeDecodeError:
                    raise ApplicationError.invalid_access_token(correlation_id=correlation_id)
    else:
        headers = getattr(request, "headers", None)
        if headers is not None:
            try:
                values = list(headers.getlist("User-Access-Token"))
            except AttributeError:
                candidate = headers.get("User-Access-Token")
                if candidate is not None:
                    values = [candidate]
    if len(values) > 1 or (values and values[0] == ""):
        raise ApplicationError.invalid_access_token(correlation_id=correlation_id)
    return values[0] if values else None


def build_execution_context(
    request: Request,
    operation: str,
    identity_provider: RequestIdentityResolver | None = None,
    correlation_ids: CorrelationIdGenerator | None = None,
) -> ExecutionContext:
    """Resolve trusted request identity and form the context supplied to a service."""

    correlation_id = correlation_id_for_request(request, correlation_ids)
    try:
        actor = identity_provider.resolve() if identity_provider is not None else None
    except ApplicationError:
        raise
    except BaseException as exc:
        raise ApplicationError.unexpected(correlation_id=correlation_id, cause=exc) from exc
    if actor is not None and not isinstance(actor, ActorContext):
        raise ApplicationError.unexpected(correlation_id=correlation_id)
    return ExecutionContext(operation=operation, correlation_id=correlation_id, actor=actor)


@contextmanager
def bind_request_actor(actor: ActorContext | None) -> Iterator[None]:
    """Make a trusted actor visible only while one request runs through middleware."""

    token: Token[ActorContext | None] = _CURRENT_ACTOR.set(actor)
    try:
        yield
    finally:
        _CURRENT_ACTOR.reset(token)


def _is_safe_correlation_id(value: str) -> bool:
    return 1 <= len(value) <= 128 and all(character.isalnum() or character in "-_.:" for character in value)
