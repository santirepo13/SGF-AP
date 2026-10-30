"""HTTP route contract and route-order checks for login."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from api.contracts import UserLoginInput
from api.routes.users.user_routes import router


@dataclass
class RecordingAdapter:
    calls: list[tuple[object, object, object, tuple[object, ...]]] = field(default_factory=list)

    def execute(self, request, operation, service, *arguments):
        self.calls.append((request, operation, service, arguments))
        return operation.name


class JsonRequest:
    def __init__(self, body: bytes) -> None:
        self._body = body
        self.headers = {"content-type": "application/json"}

    async def body(self) -> bytes:
        return self._body


def test_login_static_route_precedes_the_dynamic_user_identifier_route() -> None:
    paths = [route.path for route in router.routes]

    assert paths.index("/users/login") < paths.index("/users/{user_id}")


def test_login_route_adapts_only_email_and_password() -> None:
    endpoint = {route.name: route.endpoint for route in router.routes}["login"]
    adapter = RecordingAdapter()

    result = asyncio.run(
        endpoint(
            request=JsonRequest(b'{"email":"Ana@example.test","password":" exact Password "}'),
            user_service=object(),
            adapter=adapter,
            correlation_id="login-http",
        )
    )

    assert result == "UserService.login"
    _, operation, _, (data,) = adapter.calls[0]
    assert operation.no_store is True
    assert isinstance(data, UserLoginInput)
    assert data.email == "Ana@example.test"
    assert data.password == " exact Password "
