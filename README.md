# SGF-AP

SGF-AP es el Sistema de Gestión y Reporte de Fallas en Alumbrado Público de Medellín. Su propósito es registrar fallas reportadas por ciudadanos, validarlas, clasificarlas, priorizarlas, asignarlas a cuadrillas, registrar la atención y conservar la trazabilidad hasta el cierre.

El sistema contempla actores ciudadanos, operadores de recepción, coordinadores de mantenimiento, cuadrillas técnicas y administradores.

## Alcance actual del repositorio

La implementación actual contiene la base técnica de la API:

- Contratos tipados de entrada, salida, contexto y resultados.
- Modelos internos para las tablas del esquema PostgreSQL.
- Enums de roles, prioridades, estados y acciones.
- Catálogo y traducción centralizada de errores.
- Repositorios parametrizados e interfaces de repositorios.
- Servicios de aplicación e interfaces de servicios.
- Middleware de contexto, validación, autorización, errores y logging.
- Configuración de PostgreSQL mediante `api/.env`.
- Punto de entrada ASGI con FastAPI y Uvicorn.
- Pruebas pytest y ejecutor acumulado `tests/coverage.py`.

El alcance funcional documentado en los PDF incluye registro y seguimiento de reportes, validación, control de duplicados, priorización, asignación, intervención, evidencias, cierre, historial, indicadores y administración. Algunas de esas funciones todavía requieren rutas HTTP y componentes de producto adicionales. Actualmente el servidor se utiliza para verificar el arranque, la configuración y la conexión a PostgreSQL; no hay rutas de negocio públicas configuradas, por lo que las solicitudes HTTP devuelven `404`.

Los documentos de referencia están en `docs/`:

- `tareanegocio.pdf`: contexto, actores y reglas del negocio.
- `tarea2 (1).pdf`: requisitos funcionales y no funcionales.
- `Correccion Tarea 3 - Santiago Restrepo Torres.pdf`: referencia de pruebas estructurales, casos PE/AD y comportamiento transaccional.

La referencia de pruebas usa un modelo algorítmico con nombres en español; no debe confundirse automáticamente con los nombres de la API actual ni con sus rutas HTTP.

## Estructura principal

```text
api/
├── config/          Configuración y conexión PostgreSQL
├── contracts/       Contratos tipados de la API
├── enums/           Valores cerrados del dominio
├── errors/          Errores centralizados
├── interfaces/      Interfaces de repositorios y servicios
├── middleware/      Cadena de ejecución de la API
├── models/          Modelos internos de persistencia
├── repositories/    Acceso parametrizado a PostgreSQL
├── services/        Servicios de aplicación
└── main.py          Punto de entrada ASGI

db/                  Scripts SQL
docs/                Documentos de requisitos y pruebas
tests/               Pruebas pytest y ejecutor coverage.py
```

## Requisitos

- Python 3.13 o superior.
- PostgreSQL accesible desde la máquina donde se inicia la API.
- PowerShell en Windows o un shell compatible en Linux/macOS.

## Crear y activar `.venv`

Desde la raíz del proyecto:

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Instalar dependencias

Con `.venv` activado:

```bash
python -m pip install --upgrade pip
python -m pip install -r api/requirements.txt
python -m pip install -r tests/requirements.txt
```

`api/requirements.txt` contiene `fastapi`, `uvicorn[standard]`, `psycopg[binary]` y `python-dotenv`. `tests/requirements.txt` contiene las dependencias de pruebas, incluido `pytest`.

## Configurar PostgreSQL

Crear `api/.env` y completar la contraseña real:

```env
DB_HOST=87.239.135.39
DB_PORT=5432
DB_NAME=SGFAP
DB_USER=postgres
DB_PASSWORD=REEMPLAZAR_CON_LA_CONTRASEÑA_REAL
```

El archivo `api/.env` está excluido del control de versiones. No se deben guardar contraseñas en el código, el README ni los logs.

La aplicación valida estas variables antes de intentar conectarse. Una contraseña incorrecta, un servidor inaccesible o una base de datos inexistente producen un fallo de startup centralizado.

## Abrir la API

Desde la raíz del proyecto y con `.venv` activado:

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --log-level info
```

La dirección local es `http://localhost:8000`. Durante el startup la aplicación carga y valida `api/.env`, abre PostgreSQL, ejecuta `SELECT 1`, registra la disponibilidad y cierra la conexión al detener Uvicorn. Para detenerla, presiona `Ctrl+C`.

Actualmente no hay rutas de negocio públicas configuradas; las solicitudes HTTP devuelven `404`. Esto permite verificar el arranque, la conexión y el cierre antes de publicar las rutas.

## Ejecutar las pruebas

El ejecutor `tests/coverage.py` carga los archivos `tests/test_*.py`, ejecuta la suite acumulada y muestra el resultado por prueba.

```bash
python tests/coverage.py --unit-only
```

Para incluir la conexión real a PostgreSQL:

```bash
python tests/coverage.py --integration
```

Las pruebas de integración necesitan credenciales válidas en `api/.env`, acceso al servidor y una base de datos preparada.

## Mapa de directorios

La API está organizada por capas. Cada paquete principal con código tiene README propio; sus subdirectorios están descritos dentro del README de ese paquete.

### api/config

Configuración de entorno y conexión PostgreSQL.

- config/ — carga y valida api/.env, crea conexiones y libera recursos.
- Documentación: este README; el paquete aún no tiene README propio.

### api/contracts

Contratos tipados compartidos por todas las capas.

- contracts/ — entradas, salidas, contexto, resultados y errores.
- contracts/address/ — contratos de dirección.
- contracts/geolocation/ — contratos de municipios, comunas y barrios.
- contracts/tickets/ — contratos de tickets, evidencias e historial.
- contracts/users/ — contratos de usuarios, cuadrillas y pertenencias.
- Documentación: api/contracts/README.md.

### api/enums

Valores cerrados del dominio y conversión SQL.

- enums/ — base común de enums.
- enums/tickets/ — prioridades, estados y acciones.
- enums/users/ — roles.
- Documentación: api/enums/README.md.

### api/errors

Clasificación, traducción y salida pública de errores.

- errors/ — códigos, catálogo, excepción y handler.
- Documentación: api/errors/README.md.

### api/interfaces

Contratos sustituibles entre consumidores, servicios y repositorios.

- interfaces/ — agrupación general; el paquete aún no tiene README propio.
- interfaces/repositories/ — contratos de persistencia.
  - address/ — dirección y sus catálogos.
  - geolocation/ — municipios, comunas y barrios.
  - tickets/ — tickets, catálogos, evidencias e historial.
  - users/ — usuarios, roles, cuadrillas y pertenencias.
- interfaces/services/ — contratos de servicios.
  - address/ — AddressService.
  - geolocation/ — CatalogService.
  - tickets/ — TicketService, EvidenceService e HistoryService.
  - users/ — UserService y CrewService.
- Documentación: estos paquetes están cubiertos por este README; aún no tienen README propio.

### api/middleware

Cadena reutilizable de contexto, validación, autorización, errores, logging y ejecución.

- middleware/ — políticas y composición del pipeline.
- Documentación: api/middleware/README.md.

### api/models

Representaciones internas de las tablas persistidas.

- models/ — exportaciones y agrupación general.
- models/address/ — Address y organización de dirección.
  - addresses/ — catálogos de componentes de dirección.
- models/geolocation/ — municipios, comunas y barrios.
- models/tickets/ — tickets, catálogos, evidencias e historial.
- models/users/ — usuarios, roles, cuadrillas y pertenencias.
- Documentación: api/models/README.md.

### api/repositories

Acceso parametrizado y mapeo de persistencia.

- repositories/ — utilidades y AddressRepository.
- repositories/address/ — dirección y catálogos.
- repositories/geolocation/ — municipios, comunas y barrios.
- repositories/tickets/ — tickets, catálogos, evidencias e historial.
- repositories/users/ — usuarios, roles, cuadrillas y pertenencias.
- Documentación: api/repositories/README.md.

### api/services

Reglas de aplicación y coordinación de repositorios.

- services/ — base y exportaciones.
- services/address/ — AddressService.
- services/geolocation/ — CatalogService.
- services/tickets/ — TicketService, EvidenceService e HistoryService.
- services/users/ — UserService y CrewService.
- Documentación: api/services/README.md.

## Logs

El proceso registra eventos como `api_startup_started`, `database_connection_opened`, `database_readiness_query_succeeded`, `api_startup_ready` y `database_connection_closed`. Los logs no deben incluir contraseñas, hashes, credenciales ni parámetros sensibles.


