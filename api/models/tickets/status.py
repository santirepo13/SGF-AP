"""Status persistence model."""

from dataclasses import dataclass

from api.enums import StatusName


@dataclass(frozen=True)
class Status:
    id: int
    name: StatusName
