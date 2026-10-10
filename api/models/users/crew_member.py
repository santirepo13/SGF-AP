"""Crew membership persistence model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CrewMember:
    user_id: int
    crew_id: int
