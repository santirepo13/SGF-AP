"""Common repository interface documentation."""

from typing import Protocol


class RepositoryInterface(Protocol):
    """A persistence boundary.

    Implementations return ``None``, an empty list, or ``False`` for normal
    absence. Persistence failures propagate as the centralized
    ``ApplicationError``; repositories do not commit or roll back.
    """
