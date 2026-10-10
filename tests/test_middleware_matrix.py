"""S8 middleware interruption, preservation and safety cases."""

from api.contracts import ActorContext, ExecutionContext, ErrorOutput, OperationResult, UserCreateInput
from api.errors import ErrorCode
from api.middleware import (
    AuthorizationMiddleware, ContextMiddleware, ErrorMiddleware,
    ExecutionLoggingMiddleware, MiddlewarePipeline, ValidationMiddleware,
)
from api.middleware.base import MiddlewareRequest


class Identity:
    def __init__(self, actor=None): self.actor = actor
    def resolve(self): return self.actor


class Correlations:
    def generate(self): return "generated-s8"


class Permissions:
    def __init__(self, allowed=True): self.allowed = allowed
    def is_allowed(self, actor, permission, operation): return self.allowed


class Logger:
    def __init__(self, fail=False): self.fail, self.started, self.finished = fail, [], []
    def start(self, record):
        if self.fail: raise RuntimeError("logging destination unavailable")
        self.started.append(record)
    def finish(self, record):
        if self.fail: raise RuntimeError("logging destination unavailable")
        self.finished.append(record)


class PublicService:
    def __init__(self, result=None): self.calls, self.result = 0, result
    def get_by_id(self, context, user_id: int):
        self.calls += 1
        return OperationResult.ok(self.result if self.result is not None else user_id)


class UserCreateService:
    def __init__(self): self.calls = 0
    def create(self, context, data: UserCreateInput):
        self.calls += 1
        return OperationResult.ok(data)


class BadResultService:
    def get_by_id(self, context, user_id: int) -> OperationResult[int]:
        return OperationResult.ok("not-an-int")


def _pipeline(actor=None, permissions=None, logger=None):
    return MiddlewarePipeline(
        ContextMiddleware(Identity(actor), Correlations()),
        ValidationMiddleware(),
        AuthorizationMiddleware(permissions),
        ErrorMiddleware(),
        ExecutionLoggingMiddleware(logger or Logger()),
    )


def test_existing_context_correlation_is_preserved():
    context = ExecutionContext("UserService.get_by_id", "existing-s8", None)
    result = _pipeline().execute("UserService", "get_by_id", PublicService(), 1, context=context)
    assert result.success


def test_operation_method_mismatch_is_rejected_before_service():
    request = MiddlewareRequest("UserService", "get_by_id", PublicService(), (1,), operation="UserService.get_by_email")
    result = ErrorMiddleware().process(
        request,
        lambda current: ContextMiddleware(Identity(), Correlations()).process(current, lambda _: OperationResult.ok()),
    )
    assert result.error.code == ErrorCode.INVALID_VALUE.value


def test_service_is_invoked_once_and_false_is_valid_data():
    service = PublicService(False)
    result = _pipeline().execute("UserService", "get_by_id", service, 1)
    assert result.success and result.data is False
    assert service.calls == 1


def test_invalid_input_stops_before_service():
    service = PublicService()
    result = _pipeline().execute("UserService", "get_by_id", service, "wrong")
    assert result.error.code == ErrorCode.INVALID_VALUE.value
    assert service.calls == 0


def test_actor_absent_inactive_and_forbidden_cases_are_distinct():
    service = UserCreateService()
    data = UserCreateInput("A", "B", "a@example.test", "hash", 1)
    absent = _pipeline().execute("UserService", "create", service, data)
    inactive = _pipeline(ActorContext(1, 1, False), Permissions()).execute("UserService", "create", service, data)
    forbidden = _pipeline(ActorContext(1, 1, True), Permissions(False)).execute("UserService", "create", service, data)
    assert absent.error.code == ErrorCode.FORBIDDEN_OPERATION.value
    assert inactive.error.code == ErrorCode.INACTIVE_USER.value
    assert forbidden.error.code == ErrorCode.FORBIDDEN_OPERATION.value
    assert service.calls == 0


def test_logging_failure_does_not_repeat_service_or_change_result():
    service = PublicService(False)
    result = _pipeline(logger=Logger(True)).execute("UserService", "get_by_id", service, 1)
    assert result.success and result.data is False
    assert service.calls == 1


def test_incompatible_annotated_result_becomes_internal_error():
    result = _pipeline().execute("UserService", "get_by_id", BadResultService(), 1)
    assert result.error.code == ErrorCode.UNEXPECTED_ERROR.value


def test_known_service_error_keeps_public_shape_and_correlation():
    class FailingService:
        def get_by_id(self, context, user_id: int):
            return OperationResult.fail(ErrorOutput("VAL-002", "controlled", "service-correlation"))

    result = _pipeline().execute("UserService", "get_by_id", FailingService(), 1)
    assert result.error.code == ErrorCode.INVALID_VALUE.value
    assert result.error.correlation_id == "generated-s8"
