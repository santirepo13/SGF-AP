"""Crew persistence model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Crew:
    id: int
    name: str
