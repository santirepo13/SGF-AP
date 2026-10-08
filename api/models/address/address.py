"""Persistence model for addresses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from api.contracts.common_types import ensure_aware, ensure_length, ensure_range, ensure_uppercase_letter


@dataclass(frozen=True)
class Address:
    """Row from addresses; uniqueness is enforced by the SQL index."""

    id: int
    road_type_code: str
    road_number: int
    road_suffix_letter_code: str | None
    road_bis_code: str | None
    road_bis_suffix: str | None
    road_quadrant_code: int | None
    cross_road_number: int
    cross_suffix_letter_code: str | None
    cross_bis_code: str | None
    cross_bis_suffix: str | None
    cross_quadrant_code: int | None
    door_plate_number: int
    neighborhood_id: int | None
    created_at: datetime

    def __post_init__(self) -> None:
        ensure_length(self.road_type_code, 2, "road_type_code")
        ensure_range(self.road_number, 1, 999, "road_number")
        ensure_range(self.cross_road_number, 1, 999, "cross_road_number")
        ensure_range(self.door_plate_number, 1, 9999, "door_plate_number")
        for name, value, maximum in (
            ("road_suffix_letter_code", self.road_suffix_letter_code, 2),
            ("road_bis_code", self.road_bis_code, 3),
            ("cross_suffix_letter_code", self.cross_suffix_letter_code, 2),
            ("cross_bis_code", self.cross_bis_code, 3),
        ):
            if value is not None:
                ensure_length(value, maximum, name)
        ensure_uppercase_letter(self.road_bis_suffix, "road_bis_suffix")
        ensure_uppercase_letter(self.cross_bis_suffix, "cross_bis_suffix")
        ensure_aware(self.created_at, "created_at")
