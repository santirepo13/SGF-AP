from ..sql_enum import SqlEnum


class RoleName(SqlEnum):
    CITIZEN = "Citizen"
    OPERATOR = "Operator"
    COORDINATOR = "Coordinator"
    CREW = "Crew"
    ADMIN = "Admin"
