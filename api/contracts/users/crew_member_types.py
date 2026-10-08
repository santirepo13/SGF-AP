"""Crew membership contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CrewMemberInput:
    user_id: int
    crew_id: int


@dataclass(frozen=True)
class CrewMemberOutput:
    user_id: int
    crew_id: int


CrewMembershipResult = CrewMemberOutput | None
