from api.contracts import ActorContext, ExecutionContext, OperationResult, UserCreateInput
from api.errors import ErrorCode
from api.middleware import (
    AuthorizationMiddleware, ContextMiddleware, ErrorMiddleware,
    ExecutionLoggingMiddleware, MiddlewarePipeline, ValidationMiddleware,
)


class Identity:
    def __init__(self, actor): self.actor = actor
    def resolve(self): return self.actor


class Correlations:
    def generate(self): return "generated-correlation"


class Permissions:
    def __init__(self, allowed=True): self.allowed, self.calls = allowed, []
    def is_allowed(self, actor, permission, operation):
        self.calls.append((actor.user_id, permission, operation))
        return self.allowed


class Logger:
    def __init__(self): self.started, self.finished = [], []
    def start(self, record): self.started.append(record)
    def finish(self, record): self.finished.append(record)


class UserServiceDouble:
    def __init__(self): self.calls = 0
    def get_by_id(self, context, user_id: int):
        self.calls += 1
        return OperationResult.ok(user_id)


class UserWriteDouble:
    def __init__(self): self.calls = 0
    def create(self, context, data: UserCreateInput):
        self.calls += 1
        return OperationResult.ok(False)


def pipeline(actor=None, permissions=None, logger=None):
    return MiddlewarePipeline(
        ContextMiddleware(Identity(actor), Correlations()),
        ValidationMiddleware(),
        AuthorizationMiddleware(permissions),
        ErrorMiddleware(),
        ExecutionLoggingMiddleware(logger or Logger()),
    )


def test_pipeline_sets_correlation_invokes_service_once_and_logs_result():
    service = UserServiceDouble()
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
    service = UserServiceDouble()
    result = pipeline().execute("UserService", "get_by_id", service, "not-an-int")

    assert not result.success
    assert result.error.code == ErrorCode.INVALID_VALUE.value
    assert service.calls == 0


def test_inactive_actor_stops_protected_operation():
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
    service = UserServiceDouble()
    logger = Logger()
    result = MiddlewarePipeline(
        ContextMiddleware(Identity(None), Correlations()), ValidationMiddleware(),
        AuthorizationMiddleware(), ErrorMiddleware(), ExecutionLoggingMiddleware(logger),
    ).execute("UserService", "get_by_id", service, "invalid")

    assert result.error.code == ErrorCode.INVALID_VALUE.value
    assert logger.finished[0]["success"] is False
    assert logger.finished[0]["error_code"] == ErrorCode.INVALID_VALUE.value


def test_supplied_correlation_is_preserved_on_failure():
    service = UserServiceDouble()
    context = ExecutionContext("UserService.get_by_id", "caller-correlation", None)
    result = pipeline().execute("UserService", "get_by_id", service, "invalid", context=context)

    assert result.error.code == ErrorCode.INVALID_VALUE.value
    assert result.error.correlation_id == "caller-correlation"
