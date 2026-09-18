"""gearctl — Aplicativo de escritorio universal para control de mouse y teclado.

Flujo implementado:
  Detección VID/PID  ->  Base de datos soporta/fallback  ->  Drivers SDK alternativos
  ->  OpenRGB (RGB genérico)  ->  Interfaz Qt multiplataforma  ->  Instalador Windows

Framework de detección: pyusb/hidapi + udev (Linux) / WinUSB (Windows).
"""

__version__ = "0.1.0"
__app_name__ = "gearctl"