"""User-output behavior and centralized failures for all service methods."""

if __name__ == "__main__":
    # Direct execution hands this file to pytest so its fixtures and assertions run.
    import sys
    from pathlib import Path
    import pytest

    project_root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pytest.ini").is_file())
    sys.path.insert(0, str(project_root))
    raise SystemExit(pytest.main([__file__, *sys.argv[1:]]))

import inspect
from types import SimpleNamespace

import pytest

from api.contracts import ActorContext, CrewMemberInput, CrewUpdateInput, ExecutionContext, UserUpdateInput
from api.errors import ErrorCode
from api.models import User
from api.services.users.crew_service import CrewService
from api.services.users.user_service import UserService
from tests.support.component_catalog import SERVICE_PAIRS, method_cases
from tests.support.doubles import FailingDependency
from tests.support.values import service_arguments


METHOD_CASES = method_cases(SERVICE_PAIRS, "S6", "E")


class Users:
    """Provide one known user to the service without a real database."""
    def __init__(self, value):
        """Keep the user returned by every lookup method."""
        self.value = value

    def get_by_id(self, user_id):
        """Return the known user for an identifier lookup."""
        return self.value

    def get_by_email(self, email):
        """Return the known user for an email lookup."""
        return self.value

    def list_by_filters(self, filters=None):
        """Return the known user in a filtered list."""
        return [self.value]


class Roles:
    """Provide the role name needed to build a public user response."""
    def get_by_id(self, role_id):
        """Return the known role for the requested identifier."""
        return SimpleNamespace(id=role_id, name="Citizen")


def test_user_service_uses_injected_repository_and_excludes_password_hash():
    """Read a user through injected dependencies and hide the password hash."""
    user = User(1, "Ada", "Lovelace", "ada@example.com", "secret-hash", 2, False)
    service = UserService(Users(user), Roles())
    result = service.get_by_id(ExecutionContext("get_user", "corr-1"), 1)

    assert result.success
    assert result.data.email == "ada@example.com"
    assert result.data.active is False
    assert not hasattr(result.data, "password_hash")


def test_user_update_of_an_unknown_user_returns_resource_not_found():
    """An update cannot report success when its target user does not exist."""

    class MissingUsers:
        def update(self, data):
            return None

    service = UserService(MissingUsers(), Roles())
    context = ExecutionContext("UserService.update", "corr-update", ActorContext(99, 1, True))

    result = service.update(context, UserUpdateInput(user_id=404))

    assert result.success is False
    assert result.error is not None
    assert result.error.code == ErrorCode.RESOURCE_NOT_FOUND.value
    assert result.error.correlation_id == "corr-update"


def test_crew_update_and_membership_change_of_unknown_records_return_resource_not_found():
    """Crew maintenance must not convert an absent target into successful null data."""

    class MissingCrews:
        def update(self, data):
            return None

    class MissingMembers:
        def update_crew(self, user_id, crew_id):
            return None

    service = CrewService(MissingCrews(), MissingMembers(), object())
    context = ExecutionContext("CrewService.update", "corr-crew-update", ActorContext(99, 1, True))

    crew_result = service.update(context, CrewUpdateInput(crew_id=404, name="Unknown crew"))
    membership_context = ExecutionContext("CrewService.change_crew", "corr-membership-change", ActorContext(99, 1, True))
    membership_result = service.change_crew(membership_context, CrewMemberInput(user_id=404, crew_id=5))

    assert crew_result.success is False
    assert crew_result.error is not None
    assert crew_result.error.code == ErrorCode.RESOURCE_NOT_FOUND.value
    assert membership_result.success is False
    assert membership_result.error is not None
    assert membership_result.error.code == ErrorCode.RESOURCE_NOT_FOUND.value


def _service(service_type):
    """Construct a service whose external dependencies always fail."""
    dependencies = {}
    for name, parameter in inspect.signature(service_type.__init__).parameters.items():
        if name in {"self", "transaction", "authorizer"} or parameter.kind is parameter.VAR_KEYWORD:
            continue
        dependencies[name] = FailingDependency()
    return service_type(**dependencies)


@pytest.mark.parametrize("case_id, interface, implementation, method", METHOD_CASES, ids=[case[0] for case in METHOD_CASES])
def test_each_service_method_returns_a_centralized_failure(case_id, interface, implementation, method):
    """Run every service method with failing dependencies and inspect its error."""
    # A unique request reference lets the assertion detect lost correlation.
    service = _service(implementation)
    context = ExecutionContext(
        f"{implementation.__name__}.{method}",
        f"{case_id}-correlation",
        ActorContext(99, 1, True),
    )

    result = getattr(service, method)(context, **service_arguments(interface, method))

    assert result.success is False, case_id
    assert result.data is None, case_id
    assert result.error.code == ErrorCode.UNEXPECTED_ERROR.value, case_id
    assert result.error.correlation_id == context.correlation_id, case_id
