# Repositorios de SGF-AP

Los repositorios separan el acceso a PostgreSQL de los servicios. Cada repositorio consulta una tabla o catálogo, recibe la dependencia de persistencia desde el exterior y convierte las filas a modelos de api.models.

## Organización

| Carpeta | Responsabilidad |
|---|---|
| geolocation/ | municipalities, communes y neighborhoods. |
| address/ | Siete catálogos de dirección. |
| raíz | AddressRepository y utilidades comunes. |
| users/ | roles, users, crews y crew_members. |
| tickets/ | prioridades, tipos de falla, estados, acciones, tickets, evidencias e historial. |

La implementación actual también conserva mapping.py y persistence.py para mapear filas, ejecutar consultas y compartir comportamiento de persistencia.

## Contrato general

- Consulta individual: modelo o None si no existe.
- Consulta múltiple: list[Modelo], posiblemente [].
- create: modelo persistido con IDs, defaults y fechas devueltos por RETURNING.
- update: modelo actualizado o None si no existe.
- remove de pertenencia: True si elimina una fila; False si no existía.
- Error técnico: ApplicationError clasificado por api.errors.

Los listados deben tener un orden determinista y conservar NULL, booleanos, enums y fechas con zona horaria.

## Seguridad de consultas

Los valores se envían como parámetros separados. Los nombres de columnas, fragmentos de filtro, listas de UPDATE y criterios de orden se controlan mediante allowlists; nunca se interpolan directamente desde entrada arbitraria.

## Transacciones

El repositorio no abre conexiones y no contiene credenciales. Tampoco ejecuta commit() ni rollback(). El coordinador externo decide la confirmación o reversión.

La misma conexión o contexto transaccional puede compartirse entre ticket, evidencia e historial. Un fallo se propaga para que el servicio revierta toda la operación relacionada. Los repositorios no reintentan escrituras automáticamente.

## Errores

Los fallos identificables se traducen mediante api.errors.ErrorHandler:

- 23503: REL-001.
- 23505: CON-001.
- Restricciones de entrada reconocibles: VAL-001 o VAL-002.
- Conexión, serialización o interbloqueo: SYS-001.
- Fallos no clasificados: SYS-001 o SYS-002 según la capa que los reciba.

La causa técnica se conserva internamente; no se entrega el traceback ni los parámetros sensibles al consumidor.

