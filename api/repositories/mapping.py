"""Explicit row-to-model mappers used by the repositories."""

from api.enums import ActionName, PriorityName, RoleName, StatusName
from api.models import (
    Action, Address, Commune, Crew, CrewMember, Evidence, FailureType,
    HistoryEvent, Municipality, Neighborhood, Priority, Role, Status, Ticket,
    User,
)
from api.models.address.addresses import (
    CrossBisCode, CrossQuadrant, CrossSuffixLetter, RoadBisCode, RoadQuadrant,
    RoadSuffixLetter, RoadType,
)


def _v(row, name):
    return row[name]


def municipality(row): return Municipality(_v(row, "id"), _v(row, "name"))
def commune(row): return Commune(_v(row, "id"), _v(row, "number"), _v(row, "name"), _v(row, "municipality_id"))
def neighborhood(row): return Neighborhood(_v(row, "id"), _v(row, "name"), _v(row, "municipality_id"), _v(row, "commune_id"))
def road_type(row): return RoadType(_v(row, "code"), _v(row, "name"))
def road_suffix_letter(row): return RoadSuffixLetter(_v(row, "code"))
def road_bis_code(row): return RoadBisCode(_v(row, "code"))
def road_quadrant(row): return RoadQuadrant(_v(row, "code"), _v(row, "name"))
def cross_suffix_letter(row): return CrossSuffixLetter(_v(row, "code"))
def cross_bis_code(row): return CrossBisCode(_v(row, "code"))
def cross_quadrant(row): return CrossQuadrant(_v(row, "code"), _v(row, "name"))


def address(row):
    return Address(**{name: _v(row, name) for name in (
        "id", "road_type_code", "road_number", "road_suffix_letter_code",
        "road_bis_code", "road_bis_suffix", "road_quadrant_code",
        "cross_road_number", "cross_suffix_letter_code", "cross_bis_code",
        "cross_bis_suffix", "cross_quadrant_code", "door_plate_number",
        "neighborhood_id", "created_at",
    )})


def role(row): return Role(_v(row, "id"), RoleName.from_sql(_v(row, "name")))
def user(row): return User(_v(row, "id"), _v(row, "first_name"), _v(row, "last_name"), _v(row, "email"), _v(row, "password_hash"), _v(row, "role_id"), _v(row, "active"))
def crew(row): return Crew(_v(row, "id"), _v(row, "name"))
def crew_member(row): return CrewMember(_v(row, "user_id"), _v(row, "crew_id"))
def priority(row): return Priority(_v(row, "id"), PriorityName.from_sql(_v(row, "name")))
def failure_type(row): return FailureType(_v(row, "id"), _v(row, "name"), _v(row, "priority_id"))
def status(row): return Status(_v(row, "id"), StatusName.from_sql(_v(row, "name")))
def action(row): return Action(_v(row, "id"), ActionName.from_sql(_v(row, "name")))


def ticket(row):
    return Ticket(**{name: _v(row, name) for name in (
        "id", "code", "reported_by", "failure_type_id", "description",
        "address_id", "status_id", "priority_id", "contact_email",
        "contact_phone", "diagnosis", "solution", "crew_id", "created_at",
    )})


def evidence(row): return Evidence(_v(row, "id"), _v(row, "ticket_id"), _v(row, "file_path"), _v(row, "captured_at"), _v(row, "uploaded_by"))
def history_event(row): return HistoryEvent(_v(row, "id"), _v(row, "ticket_id"), _v(row, "user_id"), _v(row, "action_id"), _v(row, "event_time"))
