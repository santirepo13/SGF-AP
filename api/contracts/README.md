# Contratos de SGF-AP

Este paquete contiene los tipos compartidos por repositorios, servicios y middleware. Está implementado con `dataclasses` y `typing` de la biblioteca estándar y no requiere conexión a PostgreSQL.

## Correspondencia con SQL

- `SERIAL` y `BIGSERIAL` se representan como `int` en las salidas persistidas.
- `INT` y `SMALLINT` se representan como `int`.
- `TEXT`, `VARCHAR(n)` y `CHAR(1)` se representan como `str`.
- `BOOLEAN` se representa como `bool`.
- `TIMESTAMPTZ` se representa como `datetime` con zona horaria obligatoria.
- Las columnas SQL nullable se representan como `T | None`.

Los identificadores generados por persistencia no aparecen en entradas de creación. `created_at` y `event_time` se reciben en las salidas.

## Actualizaciones parciales

Los campos modificables usan `UNSET` como valor predeterminado:

- `UNSET`: conservar el valor actual.
- Un valor concreto: reemplazar el valor actual.
- `None`: eliminar el valor, únicamente para columnas nullable.

`None` y `UNSET` son valores diferentes y no deben convertirse entre sí en repositorios o servicios.

## Actor y ejecución

`ExecutionContext` contiene la operación, el `correlation_id` y opcionalmente el `ActorContext`. Las operaciones protegidas están en `ACTOR_REQUIRED_OPERATIONS` y pueden comprobarse con `requires_actor()` o `validate_actor_context()`.

El actor que ejecuta una operación es independiente de `reported_by`, que identifica al usuario que registró el ticket.

## Resultados y errores

`OperationResult[T]` representa éxito o fallo controlado:

- Éxito: `success=True`, `error=None`; `data` puede ser `None` cuando la operación no produce datos.
- Fallo: `success=False`, `error` definido y `data=None`.
- Una colección vacía es un dato válido y no representa un fallo.

`ErrorOutput` contiene `code`, `message`, detalles controlados y `correlation_id`. Los detalles nunca deben incluir credenciales, hashes ni trazas internas.

## Módulos

- `user_types.py`, `crew_types.py`, `crew_member_types.py`
- `geolocation_types.py`, `catalog_types.py`
- `address_types.py`, `ticket_types.py`
- `evidence_types.py`, `history_event_types.py`
- `actor_context.py`, `execution_context.py`
- `operation_result.py`, `error_types.py`
