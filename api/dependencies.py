"""Central composition of request-scoped SGF-AP dependencies."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import logging
from typing import Annotated, Any

from fastapi import Depends, Request

from api.config import PostgresConnectionProvider
from api.contracts import ActorContext
from api.http.context import RequestIdentityProvider, bind_request_actor
from api.interfaces.services import (
    AddressServiceInterface,
    CatalogServiceInterface,
    CrewServiceInterface,
    EvidenceServiceInterface,
    HistoryServiceInterface,
    TicketServiceInterface,
    UserServiceInterface,
)
from api.middleware import (
    AuthorizationMiddleware,
    ContextMiddleware,
    ErrorMiddleware,
    ExecutionLoggingMiddleware,
    MiddlewarePipeline,
    ValidationMiddleware,
)
from api.middleware.base import CorrelationIdGenerator, IdentityProvider, PermissionChecker
from api.middleware.context_middleware import UuidCorrelationIdGenerator
from api.repositories import (
    ActionRepository,
    AddressRepository,
    CommuneRepository,
    CrewMemberRepository,
    CrewRepository,
    CrossBisCodeRepository,
    CrossQuadrantRepository,
    CrossSuffixLetterRepository,
    EvidenceRepository,
    FailureTypeRepository,
    HistoryEventRepository,
    MunicipalityRepository,
    NeighborhoodRepository,
    PriorityRepository,
    RoadBisCodeRepository,
    RoadQuadrantRepository,
    RoadSuffixLetterRepository,
    RoadTypeRepository,
    RoleRepository,
    StatusRepository,
    TicketRepository,
    UserRepository,
)
from api.services import (
    AddressService,
    CatalogService,
    CrewService,
    EvidenceService,
    HistoryService,
    TicketService,
    UserService,
)

logger = logging.getLogger("sgf_ap.api")


class ConnectionTransactionCoordinator:
    """Expose a request connection's transaction controls to application services."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()


class UnauthenticatedIdentityProvider:
    """Default identity adapter until HTTP authentication is introduced."""

    def resolve(self):
        return None


class DenyPermissionChecker:
    """Safely deny protected operations until a remote identity adapter is configured."""

    def is_allowed(self, actor, permission: str, operation: str) -> bool:
        return False


class StructuredExecutionLogger:
    """Write pipeline lifecycle events without request bodies or credentials."""

    def __init__(self, execution_logger: logging.Logger) -> None:
        self._logger = execution_logger

    def start(self, record: dict[str, Any]) -> None:
        self._logger.info("operation_started", extra=_safe_log_fields(record))

    def finish(self, record: dict[str, Any]) -> None:
        self._logger.info("operation_finished", extra=_safe_log_fields(record))


@dataclass(slots=True)
class RepositorySet:
    municipalities: MunicipalityRepository
    communes: CommuneRepository
    neighborhoods: NeighborhoodRepository
    road_types: RoadTypeRepository
    road_suffix_letters: RoadSuffixLetterRepository
    road_bis_codes: RoadBisCodeRepository
    road_quadrants: RoadQuadrantRepository
    cross_suffix_letters: CrossSuffixLetterRepository
    cross_bis_codes: CrossBisCodeRepository
    cross_quadrants: CrossQuadrantRepository
    addresses: AddressRepository
    roles: RoleRepository
    users: UserRepository
    crews: CrewRepository
    crew_members: CrewMemberRepository
    priorities: PriorityRepository
    failure_types: FailureTypeRepository
    statuses: StatusRepository
    actions: ActionRepository
    tickets: TicketRepository
    evidences: EvidenceRepository
    history_events: HistoryEventRepository


@dataclass(slots=True)
class OperationDependencies:
    """Request-scoped services and pipeline delivered to HTTP route modules."""

    pipeline: MiddlewarePipeline
    catalog_service: CatalogServiceInterface
    address_service: AddressServiceInterface
    user_service: UserServiceInterface
    crew_service: CrewServiceInterface
    ticket_service: TicketServiceInterface
    evidence_service: EvidenceServiceInterface
    history_service: HistoryServiceInterface


class ApplicationDependencies:
    """Application-level composition with isolated dependencies per operation."""

    def __init__(
        self,
        connection_provider: PostgresConnectionProvider,
        pipeline: MiddlewarePipeline,
        identity_provider: IdentityProvider,
        correlation_ids: CorrelationIdGenerator,
    ) -> None:
        self.connection_provider = connection_provider
        self.pipeline = pipeline
        self.identity_provider = identity_provider
        self.correlation_ids = correlation_ids

    @contextmanager
    def bind_actor(self, actor: ActorContext | None) -> Iterator[None]:
        with bind_request_actor(actor):
            yield

    @contextmanager
    def operation(self) -> Iterator[OperationDependencies]:
        with self.connection_provider.connection() as connection:
            repositories = _build_repositories(connection)
            transaction = ConnectionTransactionCoordinator(connection)
            yield _build_operation_dependencies(repositories, transaction, self.pipeline)


def prepare_application_dependencies(
    connection_provider: PostgresConnectionProvider,
    *,
    identity_provider: IdentityProvider | None = None,
    permission_checker: PermissionChecker | None = None,
    correlation_ids: CorrelationIdGenerator | None = None,
) -> ApplicationDependencies:
    """Create application-shared collaborators and request-scoped service factories."""

    trusted_identity_provider = identity_provider or UnauthenticatedIdentityProvider()
    request_identity_provider = RequestIdentityProvider()
    correlation_generator = correlation_ids or UuidCorrelationIdGenerator()
    execution_logger = StructuredExecutionLogger(logger)
    pipeline = MiddlewarePipeline(
        context=ContextMiddleware(
            identity_provider=request_identity_provider,
            correlation_ids=correlation_generator,
        ),
        validation=ValidationMiddleware(),
        authorization=AuthorizationMiddleware(permission_checker=permission_checker or DenyPermissionChecker()),
        errors=ErrorMiddleware(),
        logging=ExecutionLoggingMiddleware(execution_logger),
    )
    return ApplicationDependencies(
        connection_provider,
        pipeline,
        trusted_identity_provider,
        correlation_generator,
    )


def get_operation_dependencies(request: Request) -> Iterator[OperationDependencies]:
    """FastAPI dependency that opens one shared connection for one operation."""

    dependencies = getattr(request.app.state, "dependencies", None)
    if not isinstance(dependencies, ApplicationDependencies):
        raise RuntimeError("application dependencies are not initialized")
    with dependencies.operation() as operation:
        yield operation


def get_catalog_service(
    operation_dependencies: Annotated[OperationDependencies, Depends(get_operation_dependencies)],
) -> CatalogServiceInterface:
    """Provide the request-scoped catalog service to catalog HTTP routes."""

    return operation_dependencies.catalog_service


def get_address_service(
    operation_dependencies: Annotated[OperationDependencies, Depends(get_operation_dependencies)],
) -> AddressServiceInterface:
    """Provide the request-scoped address service to address HTTP routes."""

    return operation_dependencies.address_service


def get_user_service(
    operation_dependencies: Annotated[OperationDependencies, Depends(get_operation_dependencies)],
) -> UserServiceInterface:
    """Provide the request-scoped user service to user HTTP routes."""

    return operation_dependencies.user_service


def get_crew_service(
    operation_dependencies: Annotated[OperationDependencies, Depends(get_operation_dependencies)],
) -> CrewServiceInterface:
    """Provide the request-scoped crew service to crew HTTP routes."""

    return operation_dependencies.crew_service


def get_ticket_service(
    operation_dependencies: Annotated[OperationDependencies, Depends(get_operation_dependencies)],
) -> TicketServiceInterface:
    """Provide the request-scoped ticket service to ticket HTTP routes."""

    return operation_dependencies.ticket_service


def get_evidence_service(
    operation_dependencies: Annotated[OperationDependencies, Depends(get_operation_dependencies)],
) -> EvidenceServiceInterface:
    """Provide the request-scoped evidence service to evidence HTTP routes."""

    return operation_dependencies.evidence_service


def get_history_service(
    operation_dependencies: Annotated[OperationDependencies, Depends(get_operation_dependencies)],
) -> HistoryServiceInterface:
    """Provide the request-scoped history service to history HTTP routes."""

    return operation_dependencies.history_service


def _build_repositories(connection: Any) -> RepositorySet:
    return RepositorySet(
        municipalities=MunicipalityRepository(connection),
        communes=CommuneRepository(connection),
        neighborhoods=NeighborhoodRepository(connection),
        road_types=RoadTypeRepository(connection),
        road_suffix_letters=RoadSuffixLetterRepository(connection),
        road_bis_codes=RoadBisCodeRepository(connection),
        road_quadrants=RoadQuadrantRepository(connection),
        cross_suffix_letters=CrossSuffixLetterRepository(connection),
        cross_bis_codes=CrossBisCodeRepository(connection),
        cross_quadrants=CrossQuadrantRepository(connection),
        addresses=AddressRepository(connection),
        roles=RoleRepository(connection),
        users=UserRepository(connection),
        crews=CrewRepository(connection),
        crew_members=CrewMemberRepository(connection),
        priorities=PriorityRepository(connection),
        failure_types=FailureTypeRepository(connection),
        statuses=StatusRepository(connection),
        actions=ActionRepository(connection),
        tickets=TicketRepository(connection),
        evidences=EvidenceRepository(connection),
        history_events=HistoryEventRepository(connection),
    )


def _build_operation_dependencies(
    repositories: RepositorySet,
    transaction: ConnectionTransactionCoordinator,
    pipeline: MiddlewarePipeline,
) -> OperationDependencies:
    return OperationDependencies(
        pipeline=pipeline,
        catalog_service=CatalogService(
            municipalities=repositories.municipalities,
            communes=repositories.communes,
            neighborhoods=repositories.neighborhoods,
            road_types=repositories.road_types,
            road_suffix_letters=repositories.road_suffix_letters,
            road_bis_codes=repositories.road_bis_codes,
            road_quadrants=repositories.road_quadrants,
            cross_suffix_letters=repositories.cross_suffix_letters,
            cross_bis_codes=repositories.cross_bis_codes,
            cross_quadrants=repositories.cross_quadrants,
            roles=repositories.roles,
            priorities=repositories.priorities,
            failure_types=repositories.failure_types,
            statuses=repositories.statuses,
            actions=repositories.actions,
            transaction=transaction,
        ),
        address_service=AddressService(
            addresses=repositories.addresses,
            neighborhoods=repositories.neighborhoods,
            road_types=repositories.road_types,
            road_suffix_letters=repositories.road_suffix_letters,
            road_bis_codes=repositories.road_bis_codes,
            road_quadrants=repositories.road_quadrants,
            cross_suffix_letters=repositories.cross_suffix_letters,
            cross_bis_codes=repositories.cross_bis_codes,
            cross_quadrants=repositories.cross_quadrants,
            transaction=transaction,
        ),
        user_service=UserService(
            users=repositories.users,
            roles=repositories.roles,
            transaction=transaction,
        ),
        crew_service=CrewService(
            crews=repositories.crews,
            members=repositories.crew_members,
            users=repositories.users,
            transaction=transaction,
        ),
        ticket_service=TicketService(
            tickets=repositories.tickets,
            users=repositories.users,
            failure_types=repositories.failure_types,
            statuses=repositories.statuses,
            actions=repositories.actions,
            addresses=repositories.addresses,
            crews=repositories.crews,
            evidences=repositories.evidences,
            events=repositories.history_events,
            transaction=transaction,
        ),
        evidence_service=EvidenceService(
            evidences=repositories.evidences,
            tickets=repositories.tickets,
            users=repositories.users,
            transaction=transaction,
        ),
        history_service=HistoryService(
            events=repositories.history_events,
            tickets=repositories.tickets,
            actions=repositories.actions,
            transaction=transaction,
        ),
    )


def _safe_log_fields(record: dict[str, Any]) -> dict[str, Any]:
    """Whitelist metadata emitted by the execution logger."""

    return {
        key: record[key]
        for key in ("event", "correlation_id", "operation", "actor_user_id", "duration_seconds", "success", "error_code")
        if key in record
    }
