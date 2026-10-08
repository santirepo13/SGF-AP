from dataclasses import dataclass


@dataclass(frozen=True)
class CrossBisCode:
    """Row from cross_bis_codes; code is VARCHAR(3) primary key."""

    code: str
