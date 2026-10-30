# Vista móvil en tiempo real

La interfaz ahora usa **Flet**, que es la opción de Python más cercana a Expo
para este proyecto:

- `flet run` abre una ventana de desarrollo con recarga automática.
- `flet run --web` abre la misma pantalla en el navegador.
- `flet run --android main.py` inicia el servidor móvil y muestra un QR para
  abrir el proyecto en la aplicación Flet del teléfono; al guardar cambios, la
  pantalla se actualiza en el dispositivo.
- `flet build apk` genera un APK instalable.

## Desarrollo

Desde la raíz del repositorio:

```powershell
py -m pip install -r mobile\requirements.txt
flet run --recursive --ignore-dirs .venv,tests,traceability_tests main.py
```

Para probarlo en un teléfono Android, el computador y el teléfono deben estar
en la misma red local:

```powershell
flet run --android main.py
```

El archivo `.env` local proporciona la configuración durante el desarrollo.
La pantalla no solicita las credenciales técnicas al ciudadano.

## Construcción del APK

Las credenciales técnicas se leen únicamente del entorno del proceso de build.
No deben escribirse en el código fuente ni en el repositorio:

```powershell
$env:API_USER = "<technical-user>"
$env:API_PASSWORD = "<technical-password>"
py android\build_config.py
flet build apk
```

`android/build_config.py` genera `client/packaged_config.py`, que está ignorado
por Git. Para publicar, revisar también la firma del APK y reemplazar la
configuración de credenciales por un mecanismo seguro del entorno de despliegue;
las credenciales Basic incluidas en un cliente distribuido pueden ser extraídas.

## Alternativas

Kivy/Buildozer puede producir APKs Python, pero no ofrece un flujo de preview
con QR y recarga tan directo. Si se necesitara la experiencia exacta de Expo,
la alternativa sería reescribir solo la vista en React Native/Expo y conservar
esta API Python.
