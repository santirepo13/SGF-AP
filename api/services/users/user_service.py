"""User application service, including registration and credential login."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from api.contracts import (
    CitizenRegistrationInput,
    ExecutionContext,
    OperationResult,
    UserActivationInput,
    UserCreateInput,
    UserFilters,
    UserLoginInput,
    UserLoginOutput,
    PasswordRecoveryRequestInput,
    PasswordRecoveryRequestOutput,
    PasswordRecoveryVerifyInput,
    PasswordRecoveryVerifyOutput,
    PasswordResetInput,
    PasswordResetOutput,
    UserOutput,
    UserUpdateInput,
)
from api.errors import ApplicationError, ErrorCode
from api.enums import RoleName
from api.interfaces.repositories import RoleRepositoryInterface, UserRepositoryInterface
from api.interfaces.security import AccessTokenProviderInterface
from api.notifications import PasswordRecoveryNotifier, ResendNotificationError
from api.security import (
    Argon2idPasswordHasher,
    PasswordHasherInterface,
    PasswordRecoveryStore,
    RecoveryProofRejected,
    RecoveryRateLimited,
    role_name_for,
)

from ..base import ServiceBase
from .password_recovery_validation import (
    validate_password_reset,
    validate_recovery_request,
    validate_recovery_verify,
)
from .registration_validation import validate_registration
from .user_validation import validate_login


class UserService(ServiceBase):
    def __init__(
        self,
        users: UserRepositoryInterface,
        roles: RoleRepositoryInterface,
        password_hasher: PasswordHasherInterface | None = None,
        access_token_provider: AccessTokenProviderInterface | None = None,
        password_recovery_store: PasswordRecoveryStore | None = None,
        password_recovery_notifier: PasswordRecoveryNotifier | None = None,
        password_recovery_code_ttl_seconds: int = 600,
        *,
        password_generator: PasswordHasherInterface | None = None,
        hash_generator: PasswordHasherInterface | None = None,
        token_provider: AccessTokenProviderInterface | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.users = users
        self.roles = roles
        # Accept descriptive aliases during composition while retaining one
        # hashing component for registration and verification.
        self.password_hasher = password_hasher or password_generator or hash_generator
        self.password_generator = self.password_hasher
        self.hash_generator = self.password_hasher
        self.access_token_provider = access_token_provider or token_provider
        self.token_provider = self.access_token_provider
        self.password_recovery_store = password_recovery_store
        self.password_recovery_notifier = password_recovery_notifier
        self.password_recovery_code_ttl_seconds = password_recovery_code_ttl_seconds

    @staticmethod
    def _out(value: object, *, role_name: str | None = None) -> UserOutput:
        return UserOutput(
            value.id,
            value.first_name,
            value.last_name,
            value.email,
            value.role_id,
            value.active,
            role_name,
        )

    def _get(self, context: ExecutionContext, value: object) -> UserOutput:
        if value is None:
            raise self._missing("user", context)
        return self._out(value)

    def get_by_id(self, context: ExecutionContext, user_id: int) -> OperationResult[UserOutput]:
        return self._execute(context, context.operation, lambda: self._get(context, self.users.get_by_id(user_id)))

    def get_by_email(self, context: ExecutionContext, email: str) -> OperationResult[UserOutput]:
        return self._execute(context, context.operation, lambda: self._get(context, self.users.get_by_email(email)))

    def list_by_filters(
        self,
        context: ExecutionContext,
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

    def login(
        self,
        context: ExecutionContext,
        data: UserLoginInput,
    ) -> OperationResult[UserLoginOutput]:
        """Authenticate a registered account and issue one opaque access token."""

        def work() -> UserLoginOutput:
            validated = validate_login(data, correlation_id=context.correlation_id)
            user = self.users.get_by_email(validated.email)
            if user is None:
                raise ApplicationError.with_code(
                    ErrorCode.INVALID_CREDENTIALS,
                    correlation_id=context.correlation_id,
                )
            if not self._verify_password(user.password_hash, validated.password):
                raise ApplicationError.with_code(
                    ErrorCode.INVALID_CREDENTIALS,
                    correlation_id=context.correlation_id,
                )
            if not user.active:
                raise ApplicationError.inactive_user(correlation_id=context.correlation_id)
            role = self.roles.get_by_id(user.role_id)
            public_role_name = role_name_for(role)
            if public_role_name is None or getattr(role, "id", None) != user.role_id:
                raise ApplicationError.catalog_unavailable("role", correlation_id=context.correlation_id)
            issued = self._issue_access_token(user.id, user.auth_version)
            return UserLoginOutput(
                user=self._out(user, role_name=public_role_name),
                access_token=issued.access_token,
                expires_at=issued.expires_at,
            )

        return self._execute(context, context.operation, work, actor_required=False)

    def request_password_recovery(
        self,
        context: ExecutionContext,
        data: PasswordRecoveryRequestInput,
    ) -> OperationResult[PasswordRecoveryRequestOutput]:
        """Accept a privacy-preserving recovery request and send one code when possible."""

        def work() -> PasswordRecoveryRequestOutput:
            validated = validate_recovery_request(data, correlation_id=context.correlation_id)
            store, notifier = self._recovery_components(context)
            user = self.users.get_by_email(validated.email)
            try:
                challenge, code = store.begin(
                    user_id=None if user is None else user.id,
                    email=validated.email,
                )
            except RecoveryRateLimited as error:
                raise ApplicationError.with_code(
                    ErrorCode.RECOVERY_RATE_LIMITED,
                    correlation_id=context.correlation_id,
                    cause=error,
                ) from error
            if user is not None:
                try:
                    notifier.send_code(
                        recipient=user.email,
                        request_id=challenge.request_id,
                        code=code,
                        expires_in_minutes=max(1, self.password_recovery_code_ttl_seconds // 60),
                    )
                except ResendNotificationError:
                    # Keep the public answer uniform. A later request can create
                    # a fresh proof after the configured wait.
                    pass
            return PasswordRecoveryRequestOutput(
                request_id=challenge.request_id,
                message="Si el correo corresponde a una cuenta, recibirás un código para introducir en la aplicación.",
            )

        return self._execute(context, context.operation, work, actor_required=False)

    def verify_password_recovery(
        self,
        context: ExecutionContext,
        data: PasswordRecoveryVerifyInput,
    ) -> OperationResult[PasswordRecoveryVerifyOutput]:
        def work() -> PasswordRecoveryVerifyOutput:
            validated = validate_recovery_verify(data, correlation_id=context.correlation_id)
            store, _ = self._recovery_components(context)
            try:
                reset_token, expires_at = store.verify(request_id=validated.request_id, code=validated.code)
            except RecoveryRateLimited as error:
                raise ApplicationError.with_code(ErrorCode.RECOVERY_RATE_LIMITED, correlation_id=context.correlation_id, cause=error) from error
            except RecoveryProofRejected as error:
                raise ApplicationError.with_code(ErrorCode.RECOVERY_PROOF_REJECTED, correlation_id=context.correlation_id, cause=error) from error
            return PasswordRecoveryVerifyOutput(reset_token=reset_token, expires_at=expires_at)

        return self._execute(context, context.operation, work, actor_required=False)

    def complete_password_recovery(
        self,
        context: ExecutionContext,
        data: PasswordResetInput,
    ) -> OperationResult[PasswordResetOutput]:
        """Replace the password once and advance its access-token revision."""

        def work() -> PasswordResetOutput:
            validated = validate_password_reset(data, correlation_id=context.correlation_id)
            store, notifier = self._recovery_components(context)
            try:
                recovery_id, user_id = store.claim_reset(validated.reset_token)
            except RecoveryProofRejected as error:
                raise ApplicationError.with_code(ErrorCode.RECOVERY_PROOF_REJECTED, correlation_id=context.correlation_id, cause=error) from error
            try:
                user = self.users.get_by_id(user_id)
                if user is None:
                    raise ApplicationError.with_code(ErrorCode.RECOVERY_PROOF_REJECTED, correlation_id=context.correlation_id)
                updated = self.users.replace_password(user_id, self._hash_password(validated.new_password))
                if updated is None:
                    raise ApplicationError.with_code(ErrorCode.RECOVERY_PROOF_REJECTED, correlation_id=context.correlation_id)
                if self.transaction is not None:
                    self.transaction.commit()
            except BaseException:
                if self.transaction is not None:
                    try:
                        self.transaction.rollback()
                    except BaseException:
                        pass
                store.finish_reset(recovery_id, completed=False)
                raise
            store.finish_reset(recovery_id, completed=True)
            try:
                notifier.send_password_changed(recipient=updated.email, recovery_id=recovery_id)
            except ResendNotificationError:
                pass
            return PasswordResetOutput(completed_at=datetime.now(timezone.utc))

        return self._execute(context, context.operation, work, actor_required=False)

    def get_current_user(self, context: ExecutionContext) -> OperationResult[UserOutput]:
        """Return the public account snapshot already resolved for this request."""

        def work() -> UserOutput:
            actor = context.actor
            if actor is None:
                raise ApplicationError.access_token_required(correlation_id=context.correlation_id)
            if actor.public_user is not None:
                return actor.public_user
            # Direct service callers can still provide only an ActorContext;
            # HTTP requests receive the snapshot from TokenIdentityProvider and
            # therefore do not query the account or role a second time.
            user = self.users.get_by_id(actor.user_id)
            if user is None:
                raise ApplicationError.invalid_access_token(correlation_id=context.correlation_id)
            role = self.roles.get_by_id(user.role_id)
            role_name = role_name_for(role)
            if role_name is None or getattr(role, "id", None) != user.role_id:
                raise ApplicationError.catalog_unavailable("role", correlation_id=context.correlation_id)
            return self._out(user, role_name=role_name)

        return self._execute(context, context.operation, work, actor_required=True)

    def create(self, context: ExecutionContext, data: UserCreateInput) -> OperationResult[UserOutput]:
        def work() -> UserOutput:
            if self.roles.get_by_id(data.role_id) is None:
                raise self._missing("role", context)
            return self._get(context, self.users.create(data))

        return self._execute(context, context.operation, work, write=True, actor_required=True)

    def update(self, context: ExecutionContext, data: UserUpdateInput) -> OperationResult[UserOutput]:
        return self._execute(
            context,
            context.operation,
            lambda: self._get(context, self.users.update(data)),
            write=True,
            actor_required=True,
        )

    def set_active(self, context: ExecutionContext, data: UserActivationInput) -> OperationResult[UserOutput]:
        return self._execute(
            context,
            context.operation,
            lambda: self._get(context, self.users.set_active(data)),
            write=True,
            actor_required=True,
        )

    def _recovery_components(self, context: ExecutionContext) -> tuple[PasswordRecoveryStore, PasswordRecoveryNotifier]:
        if self.password_recovery_store is None or self.password_recovery_notifier is None:
            raise ApplicationError.with_code(ErrorCode.RECOVERY_UNAVAILABLE, correlation_id=context.correlation_id)
        return self.password_recovery_store, self.password_recovery_notifier

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

    def _verify_password(self, password_hash: str, password: str) -> bool:
        component = self.password_hasher
        if component is None:
            component = Argon2idPasswordHasher()
            self.password_hasher = component
            self.password_generator = component
            self.hash_generator = component
        for method_name in ("verify_password", "verify"):
            method = getattr(component, method_name, None)
            if callable(method):
                result = method(password_hash, password)
                if type(result) is not bool:
                    raise RuntimeError("password verification component returned an invalid result")
                return result
        raise TypeError("password verification component is not callable")

    def _issue_access_token(self, user_id: int, auth_version: int = 1):
        provider = self.access_token_provider
        if provider is None:
            raise RuntimeError("access-token provider is not configured")
        issued = provider.issue(user_id, auth_version)
        token = getattr(issued, "access_token", None)
        expires_at = getattr(issued, "expires_at", None)
        if type(token) is not str or not token or expires_at is None:
            raise RuntimeError("access-token provider returned an invalid result")
        return issued
