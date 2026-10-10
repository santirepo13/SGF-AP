from dataclasses import dataclass


@dataclass(frozen=True)
class RoadType:
    """Row from road_types; code is VARCHAR(2) primary key."""

    code: str
    name: str
