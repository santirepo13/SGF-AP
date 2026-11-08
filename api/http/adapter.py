"""Common bridge from one HTTP operation to the middleware pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from api.contracts import ExecutionContext
from api.http.context import (
    build_execution_context,
    correlation_id_for_request,
    user_access_token_for_request,
)
from api.http.responses import operation_response
from api.middleware.operation_policies import OPERATION_POLICIES


@dataclass(frozen=True, slots=True)
class HttpOperation:
    """Server-owned mapping from one route to one registered service method."""

    service_name: str
    method_name: str
    success_status: int = 200
    no_store: bool = False

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
        result, context = self._execute_result(
            request,
            operation,
            service,
            *args,
            **kwargs,
        )
        response = operation_response(result, success_status=operation.success_status)
        if operation.no_store:
            response.headers["Cache-Control"] = "no-store"
        return response

    def execute_binary(
        self,
        request: Request,
        operation: HttpOperation,
        service: object,
        *args: Any,
        **kwargs: Any,
    ) -> JSONResponse | StreamingResponse:
        result, _context = self._execute_result(
            request,
            operation,
            service,
            *args,
            **kwargs,
        )
        if not result.success:
            return operation_response(result, success_status=operation.success_status)
        descriptor = result.data
        return StreamingResponse(
            _close_after_iteration(descriptor),
            media_type=descriptor.media_type,
            headers={
                "Content-Length": str(descriptor.size_bytes),
                "Content-Disposition": (
                    f'attachment; filename="{descriptor.download_name}"'
                ),
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    def _execute_result(
        self,
        request: Request,
        operation: HttpOperation,
        service: object,
        *args: Any,
        **kwargs: Any,
    ):
        application_dependencies = getattr(request.app.state, "dependencies", None)
        if application_dependencies is None:
            raise RuntimeError("application dependencies are not initialized")
        policy = OPERATION_POLICIES.get(operation.name)
        if policy is None:
            raise RuntimeError("HTTP operation is not registered")

        correlation_id = correlation_id_for_request(request, application_dependencies.correlation_ids)
        if policy.resolve_actor:
            access_token = user_access_token_for_request(request, correlation_id=correlation_id)
            operation_dependencies = getattr(request.state, "sgfap_operation_dependencies", None)
            identity_factory = getattr(application_dependencies, "identity_for_operation", None)
            if callable(identity_factory):
                identity_provider = identity_factory(
                    access_token,
                    operation_dependencies,
                    correlation_id=correlation_id,
                )
            else:
                # Preserve the adapter's standalone testability for callers
                # that supply the pre-login dependency shape.
                identity_provider = application_dependencies.identity_provider
            context = build_execution_context(
                request,
                operation.name,
                identity_provider,
                application_dependencies.correlation_ids,
            )
        else:
            # Login and account registration must not validate an old, invalid,
            # or duplicate user credential sent by a client.
            context = ExecutionContext(operation=operation.name, correlation_id=correlation_id, actor=None)

        with application_dependencies.bind_actor(context.actor):
            result = application_dependencies.pipeline.execute(
                operation.service_name,
                operation.method_name,
                service,
                *args,
                context=context,
                **kwargs,
            )
        return result, context


def _close_after_iteration(descriptor):
    try:
        while chunk := descriptor.stream.read(256 * 1024):
            yield chunk
    finally:
        descriptor.close()


def get_http_adapter(request: Request) -> HttpOperationAdapter:
    """FastAPI dependency returning the common operation adapter."""

    adapter = getattr(request.app.state, "http_adapter", None)
    if not isinstance(adapter, HttpOperationAdapter):
        raise RuntimeError("HTTP adapter is not initialized")
    return adapter
