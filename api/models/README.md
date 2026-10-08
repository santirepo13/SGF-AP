# Modelos internos de SGF-AP

Los modelos de este paquete representan registros persistidos y no abren conexiones ni ejecutan reglas que requieran consultar otras tablas. Las claves foráneas se representan mediante sus identificadores `int`.

## Correspondencia

Los 22 modelos corresponden a las tablas del esquema:

- Geolocalización: `Municipality`, `Commune`, `Neighborhood`.
- Dirección: `RoadType`, `RoadSuffixLetter`, `RoadBisCode`, `RoadQuadrant`, `CrossSuffixLetter`, `CrossBisCode`, `CrossQuadrant`, `Address`.
- Usuarios y cuadrillas: `Role`, `User`, `Crew`, `CrewMember`.
- Tickets: `Priority`, `FailureType`, `Status`, `Action`, `Ticket`.
- Seguimiento: `Evidence`, `HistoryEvent`.

Los campos nullable conservan `None`. Los identificadores `SERIAL` y `BIGSERIAL` se representan como `int`. Los campos `TIMESTAMPTZ` requieren `datetime` con zona horaria.

## Restricciones

Los modelos validan restricciones escalares que no requieren consultar la base de datos: rangos y longitudes de dirección, código de ticket, sufijos y zona horaria. Los repositorios y servicios validan existencia de referencias, unicidad, pertenencias y permisos.

Los defaults de persistencia son:

- `users.active`: `TRUE`.
- `tickets.status_id`: `1` (`Registered`).
- `addresses.created_at`: `NOW()`.
- `history_events.event_time`: `NOW()`.

`User.password_hash` pertenece al modelo interno y no debe copiarse a `UserOutput`.
