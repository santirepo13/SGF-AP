"""Actor, activation and permission checks."""

from api.errors import ApplicationError

from .base import MiddlewareRequest, NextHandler, PermissionChecker
from .operation_policies import OPERATION_POLICIES


class AuthorizationMiddleware:
    def __init__(self, permission_checker: PermissionChecker | None = None) -> None:
        self.permission_checker = permission_checker

    def process(self, request: MiddlewareRequest, next_handler: NextHandler):
        policy = OPERATION_POLICIES[request.operation_name]
        actor = request.context.actor
        if policy.actor_required and actor is None:
            raise ApplicationError.forbidden(request.operation_name, correlation_id=request.context.correlation_id)
        if actor is not None and not actor.active:
            raise ApplicationError.inactive_user(correlation_id=request.context.correlation_id)
        if policy.permission and actor is not None and self.permission_checker is not None:
            if not self.permission_checker.is_allowed(actor, policy.permission, request.operation_name):
                raise ApplicationError.forbidden(request.operation_name, correlation_id=request.context.correlation_id)
        return next_handler(request)
