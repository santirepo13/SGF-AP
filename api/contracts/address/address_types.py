"""Address input and output contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..common_types import ensure_aware, ensure_length, ensure_range, ensure_uppercase_letter


@dataclass(frozen=True)
class AddressCreateInput:
    road_type_code: str
    road_number: int
    cross_road_number: int
    door_plate_number: int
    road_suffix_letter_code: str | None = None
    road_bis_code: str | None = None
    road_bis_suffix: str | None = None
    road_quadrant_code: int | None = None
    cross_suffix_letter_code: str | None = None
    cross_bis_code: str | None = None
    cross_bis_suffix: str | None = None
    cross_quadrant_code: int | None = None
    neighborhood_id: int | None = None

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


@dataclass(frozen=True)
class AddressComponentsInput(AddressCreateInput):
    """Exact address-component lookup using the database uniqueness semantics."""


@dataclass(frozen=True, kw_only=True)
class AddressOutput(AddressCreateInput):
    id: int
    created_at: datetime

    def __post_init__(self) -> None:
        super().__post_init__()
        ensure_aware(self.created_at, "created_at")
