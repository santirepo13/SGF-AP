"""Reusable HTTP adaptation components for SGF-AP route groups."""

from .adapter import HttpOperation, HttpOperationAdapter, get_http_adapter
from .context import build_execution_context, correlation_id_for_request, get_request_correlation_id
from .inputs import build_contract, read_json_contract, read_json_object
from .responses import error_response, operation_response, to_json_value

__all__ = [
    "HttpOperation",
    "HttpOperationAdapter",
    "build_contract",
    "build_execution_context",
    "correlation_id_for_request",
    "error_response",
    "get_http_adapter",
    "get_request_correlation_id",
    "operation_response",
    "read_json_contract",
    "read_json_object",
    "to_json_value",
]
