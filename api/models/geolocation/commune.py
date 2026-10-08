"""Model for communes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Commune:
    """Row from communes, including its municipality reference."""

    id: int
    number: int
    name: str | None
    municipality_id: int
