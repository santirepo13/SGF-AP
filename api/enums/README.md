# Enums cerrados de SGF-AP

Los enums representan los valores textuales cerrados por los `CHECK` del SQL. Sus valores distinguen el nombre del catálogo del identificador numérico persistido en los modelos.

Cada enum hereda de `SqlEnum` y expone:

- `from_sql(value)`: convierte el texto persistido al miembro del enum.
- `to_sql()`: devuelve exactamente el texto que acepta el SQL.

Enums implementados:

- `RoleName`: `Citizen`, `Operator`, `Coordinator`, `Crew`, `Admin`.
- `PriorityName`: `High`, `Standard`.
- `StatusName`: `Registered`, `Validated`, `Prioritized`, `Assigned`, `InProgress`, `Blocked`, `PendingClosure`, `Resolved`.
- `ActionName`: `Registration`, `Validation`, `Prioritization`, `Assignment`, `Attention`, `Blockage`, `ClosureRequest`, `Approval`, `Rejection`.

Un valor no admitido produce `ValueError`. El ID del catálogo siempre permanece como `int` en el modelo correspondiente.
