"""Conversion of HTTP path, query, and JSON values into input contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import MISSING, fields, is_dataclass
from datetime import datetime
from enum import Enum
import json
from types import UnionType
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints

from fastapi import Request

from api.contracts import UNSET
from api.errors import ApplicationError

T = TypeVar("T")


async def read_json_contract(
    request: Request,
    contract_type: type[T],
    *,
    path_values: Mapping[str, object] | None = None,
    query_values: Mapping[str, object] | None = None,
    correlation_id: str | None = None,
) -> T:
    """Read one JSON object and combine it with typed path/query values."""

    body_values = await read_json_object(request, correlation_id=correlation_id)
    return build_contract(
        contract_type,
        body_values,
        path_values=path_values,
        query_values=query_values,
        correlation_id=correlation_id,
    )


async def read_json_object(request: Request, *, correlation_id: str | None = None) -> dict[str, object]:
    """Read a JSON object while translating malformed transport data safely."""

    body = await request.body()
    if not body:
        return {}
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApplicationError.invalid_value(
            None,
            "El cuerpo de la solicitud debe contener JSON válido.",
            correlation_id=correlation_id,
            cause=exc,
        ) from exc
    if not isinstance(value, dict):
        raise ApplicationError.invalid_value(
            None,
            "El cuerpo de la solicitud debe ser un objeto JSON.",
            correlation_id=correlation_id,
        )
    return value


def build_contract(
    contract_type: type[T],
    body_values: Mapping[str, object] | None = None,
    *,
    path_values: Mapping[str, object] | None = None,
    query_values: Mapping[str, object] | None = None,
    correlation_id: str | None = None,
) -> T:
    """Build a dataclass contract without losing omitted, null, false, or zero values."""

    if not is_dataclass(contract_type):
        raise TypeError("contract_type must be a dataclass type")

    contract_fields = {field.name: field for field in fields(contract_type)}
    supplied = _combine_sources(body_values, path_values, query_values)
    unexpected = set(supplied) - set(contract_fields)
    if unexpected:
        field = sorted(unexpected)[0]
        raise ApplicationError.invalid_value(
            field,
            "El campo no corresponde con el contrato de la operación.",
            correlation_id=correlation_id,
        )

    annotations = get_type_hints(contract_type)
    arguments: dict[str, object] = {}
    for name, field in contract_fields.items():
        if name not in supplied:
            if field.default is not MISSING or field.default_factory is not MISSING:
                continue
            raise ApplicationError.required_field(name, correlation_id=correlation_id)

        raw_value, from_text = supplied[name]
        if raw_value is None:
            if _allows_none(annotations.get(name, Any)):
                arguments[name] = None
                continue
            raise ApplicationError.required_field(name, correlation_id=correlation_id)
        try:
            arguments[name] = _convert_value(raw_value, annotations.get(name, Any), from_text=from_text)
        except (TypeError, ValueError) as exc:
            raise ApplicationError.invalid_value(
                name,
                "El valor no corresponde con el tipo o formato requerido.",
                correlation_id=correlation_id,
                cause=exc,
            ) from exc

    try:
        return contract_type(**arguments)
    except ApplicationError:
        raise
    except (TypeError, ValueError) as exc:
        raise ApplicationError.invalid_value(
            None,
            "Los datos no cumplen las reglas del contrato de la operación.",
            correlation_id=correlation_id,
            cause=exc,
        ) from exc


def _combine_sources(
    body_values: Mapping[str, object] | None,
    path_values: Mapping[str, object] | None,
    query_values: Mapping[str, object] | None,
) -> dict[str, tuple[object, bool]]:
    """Merge sources with path/query values treated as textual transport values."""

    combined: dict[str, tuple[object, bool]] = {}
    for values, from_text in (
        (body_values, False),
        (query_values, True),
        (path_values, True),
    ):
        if values is not None:
            combined.update({name: (value, from_text) for name, value in values.items()})
    return combined


def _convert_value(value: object, annotation: object, *, from_text: bool) -> object:
    if annotation is Any:
        return value
    if value is None:
        if _allows_none(annotation):
            return None
        raise ValueError("null is not allowed")

    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        options = tuple(option for option in get_args(annotation) if option is not type(None))
        for option in options:
            if option is type(UNSET):
                continue
            try:
                return _convert_value(value, option, from_text=from_text)
            except (TypeError, ValueError):
                continue
        raise ValueError("value does not match any allowed type")

    if annotation is str:
        if isinstance(value, str):
            return value
        raise TypeError("expected a string")
    if annotation is bool:
        if isinstance(value, bool):
            return value
        if from_text and isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == "true":
                return True
            if normalized == "false":
                return False
        raise TypeError("expected a boolean")
    if annotation is int:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if from_text and isinstance(value, str):
            return int(value)
        raise TypeError("expected an integer")
    if annotation is float:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if from_text and isinstance(value, str):
            return float(value)
        raise TypeError("expected a number")
    if annotation is datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        raise TypeError("expected an ISO 8601 date and time")
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        if isinstance(value, annotation):
            return value
        try:
            return annotation(value)
        except ValueError as exc:
            raise ValueError("unknown enumeration value") from exc
    if origin is list:
        if not isinstance(value, list):
            raise TypeError("expected an array")
        return [_convert_value(item, get_args(annotation)[0], from_text=from_text) for item in value]
    if origin is tuple:
        if not isinstance(value, (list, tuple)):
            raise TypeError("expected an array")
        arguments = get_args(annotation)
        if len(arguments) == 2 and arguments[1] is Ellipsis:
            return tuple(_convert_value(item, arguments[0], from_text=from_text) for item in value)
        if len(value) != len(arguments):
            raise ValueError("tuple length does not match")
        return tuple(_convert_value(item, expected, from_text=from_text) for item, expected in zip(value, arguments, strict=True))
    if origin is dict:
        if not isinstance(value, dict):
            raise TypeError("expected an object")
        key_type, value_type = get_args(annotation)
        return {
            _convert_value(key, key_type, from_text=from_text): _convert_value(item, value_type, from_text=from_text)
            for key, item in value.items()
        }
    if isinstance(annotation, type) and isinstance(value, annotation):
        return value
    raise TypeError("unsupported contract field type")


def _allows_none(annotation: object) -> bool:
    origin = get_origin(annotation)
    return origin in (Union, UnionType) and type(None) in get_args(annotation)
