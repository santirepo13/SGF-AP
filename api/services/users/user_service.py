from api.contracts import OperationResult, UserActivationInput, UserCreateInput, UserFilters, UserOutput, UserUpdateInput
from api.interfaces.repositories import RoleRepositoryInterface, UserRepositoryInterface
from ..base import ServiceBase

class UserService(ServiceBase):
    def __init__(self, users: UserRepositoryInterface, roles: RoleRepositoryInterface, **kwargs): super().__init__(**kwargs); self.users, self.roles = users, roles
    @staticmethod
    def _out(value): return UserOutput(value.id, value.first_name, value.last_name, value.email, value.role_id, value.active)
    def _get(self, context, value):
        if value is None: raise self._missing("user", context)
        return self._out(value)
    def get_by_id(self, context, user_id: int) -> OperationResult[UserOutput]: return self._execute(context, context.operation, lambda: self._get(context, self.users.get_by_id(user_id)))
    def get_by_email(self, context, email: str) -> OperationResult[UserOutput]: return self._execute(context, context.operation, lambda: self._get(context, self.users.get_by_email(email)))
    def list_by_filters(self, context, filters: UserFilters | None = None) -> OperationResult[list[UserOutput]]: return self._execute(context, context.operation, lambda: [self._out(x) for x in self.users.list_by_filters(filters)])
    def create(self, context, data: UserCreateInput) -> OperationResult[UserOutput]:
        def work():
            if self.roles.get_by_id(data.role_id) is None: raise self._missing("role", context)
            return self._get(context, self.users.create(data))
        return self._execute(context, context.operation, work, write=True, actor_required=True)
    def update(self, context, data: UserUpdateInput) -> OperationResult[UserOutput]: return self._execute(context, context.operation, lambda: self._out(value) if (value := self.users.update(data)) else None, write=True, actor_required=True)
    def set_active(self, context, data: UserActivationInput) -> OperationResult[UserOutput]: return self._execute(context, context.operation, lambda: self._get(context, self.users.set_active(data)), write=True, actor_required=True)
