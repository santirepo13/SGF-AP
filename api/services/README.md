# Servicios de aplicación de SGF-AP

El paquete api.services contiene la lógica de aplicación entre el middleware, las interfaces de repositorio y las salidas tipadas. Los servicios reciben sus dependencias por inyección, coordinan repositorios y devuelven OperationResult[T].

No abren conexiones directamente. Las transacciones y la persistencia son responsabilidad de las dependencias recibidas y del coordinador externo.

## Organización

| Carpeta | Servicio | Responsabilidad |
|---|---|---|
| geolocation/ | CatalogService | Consultas de geolocalización, dirección, roles y catálogos de tickets. |
| address/ | AddressService | Consulta, búsqueda, creación/reutilización y formato de direcciones. |
| users/ | UserService | Consulta, creación, actualización y activación de usuarios. |
| users/ | CrewService | Cuadrillas y pertenencias de integrantes. |
| tickets/ | TicketService | Registro, consulta y procesamiento del flujo del ticket. |
| tickets/ | EvidenceService | Consulta y registro de metadatos de evidencias. |
| tickets/ | HistoryService | Consulta y registro de eventos de historial. |

Las interfaces compatibles están en api.interfaces.services y deben ser utilizadas por los consumidores para sustituir implementaciones durante las pruebas.

## Nombres públicos implementados

Los métodos actuales usan nombres en inglés y deben conservarse al integrarlos:

| Servicio | Operaciones principales |
|---|---|
| CatalogService | list_municipalities, list_communes, list_neighborhoods_by_municipality, list_neighborhoods_by_commune, list_neighborhoods_without_commune, list_road_types, list_road_suffix_letters, list_road_bis_codes, list_road_quadrants, list_cross_suffix_letters, list_cross_bis_codes, list_cross_quadrants, list_roles, list_priorities, list_failure_types, list_failure_types_by_priority, list_statuses, list_actions |
| AddressService | get_by_id, find_by_components, create_or_reuse, format_address |
| UserService | get_by_id, get_by_email, list_by_filters, create, update, set_active |
| CrewService | get_by_id, list_all, create, update, get_membership, list_members, add_member, change_crew, remove_member |
| TicketService | create, get_by_id, get_by_code, list_by_filters, validate, prioritize, assign, record_attention, block, request_closure, review_closure |
| EvidenceService | get_by_id, list_by_ticket, list_by_ticket_and_uploader, create_metadata |
| HistoryService | get_event, list_by_ticket, create_event |

Los nombres de los documentos de requisitos o de la referencia algorítmica pueden estar en español; no se deben mezclar automáticamente con los nombres actuales de la API.

## Contexto y resultados

Las operaciones reciben primero un ExecutionContext y después sus datos propios. El contexto contiene la operación, correlation_id y actor cuando se requiere.

Los métodos devuelven OperationResult:

- success=True y error=None cuando la operación termina correctamente.
- success=False, data=None y un ErrorOutput cuando falla.
- Una lista vacía es una consulta válida sin coincidencias.
- data=None es válido para búsquedas o pertenencias cuya ausencia está contemplada.
- data=False es válido para un retiro de pertenencia inexistente.

La correlación debe pasar sin cambios desde el middleware hasta errores, logs y resultado.

## Dependencias inyectadas

Los servicios dependen de interfaces, no de conexiones concretas:

- CatalogService usa repositorios geográficos y de catálogos.
- AddressService usa AddressRepository, NeighborhoodRepository y los siete catálogos de dirección.
- UserService usa UserRepository y RoleRepository.
- CrewService usa CrewRepository, CrewMemberRepository y UserRepository.
- TicketService usa TicketRepository, UserRepository, FailureTypeRepository, StatusRepository y ActionRepository. Puede usar AddressRepository, CrewRepository, EvidenceRepository e HistoryEventRepository para las operaciones relacionadas.
- EvidenceService usa EvidenceRepository, TicketRepository y UserRepository.
- HistoryService usa HistoryEventRepository, TicketRepository y ActionRepository.

Los dobles de prueba deben cumplir las interfaces correspondientes.

## Reglas de aplicación

Los servicios transforman modelos internos a salidas públicas y no exponen User.password_hash. También conservan:

- reported_by como usuario reportante, separado del actor.
- uploaded_by como usuario que carga evidencia.
- None en campos nullable.
- active=False en salidas de usuario.
- fechas con zona horaria.
- IDs de catálogo separados de sus nombres enum.
- UNSET frente a None en modificaciones parciales.

Las comprobaciones de existencia, referencias, permisos, usuario activo, estados del ticket y catálogos requeridos se clasifican mediante api.errors.

## Ticket y operaciones coordinadas

TicketService representa el ticket como reporte y orden de trabajo. Sus acciones resuelven estados y acciones de catálogo, actualizan los campos permitidos y registran HistoryEvent cuando los repositorios relacionados están disponibles.

Las escrituras relacionadas deben ejecutarse con las dependencias transaccionales compartidas:

- creación del ticket y evento de registro;
- cambios de estado y evento de historial;
- asignación y evento;
- atención, evidencias e historial;
- solicitud y revisión de cierre.

Los servicios no deben confirmar parcialmente una operación coordinada ni reintentar automáticamente una escritura. Un fallo debe producir un OperationResult fallido y conservar la correlación.

## Errores

Los servicios usan ApplicationError y ErrorHandler de api.errors:

- VAL-001: dato obligatorio ausente.
- VAL-002: valor inválido.
- RES-001: registro requerido inexistente.
- REL-001: referencia inválida.
- CON-001: conflicto de unicidad.
- USR-001: actor inactivo.
- PER-001: operación no autorizada.
- TKT-001: estado incompatible.
- CAT-001: catálogo requerido no disponible.
- SYS-001: fallo de persistencia.
- SYS-002: fallo inesperado.

Un servicio no debe convertir una lista vacía, None o False válidos en error. Tampoco debe entregar excepciones técnicas, SQL, credenciales, hashes o trazas en la salida.

## Uso directo

La composición debe inyectar repositorios compatibles y entregar un contexto:

    result = service.get_by_id(context, entity_id)

Para producción, la invocación debe pasar por MiddlewarePipeline, que prepara el contexto, valida la entrada, comprueba autorización, ejecuta una vez el método y registra el resultado.

## Límites actuales

El paquete contiene la capa de aplicación y sus contratos. La exposición HTTP de operaciones, autenticación real, almacenamiento físico de archivos, notificaciones, indicadores, exportaciones y coordinación externa con servicios de mapas todavía requieren componentes adicionales.

El arranque actual de api.main comprueba PostgreSQL con SELECT 1; no publica todavía rutas de negocio. Por eso los servicios pueden probarse directamente con dobles sin iniciar FastAPI.

