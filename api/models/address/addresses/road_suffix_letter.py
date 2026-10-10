from dataclasses import dataclass


@dataclass(frozen=True)
class RoadSuffixLetter:
    """Row from road_suffix_letters; code is VARCHAR(2) primary key."""

    code: str
