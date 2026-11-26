# Sprint 5 — Registro ciudadano de fallas de alumbrado

## Límite de ubicación

La ubicación del reporte es **exclusivamente** la dirección estructurada canónica existente. El cliente crea o reutiliza la dirección mediante `POST /addresses` y utiliza el `address_id` devuelto al registrar la falla.

No hay campos de coordenadas, GPS, latitud, longitud ni ubicación de dispositivo en este flujo, en tickets, direcciones, contratos ni migraciones.

## Autenticación

Las rutas ciudadanas requieren dos credenciales independientes:

- HTTP Basic técnico en `Authorization`;
- sesión vigente de Citizen en `User-Access-Token`.

El cuerpo no admite `reported_by`, rol, código, estado, prioridad, cuadrilla, diagnóstico, solución, rutas de archivo ni otras propiedades adicionales. La identidad sale únicamente de la sesión validada.

## Dirección estructurada

Antes de crear el reporte, enviar el contrato existente `AddressCreateInput` a:

```http
POST /addresses
```

La respuesta exitosa reutiliza o crea la dirección canónica y devuelve `data.id`. La API valida códigos de catálogos y barrio, y resuelve carreras de inserción con el índice canónico de componentes.

El formulario conserva `address_id` solo para la versión actual de sus componentes. Si cambia un componente, resuelve de nuevo la dirección antes de enviar el reporte.

## Registro ciudadano

```http
POST /tickets/citizen
Authorization: Basic …
User-Access-Token: …
Content-Type: application/json
```

```json
{
  "request_key": "0e428516d5d94f17892ad749158615f3",
  "failure_type_id": 4,
  "address_id": 27,
  "description": "La luminaria permanece apagada desde anoche.",
  "contact_email": "persona@example.test",
  "contact_phone": "+57 300 000 0000",
  "email_notifications": false,
  "temporary_upload_ids": [
    "00000000-0000-0000-0000-000000000000"
  ]
}
```

## Carga temporal de fotografías

```http
POST /evidences/uploads
Content-Type: multipart/form-data
Authorization: Basic …
User-Access-Token: …
```

```text
file=<una imagen JPEG, PNG o WebP>
request_key=<clave opaca del intento>
upload_key=<clave opaca estable de la selección>
capture_source=camera|device_metadata|user_declared|unknown
captured_at=<ISO 8601 con zona, opcional>
```

```json
{
  "success": true,
  "data": {
    "upload_id": "00000000-0000-0000-0000-000000000000",
    "state": "ready",
    "size_bytes": 152300,
    "media_type": "image/jpeg",
    "captured_at": "2026-11-04T10:30:00-05:00",
    "capture_source": "camera",
    "expires_at": "2026-11-05T10:30:00-05:00"
  },
  "error": null
}
```

## Aporte a coincidencia

```http
POST /tickets/citizen/contributions
```

```json
{
  "request_key": "clave-de-intento",
  "target_code": "SGF-AAAAAAAAAAAAAAAAAAAA",
  "address_id": 27,
  "failure_type_id": 4,
  "temporary_upload_ids": [
    "00000000-0000-0000-0000-000000000000"
  ]
}
```

```json
{
  "success": true,
  "data": {
    "request_key": "clave-de-intento",
    "outcome": "contributed",
    "contribution_id": "00000000-0000-0000-0000-000000000000",
    "ticket_code": "SGF-AAAAAAAAAAAAAAAAAAAA",
    "created_at": "2026-11-04T10:40:00-05:00",
    "evidence_count": 1,
    "evidence_ids": [41]
  },
  "error": null
}
```

Campos obligatorios:

| Campo | Regla |
| --- | --- |
| `request_key` | Texto opaco de 1 a 128 caracteres. No se normaliza. |
| `failure_type_id` | Entero positivo; debe existir. |
| `address_id` | Entero positivo; debe existir. |
| `description` | Texto no vacío después de comprobar espacios; se conserva como fue enviado; límite configurable inicial de 4.000 caracteres. |

Campos opcionales:

| Campo | Regla |
| --- | --- |
| `contact_email` | Omitido o `null`; si existe, debe tener formato de correo válido. No identifica al reportante. |
| `contact_phone` | Omitido o `null`; texto de hasta 32 caracteres. No implica SMS. |
| `temporary_upload_ids` | Omitido o arreglo de hasta tres referencias opacas únicas. La carga y consumo de fotografías pertenecen al recorrido de evidencias. |
| `email_notifications` | Omitido o booleano. Su valor efectivo es `false` cuando se omite y se persiste el valor enviado. No admite `null`. |

Los campos opcionales omitidos se conservan como `UNSET` durante la canonicalización del intento; no se confunden con `null` antes de calcular el digest idempotente. `temporary_upload_ids` y `email_notifications` no admiten `null`. La preferencia se almacena en `tickets.email_notifications`.

## Consultas ciudadanas seguras

Los contratos de consulta no reutilizan `TicketOutput`, `EvidenceOutput` ni filas internas. Los campos permitidos son:

| Contrato | Campos |
| --- | --- |
| `PublicTicketOutput` | `code`, `status`, `status_label`, `last_updated_at`, `public_summary` |
| `CitizenTicketListItem` | `code`, `created_at`, `status`, `status_label`, `failure_type_label`, `last_updated_at` |
| `CitizenTicketDetailOutput` | Campos de listado, `public_summary`, `description`, `formatted_address`, `contact_email`, `contact_phone`, `email_notifications`, referencias seguras de evidencia |
| `CitizenHistoryItem` | `occurred_at`, `action`, `label` |
| Páginas | `items`, `next_cursor` |

Las referencias de evidencia solo incluyen `evidence_id`, `media_type`, `size_bytes`, `captured_at`, `capture_source`, `uploaded_at` y `content_available`.

Los contratos no incluyen `reported_by`, identificadores internos de ticket o evento, `crew_id`, técnico, diagnóstico, solución, rutas, claves de almacenamiento, hashes, contactos ajenos, coordenadas, GPS ni ubicación precisa. Las fechas son ISO 8601 con zona horaria; no se aceptan fechas naive.

Los estados públicos son `Registered/Registrado`, `Validated/Validado`, `Prioritized/Priorizado`, `Assigned/Asignado`, `InProgress/En atención`, `Blocked/Bloqueado`, `PendingClosure/Pendiente de cierre` y `Resolved/Resuelto`. Un estado no reconocido usa `Unavailable`, `Estado no disponible` y `No es posible mostrar el avance en este momento.` sin copiar el nombre interno.

Las acciones históricas son `Registration/Reporte registrado`, `Validation/Reporte validado`, `Prioritization/Reporte priorizado`, `Assignment/Atención programada`, `Attention/Atención registrada`, `Blockage/Atención temporalmente bloqueada`, `Unblock/Atención reanudada`, `ClosureRequest/Resultado en revisión`, `Approval/Reporte resuelto` y `Rejection/El reporte continúa en atención`. `Rejection` nunca se presenta como reporte rechazado.

Endpoints:

```http
GET /tickets/citizen/mine?limit=20&cursor=...
GET /tickets/citizen/mine/{code}
GET /tickets/citizen/mine/{code}/history?limit=50&cursor=...
GET /tickets/public/{code}
```

La respuesta de listado de ejemplo tiene la forma `{"success":true,"data":{"items":[],"next_cursor":null},"error":null}`. Las consultas inválidas responden `VAL-002` con HTTP 400; la ausencia o falta de titularidad del detalle privado responde `RES-001` con HTTP 404. La ruta pública aplica `OperationPolicy(resolve_actor=False)` incluso si el cliente envía un token incidental vencido.

### Ejemplos de respuestas ST3.3

Lista privada paginada con resultados:

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "code": "SGF-6DCD4CE23D88E2EE9568",
        "created_at": "2026-11-04T14:20:00-05:00",
        "status": "Registered",
        "status_label": "Registrado",
        "failure_type_label": "Light out",
        "last_updated_at": "2026-11-04T14:20:00-05:00"
      }
    ],
    "next_cursor": "opaque-signed-cursor"
  },
  "error": null
}
```

Lista privada vacía:

```json
{
  "success": true,
  "data": {"items": [], "next_cursor": null},
  "error": null
}
```

Detalle privado propio:

```json
{
  "success": true,
  "data": {
    "code": "SGF-6DCD4CE23D88E2EE9568",
    "created_at": "2026-11-04T14:20:00-05:00",
    "status": "Resolved",
    "status_label": "Resuelto",
    "failure_type_label": "Light out",
    "last_updated_at": "2026-11-05T09:10:00-05:00",
    "public_summary": "Se registró la resolución del reporte.",
    "description": "La luminaria no enciende.",
    "formatted_address": "Calle 10 # 20 - 30, Centro",
    "contact_email": "ciudadano@example.com",
    "contact_phone": "3000000000",
    "email_notifications": true,
    "evidences": []
  },
  "error": null
}
```

Consulta pública existente:

```json
{
  "success": true,
  "data": {
    "code": "SGF-6DCD4CE23D88E2EE9568",
    "status": "InProgress",
    "status_label": "En atención",
    "last_updated_at": "2026-11-05T09:10:00-05:00",
    "public_summary": "La atención del reporte está en curso."
  },
  "error": null
}
```

Consulta pública inexistente:

```json
{
  "success": false,
  "data": null,
  "error": {"code": "RES-001", "message": "Reporte no disponible"}
}
```

Detalle privado de otra cuenta usa exactamente el mismo `RES-001` y no incluye información que permita distinguir un código existente de uno inexistente:

```json
{
  "success": false,
  "data": null,
  "error": {"code": "RES-001", "message": "Reporte no disponible"}
}
```

### Inventario de rutas antiguas

| Ruta antigua | Operación | Política efectiva |
| --- | --- | --- |
| `GET /tickets/{ticket_id}` | `TicketService.get_by_id` | Actor activo, `operational_ticket_read` y regla de recurso del rol interno; Citizen bloqueado. |
| `GET /tickets/by-code/{code}` | `TicketService.get_by_code` | Actor activo, `operational_ticket_read` y regla de recurso del rol interno; Citizen bloqueado. |
| `GET /tickets` | `TicketService.list_by_filters` | Actor activo y `operational_ticket_read`; Crew queda limitado a su cuadrilla. |
| `GET /history-events/{event_id}` | `HistoryService.get_event` | Actor activo, `operational_ticket_read` y regla de recurso del rol interno. |
| `GET /history-events/ticket/{ticket_id}` | `HistoryService.list_by_ticket` | Actor activo, `operational_ticket_read` y regla de recurso del rol interno. |
| `GET /evidences/{evidence_id}` | `EvidenceService.get_by_id` | Actor activo, `operational_ticket_read` y regla de recurso del rol interno. |
| `GET /evidences` | `EvidenceService.list_by_ticket` o `list_by_ticket_and_uploader` | Actor activo, `operational_ticket_read` y regla de recurso del rol interno. |

Estas rutas antiguas no son aliases públicos de los contratos ciudadanos. El cliente Citizen usa únicamente las rutas `/tickets/citizen/mine`, `/tickets/citizen/mine/{code}`, `/tickets/citizen/mine/{code}/history`, `/tickets/citizen/mine/{code}/evidences` y `/tickets/public/{code}`.

El listado usa límite entre 1 y 50, el historial entre 1 y 100, consulta `limit + 1`, no usa `OFFSET` y aplica siempre la cuenta autenticada. Los cursores son opacos, versionados, firmados, limitados y vinculados a la cuenta o al ticket. Un cursor inválido, manipulado o de otro alcance devuelve `VAL-002`. Una lista vacía es una respuesta exitosa con `items: []` y `next_cursor: null`.

La consulta pública no requiere sesión y solo devuelve `PublicTicketOutput`; tanto un código inexistente como un recurso privado no disponible devuelven `RES-001`. Las rutas genéricas de ticket, historial y evidencia requieren actor activo y `operational_ticket_read`; Citizen no puede usarlas. Las rutas ciudadanas requieren Basic técnico y `User-Access-Token`, con `Cache-Control: no-store`.

### Resultado creado

HTTP 200; no se usa 201 para esta operación.

```json
{
  "success": true,
  "data": {
    "request_key": "0e428516d5d94f17892ad749158615f3",
    "outcome": "created",
    "ticket": {
      "code": "SGF-6DCD4CE23D88E2EE9568",
      "created_at": "2026-11-04T14:20:00-05:00",
      "status": "Registered",
      "evidence_count": 0
    },
    "matches": []
  },
  "error": null
}
```

El servidor genera el código, toma la cuenta autenticada como reportante y resuelve `Registered` y `Registration` desde los catálogos. El resultado se devuelve solo después del commit de ticket, evento de historial y ledger.

### Resultado de coincidencias

Una coincidencia exitosa no crea un ticket.

```json
{
  "success": true,
  "data": {
    "request_key": "0e428516d5d94f17892ad749158615f3",
    "outcome": "matches",
    "ticket": null,
    "matches": [
      {
        "code": "SGF-6DCD4CE23D88E2EE9568",
        "status": "InProgress",
        "created_at": "2026-11-04T10:20:00-05:00",
        "progress_label": "Atención en curso"
      }
    ]
  },
  "error": null
}
```

La regla compartida compara exactamente el mismo `address_id` y `failure_type_id`; los estados abiertos son `Registered`, `Validated`, `Prioritized`, `Assigned`, `InProgress`, `Blocked` y `PendingClosure`. `Resolved` no coincide. La salida contiene como máximo veinte candidatos y `has_more` en la ruta orientativa.

## Búsqueda orientativa

```http
POST /tickets/citizen/matches
```

```json
{
  "address_id": 27,
  "failure_type_id": 4
}
```

Respuesta:

```json
{
  "success": true,
  "data": {
    "matches": [],
    "has_more": false
  },
  "error": null
}
```

La búsqueda no crea un intento. El registro vuelve a comprobar la regla dentro de su transacción bajo la guarda de dirección/tipo de falla.

## Recuperación de intento

```http
GET /tickets/citizen/attempts/0e428516d5d94f17892ad749158615f3
```

Resultado confirmado:

```json
{
  "success": true,
  "data": {
    "request_key": "0e428516d5d94f17892ad749158615f3",
    "state": "committed",
    "result": {
      "request_key": "0e428516d5d94f17892ad749158615f3",
      "outcome": "created",
      "ticket": {
        "code": "SGF-6DCD4CE23D88E2EE9568",
        "created_at": "2026-11-04T14:20:00-05:00",
        "status": "Registered",
        "evidence_count": 0
      },
      "matches": []
    }
  },
  "error": null
}
```

Resultado sin confirmación aún:

```json
{
  "success": true,
  "data": {
    "request_key": "0e428516d5d94f17892ad749158615f3",
    "state": "not_found",
    "result": null
  },
  "error": null
}
```

`not_found` no prueba que un envío concurrente haya fallado y no autoriza generar otra clave automáticamente. Registro y recuperación envían `Cache-Control: no-store`.

## Idempotencia y concurrencia

El ledger usa la clave `(actor_user_id, operation, request_key)` con operación estable `TicketService.register_citizen`. El digest SHA-256 incluye la intención validada y distingue campos omitidos de `null`.

- misma clave y mismo digest: reproduce el resultado confirmado;
- misma clave y digest distinto: `CON-005`, HTTP 409;
- una nueva intención debe usar una nueva clave;
- la fila del actor se bloquea antes de la guarda por dirección/tipo;
- la guarda PostgreSQL serializa registros simultáneos con la misma dirección y tipo;
- una pérdida de confirmación se informa como `SYS-001` con razón pública `result_unknown`; el cliente debe recuperar o reenviar exactamente el mismo intento.

No se registran cuerpos, contactos, credenciales, referencias temporales ni rutas de archivo en logs.

## Errores relevantes

| Código | HTTP | Significado |
| --- | --- | --- |
| `VAL-001` | 400 | Campo obligatorio ausente. |
| `VAL-002` | 400 | Tipo, formato o límite no válido. |
| `USR-005`, `USR-003`, `USR-004` | 401 | Falta o no es válida/vigente la sesión de usuario. |
| `USR-001` | 403 | Cuenta inactiva. |
| `PER-001` | 403 | Rol u operación no autorizada. |
| `CON-005` | 409 | La clave de operación ya se utilizó con otros datos. |
| `REL-001` | 422 | Dirección o tipo de falla inexistente. |
| `CAT-001` | 500 | Falta un estado o acción de catálogo requerido. |
| `RES-001` | 404 | Reporte no disponible; el mismo resultado se usa para código inexistente y recurso privado ajeno. |

## Migraciones y despliegue

`db/migrations/005_06_citizen_query_indexes.sql` añade los dos índices ciudadanos y `tickets.email_notifications`. El directorio de migraciones de este checkout no contiene las versiones históricas anteriores ni un runner identificado. No aplicar este archivo a una base hasta comprobar el mecanismo de migraciones desplegado y el historial registrado; esta entrega no aplica migraciones automáticamente.

Antes del despliegue se debe verificar en PostgreSQL:

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'tickets'
  AND column_name = 'email_notifications';

SELECT indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname IN (
    'tickets_citizen_query_idx',
    'history_events_citizen_query_idx'
  );
```
