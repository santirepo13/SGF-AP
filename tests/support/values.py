"""Typed sample inputs shared by repository and service failure cases."""

from dataclasses import MISSING, fields, is_dataclass
from datetime import datetime, timezone
import inspect
from types import UnionType
from typing import Union, get_args, get_origin, get_type_hints


def sample_value(annotation, field_name="", *, nullable_as_none=True):
    arguments = get_args(annotation)
    if get_origin(annotation) in (UnionType, Union):
        choices = [value for value in arguments if value is not type(None)]
        if len(choices) != len(arguments) and (nullable_as_none or field_name.endswith("_id")):
            return None
        return sample_value(choices[0], field_name, nullable_as_none=nullable_as_none)
    if annotation is int:
        return 1
    if annotation is str:
        return "Approval" if field_name in {"decision", "action"} else "x"
    if annotation is bool:
        return True
    if annotation is datetime:
        return datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    if inspect.isclass(annotation) and is_dataclass(annotation):
        hints = get_type_hints(annotation)
        return annotation(**{
            item.name: sample_value(hints[item.name], item.name, nullable_as_none=nullable_as_none)
            for item in fields(annotation)
            if item.default is MISSING and item.default_factory is MISSING
        })
    return None


def repository_arguments(interface, method, *, nullable_as_none=True):
    catalog_names = {
        "RoleRepositoryInterface": "Citizen",
        "PriorityRepositoryInterface": "High",
        "StatusRepositoryInterface": "Registered",
        "ActionRepositoryInterface": "Registration",
    }
    return {
        name: catalog_names.get(interface.__name__, "x")
        if name == "name" and method == "get_by_name"
        else sample_value(annotation, name, nullable_as_none=nullable_as_none)
        for name, annotation in get_type_hints(getattr(interface, method)).items()
        if name != "return"
    }


def service_arguments(interface, method):
    return {
        name: sample_value(annotation, name)
        for name, annotation in get_type_hints(getattr(interface, method)).items()
        if name not in {"context", "return"}
    }
