"""Shared service interface contract."""

from typing import Protocol

from api.contracts import ExecutionContext, OperationResult


class ServiceInterface(Protocol):
    """Application boundary: context in, typed operation result out."""

    # Implementations may coordinate writes through their injected transaction
    # boundary. The interface itself performs no I/O.
