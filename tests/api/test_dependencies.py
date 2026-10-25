"""Unit coverage for Scrum 1 dependency composition and operation scope."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.config import APIConfig
from api.dependencies import (
    ApplicationDependencies,
    ConnectionTransactionCoordinator,
    _safe_log_fields,
    get_api_config,
    get_evidence_service,
    get_history_service,
    get_ticket_service,
    prepare_application_dependencies,
)


class FakeConnection:
    def __init__(self) -> None:
        self.closed = 0
        self.commits = 0
        self.rollbacks = 0

    def close(self) -> None:
        self.closed += 1

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeConnectionProvider:
    def __init__(self, *connections: FakeConnection) -> None:
        self.connections = list(connections)

    def connection(self):
        connection = self.connections.pop(0)

        class ConnectionScope:
            def __enter__(self):
                return connection

            def __exit__(self, exc_type, exc, traceback):
                connection.close()
                return False

        return ConnectionScope()


def test_request_scoped_ticket_evidence_and_history_service_dependencies() -> None:
    ticket_service = object()
    evidence_service = object()
    history_service = object()
    operation_dependencies = SimpleNamespace(
        ticket_service=ticket_service,
        evidence_service=evidence_service,
        history_service=history_service,
    )

    assert get_ticket_service(operation_dependencies) is ticket_service
    assert get_evidence_service(operation_dependencies) is evidence_service
    assert get_history_service(operation_dependencies) is history_service

    api_config = APIConfig(8002, "connector", "secret")
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(api_config=api_config)))
    assert get_api_config(request) is api_config


def test_operation_dependencies_share_connection_transaction_and_release_it() -> None:
    connection = FakeConnection()
    provider = FakeConnectionProvider(connection)
    application_dependencies = prepare_application_dependencies(provider)  # type: ignore[arg-type]

    with application_dependencies.operation() as operation:
        assert operation.catalog_service.municipalities.connection is connection
        assert operation.address_service.addresses.connection is connection
        assert operation.ticket_service.tickets.connection is connection
        assert operation.ticket_service.events.connection is connection
        assert operation.evidence_service.evidences.connection is connection
        assert operation.history_service.events.connection is connection
        assert operation.catalog_service.transaction is operation.ticket_service.transaction
        assert operation.ticket_service.transaction is operation.history_service.transaction

    assert connection.closed == 1


def test_each_operation_uses_and_closes_its_own_connection() -> None:
    first = FakeConnection()
    second = FakeConnection()
    template = prepare_application_dependencies(FakeConnectionProvider())  # type: ignore[arg-type]
    dependencies = ApplicationDependencies(
        FakeConnectionProvider(first, second),  # type: ignore[arg-type]
        template.pipeline,
        template.identity_provider,
        template.correlation_ids,
    )

    with dependencies.operation() as first_operation:
        with dependencies.operation() as second_operation:
            assert first_operation.ticket_service.tickets.connection is first
            assert second_operation.ticket_service.tickets.connection is second

    assert first.closed == 1
    assert second.closed == 1


def test_operation_scope_releases_connection_when_service_setup_or_route_fails() -> None:
    connection = FakeConnection()
    dependencies = prepare_application_dependencies(FakeConnectionProvider(connection))  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="route failure"):
        with dependencies.operation():
            raise RuntimeError("route failure")

    assert connection.closed == 1


def test_transaction_coordinator_delegates_to_operation_connection() -> None:
    connection = FakeConnection()
    transaction = ConnectionTransactionCoordinator(connection)

    transaction.commit()
    transaction.rollback()

    assert connection.commits == 1
    assert connection.rollbacks == 1


def test_middleware_pipeline_is_composed_with_its_default_collaborators() -> None:
    dependencies = prepare_application_dependencies(FakeConnectionProvider())  # type: ignore[arg-type]
    pipeline = dependencies.pipeline

    assert pipeline.context.identity_provider.__class__.__name__ == "RequestIdentityProvider"
    assert dependencies.identity_provider.__class__.__name__ == "UnauthenticatedIdentityProvider"
    assert pipeline.context.correlation_ids.__class__.__name__ == "UuidCorrelationIdGenerator"
    assert pipeline.authorization.permission_checker.__class__.__name__ == "DenyPermissionChecker"
    assert pipeline.logging.logger.__class__.__name__ == "StructuredExecutionLogger"


def test_execution_log_metadata_excludes_unapproved_sensitive_values() -> None:
    result = _safe_log_fields(
        {
            "event": "started",
            "correlation_id": "corr-1",
            "operation": "TicketService.create",
            "password": "not-to-log",
            "authorization": "not-to-log",
            "request_body": "not-to-log",
        }
    )

    assert result == {
        "event": "started",
        "correlation_id": "corr-1",
        "operation": "TicketService.create",
    }
