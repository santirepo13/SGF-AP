"""Common bridge from one HTTP operation to the middleware pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from api.http.context import build_execution_context
from api.http.responses import operation_response


@dataclass(frozen=True, slots=True)
class HttpOperation:
    """Server-owned mapping from one route to one registered service method."""

    service_name: str
    method_name: str
    success_status: int = 200

    @property
    def name(self) -> str:
        return f"{self.service_name}.{self.method_name}"


class HttpOperationAdapter:
    """Execute operations through the request-scoped pipeline and serialize the result."""

    def execute(
        self,
        request: Request,
        operation: HttpOperation,
        service: object,
        *args: Any,
        **kwargs: Any,
    ) -> JSONResponse:
        application_dependencies = getattr(request.app.state, "dependencies", None)
        if application_dependencies is None:
            raise RuntimeError("application dependencies are not initialized")

        context = build_execution_context(
            request,
            operation.name,
            application_dependencies.identity_provider,
            application_dependencies.correlation_ids,
        )
        with application_dependencies.bind_actor(context.actor):
            result = application_dependencies.pipeline.execute(
                operation.service_name,
                operation.method_name,
                service,
                *args,
                context=context,
                **kwargs,
            )
        return operation_response(result, success_status=operation.success_status)


def get_http_adapter(request: Request) -> HttpOperationAdapter:
    """FastAPI dependency returning the common operation adapter."""

    adapter = getattr(request.app.state, "http_adapter", None)
    if not isinstance(adapter, HttpOperationAdapter):
        raise RuntimeError("HTTP adapter is not initialized")
    return adapter
