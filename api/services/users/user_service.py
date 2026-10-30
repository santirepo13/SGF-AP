"""User application service, including citizen registration."""

from __future__ import annotations

from typing import Any

from api.contracts import (
    CitizenRegistrationInput,
    ExecutionContext,
    OperationResult,
    UserActivationInput,
    UserCreateInput,
    UserFilters,
    UserOutput,
    UserUpdateInput,
)
from api.errors import ApplicationError
from api.enums import RoleName
from api.interfaces.repositories import RoleRepositoryInterface, UserRepositoryInterface
from api.security import Argon2idPasswordHasher, PasswordHasherInterface

from ..base import ServiceBase
from .registration_validation import validate_registration


class UserService(ServiceBase):
    def __init__(
        self,
        users: UserRepositoryInterface,
        roles: RoleRepositoryInterface,
        password_hasher: PasswordHasherInterface | None = None,
        *,
        password_generator: PasswordHasherInterface | None = None,
        hash_generator: PasswordHasherInterface | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.users = users
        self.roles = roles
        # Accept the descriptive aliases during composition while retaining a
        # single component for the service operation.
        self.password_hasher = password_hasher or password_generator or hash_generator
        self.password_generator = self.password_hasher
        self.hash_generator = self.password_hasher

    @staticmethod
    def _out(value):
        return UserOutput(value.id, value.first_name, value.last_name, value.email, value.role_id, value.active)

    def _get(self, context, value):
        if value is None:
            raise self._missing("user", context)
        return self._out(value)

    def get_by_id(self, context, user_id: int) -> OperationResult[UserOutput]:
        return self._execute(context, context.operation, lambda: self._get(context, self.users.get_by_id(user_id)))

    def get_by_email(self, context, email: str) -> OperationResult[UserOutput]:
        return self._execute(context, context.operation, lambda: self._get(context, self.users.get_by_email(email)))

    def list_by_filters(
        self,
        context,
        filters: UserFilters | None = None,
    ) -> OperationResult[list[UserOutput]]:
        return self._execute(
            context,
            context.operation,
            lambda: [self._out(value) for value in self.users.list_by_filters(filters)],
        )

    def register_citizen(
        self,
        context: ExecutionContext,
        data: CitizenRegistrationInput,
    ) -> OperationResult[UserOutput]:
        """Create an active citizen without requiring an authenticated actor."""

        def work() -> UserOutput:
            validated = validate_registration(data, correlation_id=context.correlation_id)
            role = self.roles.get_by_name(RoleName.CITIZEN.value)
            if role is None:
                raise ApplicationError.catalog_unavailable(
                    "Citizen",
                    correlation_id=context.correlation_id,
                )
            password_hash = self._hash_password(validated.password)
            create_data = UserCreateInput(
                first_name=validated.first_name,
                last_name=validated.last_name,
                email=validated.email,
                password_hash=password_hash,
                role_id=role.id,
                active=True,
            )
            return self._get(context, self.users.create(create_data))

        return self._execute(context, context.operation, work, write=True, actor_required=False)

    def create(self, context, data: UserCreateInput) -> OperationResult[UserOutput]:
        def work():
            if self.roles.get_by_id(data.role_id) is None:
                raise self._missing("role", context)
            return self._get(context, self.users.create(data))

        return self._execute(context, context.operation, work, write=True, actor_required=True)

    def update(self, context, data: UserUpdateInput) -> OperationResult[UserOutput]:
        return self._execute(
            context,
            context.operation,
            lambda: self._get(context, self.users.update(data)),
            write=True,
            actor_required=True,
        )

    def set_active(self, context, data: UserActivationInput) -> OperationResult[UserOutput]:
        return self._execute(
            context,
            context.operation,
            lambda: self._get(context, self.users.set_active(data)),
            write=True,
            actor_required=True,
        )

    def _hash_password(self, password: str) -> str:
        component = self.password_hasher
        if component is None:
            component = Argon2idPasswordHasher()
            self.password_hasher = component
            self.password_generator = component
            self.hash_generator = component

        for method_name in ("hash", "generate_hash", "generate"):
            method = getattr(component, method_name, None)
            if callable(method):
                result = method(password)
                if not isinstance(result, str) or not result:
                    raise RuntimeError("password hash component returned an invalid result")
                return result
        if callable(component):
            result = component(password)
            if not isinstance(result, str) or not result:
                raise RuntimeError("password hash component returned an invalid result")
            return result
        raise TypeError("password hash component is not callable")
