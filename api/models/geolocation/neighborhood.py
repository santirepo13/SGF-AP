"""Model for neighborhoods."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Neighborhood:
    """Row from neighborhoods; commune_id may be absent."""

    id: int
    name: str
    municipality_id: int
    commune_id: int | None
