"""Traceability registry for executable Scrum test cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class TestCase:
    case_id: str
    scrum: str
    requirement: str
    preparation: str
    input_description: str
    expected: str
    test_file: str


def build_cases(rows: Iterable[tuple[str, str, str, str, str, str, str]]) -> tuple[TestCase, ...]:
    cases = tuple(TestCase(*row) for row in rows)
    identifiers = [case.case_id for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate test case identifier")
    if any(not identifier for identifier in identifiers):
        raise ValueError("test case identifiers cannot be empty")
    return cases
