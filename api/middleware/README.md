# Middleware de SGF-AP

El paquete api.middleware compone la ejecución de una operación de servicio sin depender de rutas HTTP. Prepara el contexto, valida la llamada, comprueba la política de acceso, ejecuta el servicio una sola vez, normaliza errores y registra el resultado.

Es framework-independent y se puede probar con servicios, proveedores de identidad, verificadores de permisos, generadores de correlación y destinos de logging sustitutos.

## Componentes

| Archivo | Componente | Responsabilidad |
|---|---|---|
| context_middleware.py | ContextMiddleware | Determina la operación, correlación y actor. |
| validation_middleware.py | ValidationMiddleware | Comprueba método, firma, tipos básicos y DTO esperado. |
| authorization_middleware.py | AuthorizationMiddleware | Comprueba actor requerido, activación y permiso. |
| error_middleware.py | ErrorMiddleware | Convierte excepciones en OperationResult con ErrorOutput. |
| execution_logging_middleware.py | ExecutionLoggingMiddleware | Registra inicio, duración, resultado y código de error. |
| middleware_pipeline.py | MiddlewarePipeline | Compone y ejecuta la cadena. |
| operation_policies.py | OperationPolicy | Declara requisitos de actor, permiso y tipo de entrada. |
| base.py | Protocolos y request | Define dependencias sustituibles y MiddlewareRequest. |

Todos los componentes se exportan desde api.middleware.

## Ejecución de la cadena

MiddlewarePipeline.execute recibe:

- service_name: nombre del servicio.
- method_name: método que se va a invocar.
- service: implementación compatible con la interfaz del servicio.
- args y kwargs: argumentos de la operación.
- context opcional: contexto existente.

El orden efectivo es:

1. ErrorMiddleware establece el límite de errores.
2. ContextMiddleware identifica la operación y prepara ExecutionContext.
3. ExecutionLoggingMiddleware registra el inicio y envuelve la ejecución.
4. ValidationMiddleware verifica método, firma y entradas.
5. AuthorizationMiddleware comprueba actor, activación y permisos.
6. Se invoca el método del servicio exactamente una vez.
7. ErrorMiddleware valida y devuelve OperationResult.
8. ExecutionLoggingMiddleware registra finalización, duración y error.

Una interrupción en contexto, validación o autorización evita llamar al servicio. El logger registra la interrupción. Un fallo del logger no cambia el resultado ni provoca una segunda ejecución.

## Uso

    from api.middleware import MiddlewarePipeline

    result = pipeline.execute(
        "AddressService",
        "get_by_id",
        address_service,
        address_id,
    )

Para una operación protegida se entrega un IdentityProvider a ContextMiddleware y un PermissionChecker a AuthorizationMiddleware. Los servicios deben ser implementaciones compatibles con api.interfaces.services.

## Request y contexto

MiddlewareRequest conserva:

- service_name y method_name.
- service.
- args y kwargs.
- ExecutionContext.
- operation seleccionada.

La operación real se forma como ServiceName.method_name. Si una operación recibida no coincide con el método seleccionado, o no existe en OPERATION_POLICIES, se produce VAL-002 antes de ejecutar el servicio.

ExecutionContext conserva operation, correlation_id y actor. La correlación existente se reutiliza; si falta, se genera mediante CorrelationIdGenerator. El actor se obtiene de IdentityProvider, nunca de un rol o usuario enviado en el payload.

## Políticas actuales

OPERATION_POLICIES declara cada operación pública de los siete servicios.

Operaciones públicas de consulta no requieren actor. Las escrituras y operaciones sensibles exigen actor y permiso:

| Permiso | Operaciones |
|---|---|
| create_address | AddressService.create_or_reuse |
| manage_users | UserService.create, update, set_active |
| manage_crews | CrewService.create, update, add_member, change_crew, remove_member |
| create_ticket | TicketService.create |
| process_tickets | TicketService.validate, prioritize, assign, record_attention, block, request_closure, review_closure |
| create_evidence | EvidenceService.create_metadata |
| create_history_event | HistoryService.create_event |

La política también declara los DTO esperados para las operaciones que reciben entrada. No sustituye las reglas de negocio del servicio: referencias, estados concretos, alcance sobre tickets y reglas transaccionales siguen siendo responsabilidad de la capa de aplicación.

## Validación

ValidationMiddleware comprueba antes de invocar el servicio:

- Existencia y capacidad de llamada del método.
- Correspondencia de los argumentos con su firma.
- Tipos exactos para int, str y bool.
- Tipo de dataclass declarado por la política.
- Conservación de None cuando el método lo admite.
- Identificación de parámetros incompatibles.

Los errores de validación producen VAL-002 con la correlación del contexto. La validación no consulta referencias ni otorga permisos.

UNSET y None deben conservar su significado en los DTO de modificación. False es un valor booleano válido y no debe tratarse como ausencia.

## Autorización

AuthorizationMiddleware:

- Exige actor cuando la política lo declara.
- Rechaza actor inactivo con USR-001.
- Usa PermissionChecker para evaluar el permiso configurado.
- Rechaza una operación no autorizada con PER-001.
- Conserva la identidad resuelta en ExecutionContext.

La identidad procede de IdentityProvider. El contenido del payload no puede modificar user_id, role_id o active del actor.

## Manejo de errores y resultados

ErrorMiddleware conserva un OperationResult fallido que ya contiene ErrorOutput y corrige su correlation_id cuando es necesario.

También captura:

- ApplicationError ya clasificado.
- Errores de validación, autorización o contexto.
- Fallos de servicios y repositorios.
- Excepciones inesperadas, clasificadas como SYS-002.
- Resultados que no son OperationResult.
- Resultados exitosos cuya data contradice la anotación de retorno del método.

Los resultados válidos se conservan sin transformación:

- listas vacías;
- None permitido;
- False permitido;
- salidas tipadas;
- errores centralizados.

No se exponen causas técnicas, SQL, credenciales, hashes ni trazas.

## Logging

ExecutionLoggingMiddleware recibe un ExecutionLogger inyectado con start(record) y finish(record).

Los registros contienen únicamente:

- correlation_id;
- operación;
- actor_user_id, si existe;
- evento started o finished;
- duración en segundos;
- success;
- error_code, si existe.

El destino de logging se trata como best-effort: si falla start() o finish(), se conserva el resultado real y no se repite el servicio. No se registran payloads completos ni secretos.

## Dependencias sustituibles

api.middleware.base define Protocol para:

- CorrelationIdGenerator.
- IdentityProvider.
- PermissionChecker.
- ExecutionLogger.

Esto permite probar cada componente con dobles sin FastAPI, PostgreSQL ni una conexión real.

## Límites actuales

El middleware no:

- abre o cierra conexiones;
- ejecuta commit(), rollback() o reintentos;
- implementa reglas de negocio de tickets;
- resuelve referencias de base de datos;
- sustituye la autenticación real;
- publica rutas HTTP.

La coordinación transaccional permanece en los servicios y en su coordinador de persistencia. api.main actualmente comprueba el arranque y PostgreSQL, pero todavía no expone rutas de negocio.

