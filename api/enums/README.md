# Enums cerrados de SGF-AP

El paquete api.enums representa los valores textuales cerrados por los CHECK del SQL. El enum representa el nombre persistido del catálogo; el ID numérico del catálogo permanece separado en el modelo.

## Implementación

SqlEnum es la base común:

- from_sql(value) convierte un texto SQL al miembro correspondiente.
- to_sql() devuelve exactamente el valor que se persiste.
- Un valor desconocido, con capitalización distinta o con espacios adicionales produce ValueError.
- No existen IDs fijos dentro de los enums.

Los enums y miembros se exportan desde api.enums.

## Valores admitidos

| Enum | Valores SQL |
|---|---|
| RoleName | Citizen, Operator, Coordinator, Crew, Admin |
| PriorityName | High, Standard |
| StatusName | Registered, Validated, Prioritized, Assigned, InProgress, Blocked, PendingClosure, Resolved |
| ActionName | Registration, Validation, Prioritization, Assignment, Attention, Blockage, ClosureRequest, Approval, Rejection |

## Uso

    from api.enums import StatusName

    status = StatusName.from_sql("PendingClosure")
    assert status.to_sql() == "PendingClosure"

Los repositorios convierten el valor textual de la fila al enum. Los modelos conservan además el id persistido. Las salidas públicas pueden convertir el enum a su valor SQL cuando el contrato requiere str.

## Reglas

Los enums distinguen mayúsculas y minúsculas exactamente como el SQL. No se debe normalizar, recortar ni traducir el valor antes de convertirlo. La conversión debe fallar de forma identificable para que la capa superior pueda clasificar el error.

