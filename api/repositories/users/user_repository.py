from dataclasses import dataclass
from api.contracts import UNSET, UserActivationInput, UserCreateInput, UserUpdateInput
from ..mapping import user
from ..persistence import RepositoryBase

@dataclass(frozen=True)
class UserFilters:
    email: str | None = None
    role_id: int | None = None
    active: bool | None = None

_COLUMNS = "id, first_name, last_name, email, password_hash, role_id, active"

class UserRepository(RepositoryBase):
    def get_by_id(self, user_id: int):
        return self.fetch_one(f"SELECT {_COLUMNS} FROM users WHERE id = %s", (user_id,), operation="users.get_by_id", entity="user", mapper=user)
    def get_by_email(self, email: str):
        return self.fetch_one(f"SELECT {_COLUMNS} FROM users WHERE email = %s", (email,), operation="users.get_by_email", entity="user", mapper=user)
    def list_by_filters(self, filters: UserFilters | None = None):
        filters = filters or UserFilters()
        clauses, params = [], []
        for column in ("email", "role_id", "active"):
            value = getattr(filters, column)
            if value is not None:
                clauses.append(f"{column} = %s"); params.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return self.fetch_all(f"SELECT {_COLUMNS} FROM users{where} ORDER BY id", tuple(params), operation="users.list_by_filters", entity="user", mapper=user)
    def create(self, data: UserCreateInput):
        return self.execute_one(f"INSERT INTO users (first_name, last_name, email, password_hash, role_id, active) VALUES (%s, %s, %s, %s, %s, %s) RETURNING {_COLUMNS}", (data.first_name, data.last_name, data.email, data.password_hash, data.role_id, data.active), operation="users.create", entity="user", mapper=user)
    def update(self, data: UserUpdateInput):
        allowed = ("first_name", "last_name", "email", "password_hash", "role_id", "active")
        changes = [(name, getattr(data, name)) for name in allowed if getattr(data, name) is not UNSET]
        if not changes: return self.get_by_id(data.user_id)
        values = [value for _, value in changes] + [data.user_id]
        set_clause = ", ".join(f"{name} = %s" for name, _ in changes)
        return self.execute_one(f"UPDATE users SET {set_clause} WHERE id = %s RETURNING {_COLUMNS}", tuple(values), operation="users.update", entity="user", mapper=user)
    def set_active(self, data: UserActivationInput):
        return self.execute_one(f"UPDATE users SET active = %s WHERE id = %s RETURNING {_COLUMNS}", (data.active, data.user_id), operation="users.set_active", entity="user", mapper=user)
