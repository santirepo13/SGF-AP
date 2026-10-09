# Errores centrales de SGF-AP

El paquete api.errors define la única clasificación de errores usada por repositorios, servicios, middleware y configuración de PostgreSQL. Es independiente de FastAPI y no abre conexiones ni ejecuta transacciones.

## Componentes

| Archivo | Responsabilidad |
|---|---|---|
| error_codes.py | Enum central ErrorCode con los 11 códigos públicos. |
| error_catalog.py | Definiciones inmutables de código, categoría y mensaje público. |
| application_error.py | Excepción de aplicación con detalles, correlación y causa original. |
| error_handler.py | Clasificación, traducción de SQLSTATE y construcción de ErrorOutput. |
| __init__.py | Exportaciones públicas del paquete. |

Los contratos públicos utilizados son ErrorDetail y ErrorOutput de api.contracts.error_types.

## Catálogo central

| Código | Enum | Categoría | Mensaje público |
|---|---|---|---|
| VAL-001 | REQUIRED_FIELD_MISSING | Validación | Falta un dato obligatorio. |
| VAL-002 | INVALID_VALUE | Validación | Uno o más datos tienen un tipo, formato o valor inválido. |
| RES-001 | RESOURCE_NOT_FOUND | Recurso | No se encontró el registro solicitado. |
| REL-001 | INVALID_REFERENCE | Relación | Una referencia indicada no existe o no corresponde al registro relacionado. |
| CON-001 | UNIQUE_CONFLICT | Conflicto | Ya existe un registro con los datos que deben ser únicos. |
| USR-001 | INACTIVE_USER | Usuario | El usuario está inactivo. |
| PER-001 | FORBIDDEN_OPERATION | Permisos | No tiene autorización para realizar esta operación. |
| TKT-001 | INVALID_TICKET_STATE | Ticket | La operación no está permitida en el estado actual del ticket. |
| CAT-001 | CATALOG_VALUE_UNAVAILABLE | Catálogo | Un valor de catálogo requerido para la operación no está disponible. |
| SYS-001 | PERSISTENCE_FAILURE | Persistencia | No fue posible completar la operación de persistencia. |
| SYS-002 | UNEXPECTED_ERROR | Interno | Ocurrió un error interno inesperado. |

El catálogo verifica al importar que exista exactamente una definición para cada miembro de ErrorCode. Las definiciones y el mapa expuesto son inmutables.

## Contrato público

ErrorDetail contiene field: str | None, entity: str | None y reason: str.

ErrorOutput contiene code, message, details y correlation_id. details es una colección vacía cuando no existen detalles públicos.

Una salida pública nunca incluye la excepción técnica, su traceback, SQL, parámetros completos, contraseñas, hashes, credenciales ni cadenas de conexión.

## Crear errores conocidos

Usar las fábricas de ApplicationError en lugar de repetir códigos o mensajes:

    from api.errors import ApplicationError

    error = ApplicationError.required_field(
        "road_number",
        entity="AddressCreateInput",
        correlation_id=context.correlation_id,
    )

    error = ApplicationError.invalid_value(
        "door_plate_number",
        "Debe estar entre 1 y 9999.",
        entity="AddressCreateInput",
    )

    error = ApplicationError.resource_not_found("Ticket")
    error = ApplicationError.invalid_reference("role_id", "El rol no existe.", entity="User")
    error = ApplicationError.unique_conflict("email", entity="User", cause=database_error)
    error = ApplicationError.inactive_user()
    error = ApplicationError.forbidden("TicketService.asignar")
    error = ApplicationError.invalid_ticket_state()
    error = ApplicationError.catalog_unavailable("statuses")
    error = ApplicationError.persistence_failure(cause=database_error)
    error = ApplicationError.unexpected(cause=unexpected_error)

También puede usarse ApplicationError.with_code(...) cuando se necesita construir un error con un código central y varios detalles.

La causa se conserva internamente mediante error.cause y el encadenamiento de excepciones. No se copia al contrato público.

## Correlación

La correlación se conserva en este orden:

1. ApplicationError.correlation_id, si ya existe.
2. ExecutionContext.correlation_id, si existe.
3. Un UUID nuevo al construir la salida pública.

Las capas no deben generar una correlación nueva para el mismo error. El mismo identificador debe aparecer en el resultado, el log y el error público.

    from api.errors import ErrorHandler

    public_error = ErrorHandler.to_public(error, context)

## Clasificación central

ErrorHandler.classify_exception aplica estas reglas:

- Un ApplicationError se conserva sin cambiar su código.
- Un SQLSTATE reconocido se traduce mediante translate_persistence().
- Un ValueError solo se convierte en VAL-002 cuando el contexto indica que proviene de entrada de usuario.
- Una excepción no clasificada se convierte en SYS-002.
- Los fallos de conexión, serialización transaccional e interbloqueo se convierten en SYS-001.

    error = ErrorHandler.classify_exception(
        exception,
        context,
        persistence_context=persistence_context,
    )
    public_error = ErrorHandler.to_public(error, context)

También puede usarse ErrorHandler.handle(exception, context) para clasificar y construir la salida en un paso.

## Traducción de PostgreSQL

La traducción utiliza SQLSTATE y diagnósticos estructurados, no el texto de la excepción.

| SQLSTATE | Condición | Resultado |
|---|---|---|
| 23502 | NOT NULL | VAL-001 si proviene de entrada; en otro caso SYS-001. |
| 23503 | Clave foránea | REL-001. |
| 23505 | Unicidad | CON-001. |
| 23514 | CHECK | VAL-002 si proviene de entrada. |
| 22001 | Texto demasiado largo | VAL-002 si proviene de entrada. |
| 22P02 | Representación inválida | VAL-002 si proviene de entrada. |
| 22003 | Número fuera de rango | VAL-002 si proviene de entrada. |
| Clase 08 | Fallo de conexión | SYS-001. |
| 40001 | Falla de serialización | SYS-001. |
| 40P01 | Interbloqueo | SYS-001. |
| Otro SQLSTATE | Fallo técnico no clasificado | SYS-001. |

Para clasificar correctamente el origen se puede aportar:

    from api.errors import PersistenceContext

    persistence_context = PersistenceContext(
        operation="UserRepository.create",
        entity="users",
        field="email",
        input_origin=True,
    )

input_origin=False es el valor predeterminado. Así, una restricción causada por un defecto de implementación no se presenta automáticamente como error del usuario.

## Reglas de ausencia y fallo

- Una búsqueda sin coincidencias devuelve None; no es automáticamente un error.
- Un listado sin coincidencias devuelve []; no es automáticamente un error.
- Un recurso requerido por un servicio puede convertirse entonces en RES-001.
- Un campo nullable con None no produce VAL-001.
- Un error conocido no debe transformarse en SYS-002 al pasar por otra capa.
- El handler no hace commit(), rollback(), reintentos ni recuperación transaccional.
- Si falla un rollback, la coordinación transaccional debe conservar tanto el fallo original como el fallo secundario internamente.

## Separación de información

Información pública permitida:

- Código central.
- Mensaje del catálogo.
- Detalles construidos explícitamente.
- Identificador de correlación.

Información exclusivamente interna:

- Tipo y objeto de la excepción técnica.
- SQLSTATE.
- Restricción o diagnóstico del driver.
- Causa original y traceback.
- Contexto técnico de transacción.

Nunca se deben construir detalles públicos copiando automáticamente str(exception), consultas SQL, parámetros, hashes o credenciales.

## Uso por capa

- Repositorios: traducen fallos técnicos identificables y conservan la causa.
- Servicios: crean errores de validación, referencia, permisos, usuario inactivo, catálogo y estado del ticket.
- Middleware: conserva errores ya clasificados, convierte errores inesperados y agrega la correlación.
- Configuración/conexión: usa SYS-001 para fallos de configuración/conexión y no expone credenciales.

