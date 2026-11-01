from ..sql_enum import SqlEnum


class ActionName(SqlEnum):
    REGISTRATION = "Registration"
    VALIDATION = "Validation"
    PRIORITIZATION = "Prioritization"
    ASSIGNMENT = "Assignment"
    ATTENTION = "Attention"
    BLOCKAGE = "Blockage"
    UNBLOCK = "Unblock"
    CLOSURE_REQUEST = "ClosureRequest"
    APPROVAL = "Approval"
    REJECTION = "Rejection"
