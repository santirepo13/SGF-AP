# Errores centrales de SGF-AP

`api.errors` es la fuente única de códigos, mensajes y traducción de fallos para repositorios, servicios y middleware.

## Flujo

1. Las capas crean `ApplicationError` para condiciones conocidas.
2. `ErrorHandler.classify_exception()` conserva errores conocidos o traduce excepciones técnicas.
3. `ErrorHandler.to_public()` construye el `ErrorOutput` de Scrum 1.

La causa original se conserva en `ApplicationError.cause` y en el encadenamiento interno, pero nunca se incluye en la salida pública.

## Correlación

El handler conserva el `correlation_id` del error o del `ExecutionContext`. Si ninguno existe, genera uno al construir la salida pública. El mismo identificador debe reutilizarse entre capas.

## Persistencia

`PersistenceContext.input_origin` indica si un fallo técnico proviene de datos recibidos. Esto permite distinguir un valor inválido del usuario de un defecto de implementación. La traducción utiliza SQLSTATE y diagnósticos estructurados; no depende del texto de la excepción.

El handler no ejecuta transacciones, reintentos ni operaciones de recuperación.
