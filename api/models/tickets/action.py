"""Action persistence model."""

from dataclasses import dataclass

from api.enums import ActionName


@dataclass(frozen=True)
class Action:
    id: int
    name: ActionName
