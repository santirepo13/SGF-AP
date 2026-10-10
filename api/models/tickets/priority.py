"""Priority persistence model."""

from dataclasses import dataclass

from api.enums import PriorityName


@dataclass(frozen=True)
class Priority:
    id: int
    name: PriorityName
