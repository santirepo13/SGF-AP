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
| `email_notifications` | Omitido o booleano. Su valor efectivo inicial es `false`; la persistencia de preferencias pertenece al flujo posterior de notificaciones. |

Los campos opcionales omitidos se conservan como `UNSET` durante la canonicalización del intento; no se confunden con `null` antes de calcular el digest idempotente. `temporary_upload_ids` y `email_notifications` no admiten `null`.

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

## Migraciones y despliegue

En una instalación nueva, primero aplicar los scripts base de `db/`; luego ejecutar el runner versionado:

```bash
cd /ruta/a/sgf-ap
api/.venv/bin/python db/apply_migrations.py
```

En una base existente, ejecutar únicamente el runner para aplicar las versiones pendientes. El runner usa `schema_migrations`, checksum SHA-256 y un bloqueo asesor de PostgreSQL; una versión aplicada cuyo contenido cambie detiene el despliegue.

Las migraciones requeridas son:

1. `005_01_citizen_ticket` — línea base de reporte ciudadano, sin coordenadas;
2. `005_02_operation_attempts` — ledger idempotente;
3. `005_03_ticket_match_guards` — guardas de concurrencia e índice de coincidencias.

Aplicarlas antes de desplegar la API. La aplicación verifica las tres versiones al iniciar y falla de forma segura si falta alguna; nunca las ejecuta durante una solicitud.
