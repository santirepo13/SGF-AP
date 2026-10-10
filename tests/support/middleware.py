"""Identity, permission, logging and service doubles for middleware tests."""

from api.contracts import OperationResult, UserCreateInput
from api.middleware import (
    AuthorizationMiddleware, ContextMiddleware, ErrorMiddleware,
    ExecutionLoggingMiddleware, MiddlewarePipeline, ValidationMiddleware,
)


class Identity:
    def __init__(self, actor=None):
        self.actor = actor

    def resolve(self):
        return self.actor


class Correlations:
    def generate(self):
        return "generated-correlation"


class Permissions:
    def __init__(self, allowed=True):
        self.allowed, self.calls = allowed, []

    def is_allowed(self, actor, permission, operation):
        self.calls.append((actor.user_id, permission, operation))
        return self.allowed


class Logger:
    def __init__(self, fail=False):
        self.fail, self.started, self.finished = fail, [], []

    def start(self, record):
        if self.fail:
            raise RuntimeError("logging destination unavailable")
        self.started.append(record)

    def finish(self, record):
        if self.fail:
            raise RuntimeError("logging destination unavailable")
        self.finished.append(record)


class PublicService:
    def __init__(self, result=None):
        self.calls, self.result = 0, result

    def get_by_id(self, context, user_id: int):
        self.calls += 1
        return OperationResult.ok(self.result if self.result is not None else user_id)


class UserWriteDouble:
    def __init__(self):
        self.calls = 0

    def create(self, context, data: UserCreateInput):
        self.calls += 1
        return OperationResult.ok(False)


def pipeline(actor=None, permissions=None, logger=None):
    return MiddlewarePipeline(
        ContextMiddleware(Identity(actor), Correlations()),
        ValidationMiddleware(), AuthorizationMiddleware(permissions),
        ErrorMiddleware(), ExecutionLoggingMiddleware(logger or Logger()),
    )
