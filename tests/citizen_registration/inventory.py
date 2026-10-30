"""Citizen-registration test inventory mapped to Scrum 1 subtasks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegistrationCase:
    case_id: str
    subtask: str
    modality: str
    automated_test: str | None


def _subtask_for(number: int) -> str:
    if number <= 5:
        return "ST1.1"
    if number <= 11:
        return "ST1.2"
    if number <= 21:
        return "ST1.3"
    if number <= 29:
        return "ST1.4"
    if number <= 35:
        return "ST1.5"
    if number <= 44:
        return "ST1.6"
    if number <= 51:
        return "ST1.7"
    if number <= 58:
        return "ST1.8"
    return "ST1.9"


def _test_for(number: int) -> str | None:
    if number <= 21 or number in {59, 61, 63, 71}:
        return None
    if 22 <= number <= 29:
        return "test_registration_contract.py" if number < 27 else "test_registration_http.py"
    if 30 <= number <= 35:
        return "test_password_hashing.py"
    if 36 <= number <= 44:
        return "test_registration_service.py"
    if 45 <= number <= 51:
        return "test_registration_authorization.py"
    if 52 <= number <= 58:
        return "test_registration_http.py"
    if 59 <= number <= 75:
        return "test_registration_connector.py"
    return None


def _modality_for(number: int) -> str:
    if number <= 21 or number in {59, 61, 63, 71}:
        return "manual"
    return "automated"


REGISTRATION_CASES = tuple(
    RegistrationCase(
        case_id=f"REG-{number:03d}",
        subtask=_subtask_for(number),
        modality=_modality_for(number),
        automated_test=_test_for(number),
    )
    for number in range(1, 76)
)


__all__ = ["REGISTRATION_CASES", "RegistrationCase"]
