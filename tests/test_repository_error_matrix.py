"""R4 method-level induced failure cases."""

from dataclasses import MISSING, fields, is_dataclass
from datetime import datetime, timezone
import inspect
from types import UnionType
from typing import Any, get_args, get_origin, get_type_hints

import pytest

from api.contracts import *
from api.errors import ApplicationError, ErrorCode
from api.interfaces.repositories import *
from api.repositories import *
from tests.test_case_inventory import REPOSITORY_PAIRS, public_methods


class FailingCursor:
    description = None
    rowcount = 0

    def execute(self, query, params=()):
        raise RuntimeError("private query parameter and password=secret")

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        pass


class FailingConnection:
    def cursor(self):
        return FailingCursor()


def _value(annotation: Any, field_name: str = ""):
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (UnionType,):
        non_none = [item for item in args if item is not type(None)]
        return None if len(non_none) != len(args) and field_name.endswith("_id") else _value(non_none[0], field_name)
    if annotation is int:
        return 1
    if annotation is str:
        return "x"
    if annotation is bool:
        return True
    if annotation is datetime:
        return datetime.now(timezone.utc)
    if inspect.isclass(annotation) and is_dataclass(annotation):
        values = {}
        hints = get_type_hints(annotation)
        for field in fields(annotation):
            if field.default is not MISSING:
                continue
            if field.default_factory is not MISSING:
                continue
            values[field.name] = _value(hints[field.name], field.name)
        return annotation(**values)
    return None


def _arguments(interface, method_name):
    hints = get_type_hints(getattr(interface, method_name))
    values = {}
    for name, annotation in hints.items():
        if name == "return":
            continue
        if name == "name" and method_name == "get_by_name":
            values[name] = {
                "RoleRepositoryInterface": "Citizen",
                "PriorityRepositoryInterface": "High",
                "StatusRepositoryInterface": "Registered",
                "ActionRepositoryInterface": "Registration",
            }.get(interface.__name__, "x")
        else:
            values[name] = _value(annotation, name)
    return values


METHOD_CASES = tuple(
    (f"R4-{index:02d}.E", interface, implementation, method)
    for index, (interface, implementation, method) in enumerate(
        ((interface, implementation, method)
         for interface, implementation in REPOSITORY_PAIRS
         for method in public_methods(interface)), 1
    )
)


@pytest.mark.parametrize("case_id, interface, implementation, method", METHOD_CASES, ids=[case[0] for case in METHOD_CASES])
def test_each_repository_method_translates_technical_failures(case_id, interface, implementation, method):
    repository = implementation(FailingConnection())
    arguments = _arguments(interface, method)

    with pytest.raises(ApplicationError) as caught:
        getattr(repository, method)(**arguments)

    assert caught.value.code in {ErrorCode.UNEXPECTED_ERROR, ErrorCode.PERSISTENCE_FAILURE}, case_id
    assert caught.value.cause is not None
