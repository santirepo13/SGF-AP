"""S6 method-level service failure cases with injected failing dependencies."""

from dataclasses import MISSING, fields, is_dataclass
from datetime import datetime, timezone
import inspect
from types import UnionType
from typing import Any, get_args, get_origin, get_type_hints

import pytest

from api.contracts import ActorContext, ExecutionContext
from api.errors import ErrorCode
from api.interfaces.services import *
from api.services import *
from tests.test_case_inventory import SERVICE_PAIRS, public_methods


class FailingDependency:
    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise RuntimeError("private service dependency failure")
        return fail


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
        return "Approval" if field_name in {"decision", "action"} else "x"
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


def _service(service_type):
    dependencies = {}
    for name, parameter in inspect.signature(service_type.__init__).parameters.items():
        if name in {"self", "transaction", "authorizer"} or parameter.kind is parameter.VAR_KEYWORD:
            continue
        dependencies[name] = FailingDependency()
    return service_type(**dependencies)


def _arguments(interface, method_name):
    hints = get_type_hints(getattr(interface, method_name))
    return {
        name: _value(annotation, name)
        for name, annotation in hints.items()
        if name not in {"context", "return"}
    }


METHOD_CASES = tuple(
    (f"S6-{index:02d}.E", interface, implementation, method)
    for index, (interface, implementation, method) in enumerate(
        ((interface, implementation, method)
         for interface, implementation in SERVICE_PAIRS
         for method in public_methods(interface)), 1
    )
)


@pytest.mark.parametrize("case_id, interface, implementation, method", METHOD_CASES, ids=[case[0] for case in METHOD_CASES])
def test_each_service_method_returns_a_centralized_failure(case_id, interface, implementation, method):
    service = _service(implementation)
    context = ExecutionContext(
        f"{implementation.__name__}.{method}",
        f"{case_id}-correlation",
        ActorContext(99, 1, True),
    )

    result = getattr(service, method)(context, **_arguments(interface, method))

    assert result.success is False, case_id
    assert result.data is None, case_id
    assert result.error.code == ErrorCode.UNEXPECTED_ERROR.value, case_id
    assert result.error.correlation_id == context.correlation_id, case_id
