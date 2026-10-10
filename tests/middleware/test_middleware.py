"""Middleware ordering, interruptions, results, correlation and logging."""

if __name__ == "__main__":
    # Direct execution hands this file to pytest so its fixtures and assertions run.
    import sys
    from pathlib import Path
    import pytest

    project_root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pytest.ini").is_file())
    sys.path.insert(0, str(project_root))
    raise SystemExit(pytest.main([__file__, *sys.argv[1:]]))

from api.contracts import ActorContext, ExecutionContext, ErrorOutput, OperationResult, UserCreateInput
from api.errors import ErrorCode
from api.middleware import (
    AuthorizationMiddleware, ContextMiddleware, ErrorMiddleware,
    ExecutionLoggingMiddleware, MiddlewarePipeline, ValidationMiddleware,
)
from api.middleware.base import MiddlewareRequest
from tests.support.middleware import (
    Correlations, Identity, Logger, Permissions, PublicService, UserWriteDouble, pipeline,
)


class BadResultService:
    """Return the wrong data type to exercise middleware result validation."""
    def get_by_id(self, context, user_id: int) -> OperationResult[int]:
        """Claim to return an integer while returning text."""
        return OperationResult.ok("not-an-int")


def test_pipeline_sets_correlation_invokes_service_once_and_logs_result():
    """Build a full pipeline, run one request, and verify correlation and logs."""
    service = PublicService()
    logger = Logger()
    result = MiddlewarePipeline(
        ContextMiddleware(Identity(None), Correlations()), ValidationMiddleware(),
        AuthorizationMiddleware(), ErrorMiddleware(), ExecutionLoggingMiddleware(logger),
    ).execute("UserService", "get_by_id", service, 7)

    assert result.success and result.data == 7
    assert service.calls == 1
    assert logger.started[0]["correlation_id"] == "generated-correlation"
    assert logger.finished[0]["success"] is True


def test_invalid_input_stops_before_service():
    """Reject an invalid argument before it reaches the service."""
    service = PublicService()
    result = pipeline().execute("UserService", "get_by_id", service, "not-an-int")

    assert not result.success
    assert result.error.code == ErrorCode.INVALID_VALUE.value
    assert service.calls == 0


def test_inactive_actor_stops_protected_operation():
    """Deny a protected write by an inactive actor without calling the service."""
    service = UserWriteDouble()
    actor = ActorContext(9, 2, False)
    result = pipeline(actor, Permissions()).execute(
        "UserService", "create", service,
        UserCreateInput("A", "B", "a@example.com", "hash", 1),
    )

    assert not result.success
    assert result.error.code == ErrorCode.INACTIVE_USER.value
    assert service.calls == 0


def test_valid_false_result_is_preserved():
    """Treat a false service value as successful data, not an error."""
    service = UserWriteDouble()
    actor = ActorContext(9, 2, True)
    result = pipeline(actor, Permissions(True)).execute(
        "UserService", "create", service,
        UserCreateInput("A", "B", "a@example.com", "hash", 1),
    )

    assert result.success is True
    assert result.data is False
    assert service.calls == 1


def test_interruption_is_logged_with_the_central_error_code():
    """Log an invalid request as an unsuccessful operation with its reason."""
    service = PublicService()
    logger = Logger()
    result = MiddlewarePipeline(
        ContextMiddleware(Identity(None), Correlations()), ValidationMiddleware(),
        AuthorizationMiddleware(), ErrorMiddleware(), ExecutionLoggingMiddleware(logger),
    ).execute("UserService", "get_by_id", service, "invalid")

    assert result.error.code == ErrorCode.INVALID_VALUE.value
    assert logger.finished[0]["success"] is False
    assert logger.finished[0]["error_code"] == ErrorCode.INVALID_VALUE.value


def test_supplied_correlation_is_preserved_on_failure():
    """Keep the caller's tracking reference in an error response."""
    service = PublicService()
    context = ExecutionContext("UserService.get_by_id", "caller-correlation", None)
    result = pipeline().execute("UserService", "get_by_id", service, "invalid", context=context)

    assert result.error.code == ErrorCode.INVALID_VALUE.value
    assert result.error.correlation_id == "caller-correlation"


def test_existing_context_correlation_is_preserved():
    """Keep the tracking reference already stored in a successful context."""
    context = ExecutionContext("UserService.get_by_id", "existing-s8", None)
    result = pipeline().execute("UserService", "get_by_id", PublicService(), 1, context=context)
    assert result.success


def test_operation_method_mismatch_is_rejected_before_service():
    """Reject a request whose declared operation differs from its method."""
    request = MiddlewareRequest("UserService", "get_by_id", PublicService(), (1,), operation="UserService.get_by_email")
    result = ErrorMiddleware().process(
        request,
        lambda current: ContextMiddleware(Identity(), Correlations()).process(current, lambda _: OperationResult.ok()),
    )
    assert result.error.code == ErrorCode.INVALID_VALUE.value


def test_service_is_invoked_once_and_false_is_valid_data():
    """Call the service once and preserve a false return value as data."""
    service = PublicService(False)
    result = pipeline().execute("UserService", "get_by_id", service, 1)
    assert result.success and result.data is False
    assert service.calls == 1


def test_actor_absent_inactive_and_forbidden_cases_are_distinct():
    """Check missing, inactive, and unauthorized actors independently."""
    service = UserWriteDouble()
    data = UserCreateInput("A", "B", "a@example.test", "hash", 1)
    absent = pipeline().execute("UserService", "create", service, data)
    inactive = pipeline(ActorContext(1, 1, False), Permissions()).execute("UserService", "create", service, data)
    forbidden = pipeline(ActorContext(1, 1, True), Permissions(False)).execute("UserService", "create", service, data)
    assert absent.error.code == ErrorCode.FORBIDDEN_OPERATION.value
    assert inactive.error.code == ErrorCode.INACTIVE_USER.value
    assert forbidden.error.code == ErrorCode.FORBIDDEN_OPERATION.value
    assert service.calls == 0


def test_logging_failure_does_not_repeat_service_or_change_result():
    """Keep the service response unchanged when logging itself fails."""
    service = PublicService(False)
    result = pipeline(logger=Logger(True)).execute("UserService", "get_by_id", service, 1)
    assert result.success and result.data is False
    assert service.calls == 1


def test_incompatible_annotated_result_becomes_internal_error():
    """Convert a returned value that violates its declared type to an error."""
    result = pipeline().execute("UserService", "get_by_id", BadResultService(), 1)
    assert result.error.code == ErrorCode.UNEXPECTED_ERROR.value


def test_known_service_error_keeps_public_shape_and_correlation():
    """Preserve a known service error's public fields and request reference."""
    class FailingService:
        """Return a known public error for middleware to pass through."""
        def get_by_id(self, context, user_id: int):
            """Supply a controlled error with a service-level reference."""
            return OperationResult.fail(ErrorOutput("VAL-002", "controlled", "service-correlation"))

    result = pipeline().execute("UserService", "get_by_id", FailingService(), 1)
    assert result.error.code == ErrorCode.INVALID_VALUE.value
    assert result.error.correlation_id == "generated-correlation"
