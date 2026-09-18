# gearctl — Control universal de mouse y teclado

**gearctl** es un aplicativo de escritorio multiplataforma (**Linux** y **Windows**)
para controlar y personalizar mouse y teclado: iluminación **RGB**, **teclas
programables/macros**, DPI y perfiles — todo desde un **único panel de control**,
sin depender de una app distinta por cada fabricante.

## El problema que resuelve

Cada fabricante obliga a usar su propio software (Logitech G HUB, Corsair iCUE,
Razer Synapse), y la mayoría **no existe en Linux** o no se hablan entre sí.
Si tienes un mouse Logitech y un teclado Razer, hoy necesitas dos programas
distintos — y en Linux, probablemente ninguno funcione.

**gearctl** unifica eso: detecta lo que conectes, averigua qué puede hacer y te
lo ofrece en una sola interfaz, usando el SDK oficial cuando existe y un
backend genérico (OpenRGB / HID) cuando no.

## ¿Cómo funciona?

```
Conectas un periférico
        ↓
1. Detección automática por VID:PID (quién es: marca y modelo)
        ↓
2. Consulta al catálogo: ¿soporta RGB? ¿macros? ¿qué SDK usa?
        ↓
3a. Si hay soporte → se activa el SDK del fabricante u OpenRGB
3b. Si no hay soporte → fallback HID (funciones básicas, sin romperse)
        ↓
4. Panel de control Qt con las opciones disponibles para ese dispositivo
```

## Características

- **Detección hotplug**: reconoce mouse/teclado al conectarse (udev en Linux, WinUSB en Windows, hidapi como respaldo).
- **Catálogo de modelos**: base local (+ sincronización remota opcional) que indica capacidades RGB/macros por VID:PID.
- **SDKs de fabricante**: Razer/OpenRazer (D-Bus), Logitech G HUB, Corsair iCUE — con degradación automática a fallback si el daemon no está activo.
- **RGB genérico** vía OpenRGB: color uniforme, modo Direct, detección de zonas/LEDs.
- **Seguridad**: los drivers descargados solo viajan por HTTPS y se verifican por SHA-256 antes de usarse; nada no verificado se ejecuta.
- **Instalador Windows**: script PowerShell que instala dependencias, compila con PyInstaller y crea acceso directo en Escritorio y Menú Inicio.

## Estado del proyecto

Proyecto en desarrollo activo (~v0.1, esqueleto funcional). La hoja de ruta
completa está en [`PLAN.md`](PLAN.md): control real de DPI, grabación de
macros, motor de efectos RGB, perfiles con auto-switch por aplicación,
bandeja del sistema, tests/CI e instaladores profesionales.

## Requisitos

- Python 3.10+
- Windows 10/11 o Linux con permisos de dispositivo
- (Opcional) Daemon de **OpenRGB** en ejecución para el control RGB

## Instalación y ejecución

```bash
# Crear entorno virtual e instalar dependencias
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Ejecutar
python main.py
```

> En Linux puede requerir pertenecer al grupo `input`/`plugdev` para acceder a
> los periféricos.

## Instalación en Windows

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\install.ps1
```

El script instala dependencias, compila con `pyinstaller --onefile main.py` y
crea `gearctl.lnk` en el **Escritorio** y el **Menú Inicio**.

## Seguridad

- Descargas de drivers solo por **HTTPS** (`src/gearctl/security.py`).
- Verificación **SHA-256** contra huellas del publicador antes de cualquier uso.
- El programa nunca ejecuta firmware/drivers no verificados.
- Pendiente: poblar `SecurityPolicy.TRUSTED_PUBLISHERS` con huellas reales.

## Estructura

```
main.py                     # punto de entrada
requirements.txt
install.ps1                 # instalador Windows + acceso directo
PLAN.md                     # hoja de ruta del proyecto
README.md
src/gearctl/
  security.py               # validación de drivers/firmware
  deteccion/detector.py     # VID/PID + hotplug (udev/WinUSB/hidapi)
  db/models.py              # modelos: capacidades y dispositivo
  db/device_db.py           # catálogo local
  db/cloud_db.py            # sincronización con nube
  drivers/manager.py        # selección de backend (SDK/OpenRGB/HID)
  drivers/vendor_sdks.py    # bindings OpenRazer, G HUB, iCUE
  rgb/openrgb.py            # backend OpenRGB
  gui/control_bus.py        # capa de servicios
  gui/app_window.py         # panel de control Qt
```
