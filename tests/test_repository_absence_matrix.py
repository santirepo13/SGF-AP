"""R4 absence and empty-list cases for every applicable repository method."""

from dataclasses import MISSING, fields, is_dataclass
from datetime import datetime, timezone
import inspect
from types import UnionType
from typing import Any, get_args, get_origin, get_type_hints

import pytest

from api.contracts import *
from api.interfaces.repositories import *
from api.repositories import *
from tests.test_case_inventory import REPOSITORY_PAIRS, public_methods


class EmptyCursor:
    description = None
    rowcount = 0

    def execute(self, query, params=()):
        self.query, self.params = query, tuple(params)

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        pass


class EmptyConnection:
    def __init__(self):
        self.last_cursor = None

    def cursor(self):
        self.last_cursor = EmptyCursor()
        return self.last_cursor


def _value(annotation: Any, field_name: str = ""):
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (UnionType,):
        non_none = [item for item in args if item is not type(None)]
        if len(non_none) != len(args):
            return None
        return _value(non_none[0], field_name)
    if annotation is int:
        return 1
    if annotation is str:
        return "Citizen" if field_name == "name" else "x"
    if annotation is bool:
        return True
    if annotation is datetime:
        return datetime.now(timezone.utc)
    if inspect.isclass(annotation) and is_dataclass(annotation):
        hints = get_type_hints(annotation)
        values = {}
        for field in fields(annotation):
            if field.default is not MISSING or field.default_factory is not MISSING:
                continue
            values[field.name] = _value(hints[field.name], field.name)
        return annotation(**values)
    return None


def _arguments(interface, method_name):
    values = {}
    for name, annotation in get_type_hints(getattr(interface, method_name)).items():
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


ABSENCE_CASES = tuple(
    (f"R4-{index:02d}.N", interface, implementation, method)
    for index, (interface, implementation, method) in enumerate(
        ((interface, implementation, method)
         for interface, implementation in REPOSITORY_PAIRS
         for method in public_methods(interface)
         if method not in {"create"}), 1
    )
)


@pytest.mark.parametrize("case_id, interface, implementation, method", ABSENCE_CASES, ids=[case[0] for case in ABSENCE_CASES])
def test_repository_absence_cases_return_none_empty_or_false(case_id, interface, implementation, method):
    connection = EmptyConnection()
    result = getattr(implementation(connection), method)(**_arguments(interface, method))
    if method.startswith("list"):
        assert result == [], case_id
    elif method == "remove":
        assert result is False, case_id
    else:
        assert result is None, case_id
