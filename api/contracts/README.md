# Contratos de la API

El paquete api.contracts define los datos que cruzan contratos, modelos, repositorios, servicios y middleware. Son tipos independientes del framework web y de PostgreSQL: se pueden importar y probar sin abrir conexiones.

## Responsabilidad

Los contratos describen:

- Entradas de creación, consulta y modificación.
- Salidas públicas de entidades y catálogos.
- Actor y contexto de ejecución.
- Resultado exitoso o fallido de una operación.
- Detalles y salida pública de errores.
- Ausencia, nulabilidad y actualizaciones parciales.

Las referencias externas se representan con identificadores. La existencia de esas referencias se comprueba en repositorios o servicios.

## Organización

| Módulo | Contenido |
|---|---|
| common_types.py | UNSET, Unset y validación de fechas con zona horaria. |
| geolocation/ | Entradas y salidas de municipios, comunas y barrios. |
| address/ | Componentes, creación y salida de direcciones. |
| users/ | Usuarios, roles, cuadrillas y pertenencias. |
| tickets/ | Tickets, filtros, evidencias e historial. |
| catalog_types.py | Salidas y consultas de catálogos. |
| actor_context.py | Identidad verificada del actor. |
| execution_context.py | Operación, correlación y actor. |
| operation_result.py | Resultado genérico de una operación. |
| error_types.py | ErrorDetail y ErrorOutput. |

Todos los tipos se exportan desde api.contracts.

## Correspondencia con PostgreSQL

- SERIAL y BIGSERIAL se representan como int.
- INT y SMALLINT se representan como int.
- TEXT, VARCHAR y CHAR se representan como str.
- BOOLEAN se representa como bool.
- TIMESTAMPTZ se representa como datetime con tzinfo.
- Las columnas nullable se representan como T | None.
- Los IDs generados y las fechas generadas por persistencia pertenecen a las salidas, no a las entradas de creación.

Los contratos no reemplazan las restricciones relacionales del SQL: una FK, una unicidad o una regla que requiere consultar otra tabla se verifica en la capa correspondiente.

## UNSET y modificaciones parciales

UNSET representa un campo omitido y es distinto de None:

| Entrada | Significado |
|---|---|
| UNSET | Conservar el valor actual. |
| Un valor | Reemplazar el valor actual. |
| None | Eliminar el valor, solo si la columna admite NULL. |

Esto aplica a UserUpdateInput, CrewUpdateInput y TicketUpdateInput. Los repositorios deben conservar esta diferencia al construir UPDATE.

## Contexto de ejecución

ExecutionContext contiene operation, correlation_id y actor opcional. ActorContext contiene user_id, role_id y active.

El actor que ejecuta la operación es diferente de reported_by en un ticket y de uploaded_by en una evidencia. Las operaciones protegidas se identifican en ACTOR_REQUIRED_OPERATIONS y se validan con requires_actor() y validate_actor_context().

## OperationResult

OperationResult[T] representa el resultado de una operación:

- Éxito: success=True y error=None.
- Fallo: success=False, data=None y error definido.
- Lista vacía: éxito válido cuando no hay coincidencias.
- data=None: ausencia esperada solo cuando el método lo permite.
- data=False: resultado booleano válido; no significa fallo.

ErrorOutput contiene code, message, details y correlation_id. No debe incluir contraseñas, hashes, consultas ni trazas.

## Verificación

Las pruebas deben verificar campos, tipos, nulabilidad, valores predeterminados, zonas horarias, UNSET frente a None, salidas públicas y consistencia de OperationResult. Los contratos pueden probarse sin conexión local.

