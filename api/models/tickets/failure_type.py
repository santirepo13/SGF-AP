"""Failure type persistence model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FailureType:
    id: int
    name: str
    priority_id: int
