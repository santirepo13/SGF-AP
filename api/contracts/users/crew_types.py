"""Crew contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CrewCreateInput:
    name: str


@dataclass(frozen=True)
class CrewUpdateInput:
    crew_id: int
    name: str


@dataclass(frozen=True)
class CrewOutput:
    id: int
    name: str
