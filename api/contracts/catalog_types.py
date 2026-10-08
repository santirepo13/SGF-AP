"""Typed outputs for lookup catalogs."""

from dataclasses import dataclass

from .common_types import ensure_choice, ensure_length

ROLE_NAMES = ("Citizen", "Operator", "Coordinator", "Crew", "Admin")
PRIORITY_NAMES = ("High", "Standard")
STATUS_NAMES = ("Registered", "Validated", "Prioritized", "Assigned", "InProgress", "Blocked", "PendingClosure", "Resolved")
ACTION_NAMES = ("Registration", "Validation", "Prioritization", "Assignment", "Attention", "Blockage", "ClosureRequest", "Approval", "Rejection")


@dataclass(frozen=True)
class RoleLookupInput:
    role_id: int


@dataclass(frozen=True)
class PriorityLookupInput:
    priority_id: int


@dataclass(frozen=True)
class FailureTypeLookupInput:
    failure_type_id: int


@dataclass(frozen=True)
class StatusLookupInput:
    status_id: int


@dataclass(frozen=True)
class ActionLookupInput:
    action_id: int


@dataclass(frozen=True)
class TextCodeLookupInput:
    code: str


@dataclass(frozen=True)
class RoleOutput:
    id: int
    name: str

    def __post_init__(self) -> None:
        ensure_length(self.name, 20, "name")
        ensure_choice(self.name, ROLE_NAMES, "role.name")


@dataclass(frozen=True)
class PriorityOutput:
    id: int
    name: str

    def __post_init__(self) -> None:
        ensure_length(self.name, 12, "name")
        ensure_choice(self.name, PRIORITY_NAMES, "priority.name")


@dataclass(frozen=True)
class FailureTypeOutput:
    id: int
    name: str
    priority_id: int


@dataclass(frozen=True)
class StatusOutput:
    id: int
    name: str

    def __post_init__(self) -> None:
        ensure_length(self.name, 24, "name")
        ensure_choice(self.name, STATUS_NAMES, "status.name")


@dataclass(frozen=True)
class ActionOutput:
    id: int
    name: str

    def __post_init__(self) -> None:
        ensure_choice(self.name, ACTION_NAMES, "action.name")


@dataclass(frozen=True)
class RoadTypeOutput:
    code: str
    name: str

    def __post_init__(self) -> None:
        ensure_length(self.code, 2, "code")


@dataclass(frozen=True)
class RoadSuffixLetterOutput:
    code: str

    def __post_init__(self) -> None:
        ensure_length(self.code, 2, "code")


@dataclass(frozen=True)
class RoadBisCodeOutput:
    code: str

    def __post_init__(self) -> None:
        ensure_length(self.code, 3, "code")


@dataclass(frozen=True)
class RoadQuadrantOutput:
    code: int
    name: str


@dataclass(frozen=True)
class CrossSuffixLetterOutput:
    code: str

    def __post_init__(self) -> None:
        ensure_length(self.code, 2, "code")


@dataclass(frozen=True)
class CrossBisCodeOutput:
    code: str

    def __post_init__(self) -> None:
        ensure_length(self.code, 3, "code")


@dataclass(frozen=True)
class CrossQuadrantOutput:
    code: int
    name: str
