from dataclasses import dataclass


@dataclass(frozen=True)
class RoadQuadrant:
    """Row from road_quadrants; code is an integer primary key."""

    code: int
    name: str
