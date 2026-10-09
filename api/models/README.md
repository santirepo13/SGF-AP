# Modelos internos de SGF-AP

El paquete api.models representa filas persistidas del esquema PostgreSQL. Los modelos no abren conexiones y no consultan otras tablas. Las claves foráneas se representan mediante los identificadores de las entidades relacionadas.

## Modelos cubiertos

| Grupo | Modelos |
|---|---|
| Geolocalización | Municipality, Commune, Neighborhood |
| Dirección | RoadType, RoadSuffixLetter, RoadBisCode, RoadQuadrant, CrossSuffixLetter, CrossBisCode, CrossQuadrant, Address |
| Usuarios | Role, User, Crew, CrewMember |
| Tickets | Priority, FailureType, Status, Action, Ticket |
| Seguimiento | Evidence, HistoryEvent |

Son 22 modelos, exportados desde api.models y organizados en subcarpetas Geolocation, Address, Users y Tickets según el dominio.

## Correspondencia de tipos

- SERIAL y BIGSERIAL se representan como int.
- INT y SMALLINT se representan como int.
- TEXT, VARCHAR y CHAR se representan como str.
- BOOLEAN se representa como bool.
- TIMESTAMPTZ se representa como datetime con zona horaria.
- Campos nullable conservan None.
- Las relaciones conservan el ID de la FK, no una conexión implícita a otro modelo.

## Defaults de persistencia

- users.active: TRUE.
- tickets.status_id: estado inicial Registered según el catálogo resuelto por la aplicación.
- addresses.created_at: NOW().
- history_events.event_time: NOW().

Si una fila ya contiene un valor generado, el modelo debe conservarlo literalmente, incluidos el ID, active=False, None y la zona horaria de las fechas.

## Restricciones por capa

Los modelos pueden validar restricciones escalares, como rangos, longitudes, sufijos y fechas aware. Los repositorios y servicios validan existencia de referencias, unicidad, relaciones compuestas, pertenencias, permisos y transiciones de ticket.

User.password_hash es interno para persistencia y nunca debe copiarse a UserOutput. Ticket conserva por separado reported_by y los datos de procesamiento. Evidence conserva captured_at y uploaded_by. HistoryEvent permite user_id=None y conserva event_time.

## Uso

Los repositorios convierten filas de PostgreSQL a estos modelos. Los servicios convierten los modelos a las salidas de api.contracts. Los modelos se pueden construir directamente en pruebas sin conexión.

