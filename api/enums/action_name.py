from .sql_enum import SqlEnum


class ActionName(SqlEnum):
    REGISTRATION = "Registration"
    VALIDATION = "Validation"
    PRIORITIZATION = "Prioritization"
    ASSIGNMENT = "Assignment"
    ATTENTION = "Attention"
    BLOCKAGE = "Blockage"
    CLOSURE_REQUEST = "ClosureRequest"
    APPROVAL = "Approval"
    REJECTION = "Rejection"
