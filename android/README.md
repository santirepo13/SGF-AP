# Cliente Android de SGF-AP

La implementación visual principal está en `main.py` y `client/flet_app.py`.
Flet ofrece preview con recarga automática (`flet run --android`) y empaquetado
(`flet build apk`); la configuración efectiva de Android está en
`pyproject.toml`.

Los archivos `AndroidManifest.xml` y `res/xml/network_security_config.xml` se
conservan como referencia para una futura plantilla Android personalizada. No se
copian automáticamente al APK de Flet mientras no se configure una plantilla
Flet propia.

La capa de estado y red está en `client/` y no depende de un toolkit visual.
Una pantalla Android puede enlazar sus controles a `RegistrationController`.

## Configuración de distribución

Antes de construir el APK, definir `API_USER` y `API_PASSWORD` solamente en el
entorno del proceso de construcción y ejecutar:

```bash
python android/build_config.py
```

El comando genera `client/packaged_config.py`, que está excluido del control de
versiones. `client.config.load_client_config()` lo usa en el APK; durante el
desarrollo utiliza `config.py` y `.env`.

`API_URL` y `API_PORT` permanecen separados (`http://87.239.135.39` y `8002`),
y el conector compone `http://87.239.135.39:8002/users/register`. El cliente
no solicita estas variables al ciudadano.

`AndroidManifest.xml` declara `android.permission.INTERNET` y la configuración
de seguridad de red limita el tráfico HTTP claro al servidor configurado. Las
credenciales incluidas en un APK permiten inspección por quien posea el
paquete; no deben tratarse como secretos.
