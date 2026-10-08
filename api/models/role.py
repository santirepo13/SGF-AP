"""Role persistence model."""

from dataclasses import dataclass

from api.enums import RoleName


@dataclass(frozen=True)
class Role:
    id: int
    name: RoleName
