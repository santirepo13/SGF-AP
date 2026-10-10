from ..sql_enum import SqlEnum


class StatusName(SqlEnum):
    REGISTERED = "Registered"
    VALIDATED = "Validated"
    PRIORITIZED = "Prioritized"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "InProgress"
    BLOCKED = "Blocked"
    PENDING_CLOSURE = "PendingClosure"
    RESOLVED = "Resolved"
