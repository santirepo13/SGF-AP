"""Scrum 2 unit coverage for request context and pipeline adaptation."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import Request

from api.contracts import ActorContext, OperationResult
from api.http.adapter import HttpOperation, HttpOperationAdapter
from api.http.context import RequestIdentityProvider, bind_request_actor, build_execution_context, correlation_id_for_request


class FixedIdentity:
    def __init__(self, actor: ActorContext | None) -> None:
        self.actor = actor

    def resolve(self) -> ActorContext | None:
        return self.actor


class FixedCorrelations:
    def generate(self) -> str:
        return "generated-correlation"


class RecordingPipeline:
    def __init__(self) -> None:
        self.call = None

    def execute(self, service_name, method_name, service, *args, context, **kwargs):
        self.call = (service_name, method_name, service, args, context, kwargs)
        return OperationResult.ok(False)


class RequestDependencies:
    def __init__(self, actor: ActorContext | None) -> None:
        self.identity_provider = FixedIdentity(actor)
        self.correlation_ids = FixedCorrelations()
        self.pipeline = RecordingPipeline()

    @contextmanager
    def bind_actor(self, actor):
        with bind_request_actor(actor):
            yield


def request_for(app, *, correlation_id: str | None = None) -> Request:
    headers = [] if correlation_id is None else [(b"x-correlation-id", correlation_id.encode())]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers, "app": app})


def test_context_uses_server_identity_and_preserves_supplied_correlation_id() -> None:
    actor = ActorContext(user_id=5, role_id=2, active=True)
    request = request_for(SimpleNamespace(state=SimpleNamespace()), correlation_id="request-42")

    context = build_execution_context(request, "TicketService.request_closure", FixedIdentity(actor), FixedCorrelations())

    assert context.operation == "TicketService.request_closure"
    assert context.correlation_id == "request-42"
    assert context.actor is actor
    assert correlation_id_for_request(request) == "request-42"


def test_request_identity_provider_is_scoped_and_resets_after_execution() -> None:
    actor = ActorContext(user_id=5, role_id=2, active=True)
    provider = RequestIdentityProvider()

    assert provider.resolve() is None
    with bind_request_actor(actor):
        assert provider.resolve() is actor
    assert provider.resolve() is None


def test_adapter_executes_registered_operation_through_pipeline_with_trusted_actor() -> None:
    actor = ActorContext(user_id=5, role_id=2, active=True)
    dependencies = RequestDependencies(actor)
    application = SimpleNamespace(state=SimpleNamespace(dependencies=dependencies, http_adapter=HttpOperationAdapter()))
    request = request_for(application)
    service = object()

    response = HttpOperationAdapter().execute(
        request,
        HttpOperation("TicketService", "request_closure"),
        service,
        "input-contract",
    )

    assert response.status_code == 200
    assert dependencies.pipeline.call[:4] == ("TicketService", "request_closure", service, ("input-contract",))
    assert dependencies.pipeline.call[4].actor is actor
    assert dependencies.pipeline.call[4].correlation_id == "generated-correlation"
