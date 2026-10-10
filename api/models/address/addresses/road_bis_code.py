from dataclasses import dataclass


@dataclass(frozen=True)
class RoadBisCode:
    """Row from road_bis_codes; code is VARCHAR(3) primary key."""

    code: str
