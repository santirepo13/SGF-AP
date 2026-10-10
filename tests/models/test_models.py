"""Persistence models and individually identified enum conversions."""

if __name__ == "__main__":
    # Direct execution hands this file to pytest so its fixtures and assertions run.
    import sys
    from pathlib import Path
    import pytest

    project_root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pytest.ini").is_file())
    sys.path.insert(0, str(project_root))
    raise SystemExit(pytest.main([__file__, *sys.argv[1:]]))

from datetime import datetime, timezone
from dataclasses import fields

import pytest

from api.enums import ActionName, PriorityName, RoleName, StatusName
from api.models import (
    Action,
    Address,
    Commune,
    Crew,
    CrewMember,
    CrossBisCode,
    CrossQuadrant,
    CrossSuffixLetter,
    Evidence,
    FailureType,
    HistoryEvent,
    Municipality,
    Neighborhood,
    Priority,
    RoadBisCode,
    RoadQuadrant,
    RoadSuffixLetter,
    RoadType,
    Role,
    Status,
    Ticket,
    User,
)


UTC = timezone.utc


def test_all_22_models_are_constructible() -> None:
    """Construct every data model with representative valid values."""
    now = datetime.now(UTC)
    instances = (
        Municipality(1, "Medellín"),
        Commune(1, 1, "Popular", 1),
        Neighborhood(1, "Centro", 1, None),
        RoadType("CL", "Calle"),
        RoadSuffixLetter("A"),
        RoadBisCode("BIS"),
        RoadQuadrant(1, "Sur"),
        CrossSuffixLetter("A"),
        CrossBisCode("BIS"),
        CrossQuadrant(2, "Este"),
        Address(1, "CL", 10, None, None, None, None, 20, None, None, None, None, 30, None, now),
        Role(1, RoleName.CITIZEN),
        User(1, "Ana", "Gómez", "ana@example.test", "hash", 1, False),
        Crew(1, "Cuadrilla A"),
        CrewMember(1, 1),
        Priority(1, PriorityName.HIGH),
        FailureType(1, "Exposed cable", 1),
        Status(1, StatusName.REGISTERED),
        Action(1, ActionName.REGISTRATION),
        Ticket(1, "T-1", 1, 1, "Falla", None, 1, None, None, None, None, None, None, now),
        Evidence(1, 1, "/tmp/evidence.jpg", now, 1),
        HistoryEvent(1, 1, None, 1, now),
    )
    assert len(instances) == 22

def test_model_fields_match_address_table() -> None:
    """Compare the address model's field order with its database columns."""
    assert [field.name for field in fields(Address)] == [
        "id", "road_type_code", "road_number", "road_suffix_letter_code",
        "road_bis_code", "road_bis_suffix", "road_quadrant_code",
        "cross_road_number", "cross_suffix_letter_code", "cross_bis_code",
        "cross_bis_suffix", "cross_quadrant_code", "door_plate_number",
        "neighborhood_id", "created_at",
    ]

def test_nullable_relationships_are_preserved() -> None:
    """Keep optional links absent in neighborhood, ticket, and history records."""
    assert Neighborhood(1, "Centro", 1, None).commune_id is None
    assert Ticket(1, "T-1", 1, 1, "Falla", None, 1, None, None, None, None, None, None, datetime.now(UTC)).address_id is None
    assert HistoryEvent(1, 1, None, 1, datetime.now(UTC)).user_id is None

def test_enum_rejects_unknown_sql_value() -> None:
    """Reject a stored role name that is not part of the allowed values."""
    with pytest.raises(ValueError, match="RoleName"):
        RoleName.from_sql("Unknown")

def test_models_require_timezone_aware_dates() -> None:
    """Reject a ticket timestamp that lacks a time zone."""
    with pytest.raises(ValueError):
        Ticket(1, "T-1", 1, 1, "Falla", None, 1, None, None, None, None, None, None, datetime.now())


@pytest.mark.parametrize(
    "enum_type, value",
    [(enum_type, member.value) for enum_type in (RoleName, PriorityName, StatusName, ActionName) for member in enum_type],
    ids=[f"{enum_type.__name__}.{value}" for enum_type, value in [(enum_type, member.value) for enum_type in (RoleName, PriorityName, StatusName, ActionName) for member in enum_type]],
)
def test_enum_sql_round_trip_is_individual(enum_type, value):
    """Read and write each catalogue value without changing it."""
    assert enum_type.from_sql(value).to_sql() == value
