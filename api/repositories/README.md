# Repositories

There is one repository per SQL table. Each repository receives a DB-API-like
connection from its caller, uses parameterized values, maps rows to an internal
model, and translates technical failures through `api.errors.ErrorHandler`.

`create` and `update` use `RETURNING` so generated identifiers, timestamps,
defaults, and nullable values come from persistence. Lists are deterministic
and return `[]` when no rows exist. Updates use an explicit allowlist: `UNSET`
preserves a field, a value replaces it, and `None` clears a nullable field.

Repositories do not open connections and do not call `commit()` or
`rollback()`. The caller owns the transaction and may pass the same connection
to ticket, evidence, and history repositories.
