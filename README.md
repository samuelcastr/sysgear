# gearctl

Aplicativo de escritorio **universal** para controlar mouse y teclado (RGB y
teclas programables) en **Windows** y **Linux**.

El flujo está modularizado tal y como pide el requisito:

```
Detector (VID/PID)  →  Base de datos (¿soporta RGB/macros?)  →  Driver/SDK
      ↓                                                                  ↓
  Udev / WinUSB / hidapi                                            fallback HID
                                                                          ↓
                                                       OpenRGB (RGB genérico) ←─ RGB
                                                                          ↓
                                               Interfaz Qt multiplataforma (GUI)
                                                                          ↓
                                          Script de instalación Windows + acceso directo
```

---

## Flujo modular

| Paso | Módulo | Responsabilidad |
|------|--------|-----------------|
| 1. Detección | `src/gearctl/deteccion/` | Enumera periféricos por **VID:PID** usando udev (Linux), WinUSB/pyusb (Windows) y hidapi como respaldo. |
| 2. BD | `src/gearctl/db/` | Catálogo local de modelos + sincronización con nube opcional. Marca si cada modelo soporta RGB/macros. |
| 3. Driver/SDK | `src/gearctl/drivers/` | Selecciona backend: SDK de fabricante, OpenRGB o **fallback HID**. |
| 4. Fallback | `src/gearctl/deteccion/` | Sin soporte → solo funcionalidad HID básica. |
| 5. RGB | `src/gearctl/rgb/` | Backend **OpenRGB** para control genérico de luces. |
| 6. GUI | `src/gearctl/gui/` | Panel de control unificado (Qt/PySide6) multiplataforma. |
| 7. Instalador | `install.ps1` | Instala dependencias, compila y crea acceso directo en Windows. |
| 8. Seguridad | `src/gearctl/security.py` | Valida drivers/firmware descargados (HTTPS + huella SHA-256). |

Los **SDK de fabricante** se integran en `src/gearctl/drivers/vendor_sdks.py`:

| SDK | Módulo | Requisito en ejecución |
|-----|--------|------------------------|
| Razer/OpenRazer | `OpenRazerDriver` | Daemon `openrazer` vía D-Bus (Linux) |
| Logitech G HUB | `LogitechGDriver` | G HUB con el SDK habilitado |
| Corsair iCUE | `CorsairCueDriver` | iCUE con el "SDK Server" activo |

Si el daemon/servidor del SDK **no está disponible**, el dispositivo se degrada
automáticamente y sin errores a **fallback HID**.

---

## Requisitos

- Python 3.10+
- Windows 10/11 o Linux con permisos de dispositivo
- (Opcional) Daemon de **OpenRGB** en ejecución para el control RGB

Instalación de dependencias:

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
# Linux / Windows
python main.py
```

> En Linux es recomendable ejecutar desde el grupo `input`/`plugdev` para
> acceder a los periféricos; también puede requerir permisos udev.

## Instalación en Windows (acceso directo)

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\install.ps1
```

El script:

1. Instala `requirements.txt` con `pip`.
2. Compila con `pyinstaller --onefile main.py` → `dist/gearctl.exe`.
3. Crea `gearctl.lnk` en el **Escritorio** y en el **Menú Inicio**.

Para un instalador profesional, `install.ps1` es el precursor; seguirlo con un
`.iss` de Inno Setup sobre `dist/gearctl.exe`.

## Seguridad

- Descargas de drivers solo por **HTTPS** (`src/gearctl/security.py`).
- Toda descarga se verifica por **SHA-256** contra huellas conocidas del
  publicador antes de cualquier ejecución.
- El binario nunca ejecuta firmware/drivers no verificado (veredicto
  `TrustLevel`).
- Revisar `SecurityPolicy.TRUSTED_PUBLISHERS` para completar las huellas.
- Los SDK de fabricante se integran vía `drivers/vendor_sdks.py` (OpenRazer,
  Logitech G HUB, Corsair iCUE) con degradación a fallback.
- `SecurityPolicy.TRUSTED_PUBLISHERS` debe poblarse con huellas reales.

## Estructura

```
main.py                     # punto de entrada
requirements.txt
install.ps1                 # instalador Windows + acceso directo
README.md
src/gearctl/
  __init__.py
  security.py               # validación de drivers/firmware
  deteccion/detector.py     # VID/PID + hotplug (udev/WinUSB/hidapi)
  db/models.py              # dataclasses Capacidades/Dispositivo
  db/device_db.py           # catálogo local
  db/cloud_db.py            # sincronización con nube
  drivers/manager.py        # selección backend (SDK/OpenRGB/HID)
  rgb/openrgb.py            # backend OpenRGB
  gui/control_bus.py        # capa de servicios
  gui/app_window.py         # panel de control Qt
```

## Estado actual

Módulos core implementados y conectados por `ControlBus`. Los SDK de fabricante
tienen bindings reales en `drivers/vendor_sdks.py` (OpenRazer, Logitech G HUB,
Corsair iCUE) con degradación automática a fallback HID cuando el daemon o
servidor del SDK no está en ejecución. Para `set_macro`, algunos SDK requieren
completar el mapeo de teclas específico del fabricante.