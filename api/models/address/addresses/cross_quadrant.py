from dataclasses import dataclass


@dataclass(frozen=True)
class CrossQuadrant:
    """Row from cross_quadrants; code is an integer primary key."""

    code: int
    name: str
