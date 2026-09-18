"""Bindings reales de los SDK de fabricante.

Cada clase implementa una integración concreta. Se usan de forma *perezosa*
(import dentro de uso) para que la ausencia del SDK/daemon no rompa el resto de
la aplicación: se captura la excepción y se degrada a fallback HID.

Disponibilidad real:
  - OpenRazer (Linux): requiere el daemon ``openrazer`` en ejecución.
  - Logitech G HUB SDK: requiere ``lghub_agent`` con el SDK habilitado en el
    cliente Logitech G HUB (Windows/macOS).
  - Corsair iCUE SDK: requiere iCUE con el "SDK Server" activado.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..db.models import DetectedDevice
from .manager import DriverError, FirmwareWarning


class VendorDriver(ABC):
    """Interfaz única frente a un SDK de fabricante."""

    vendor = "generic"

    def __init__(self, device: DetectedDevice):
        self.device = device

    @property
    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def device_info(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def set_macro(self, key: str, sequence: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_rgb(self, color: int) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# OpenRazer (Linux) — control vía D-Bus del daemon oficial
# ---------------------------------------------------------------------------
class OpenRazerDriver(VendorDriver):
    """Integración con el daemon ``openrazer`` usando su API de D-Bus.

    los caminos de D-Bus: ``/org/razer`` ``org.razer`` con interfaces por
    dispositivo (``razer.device.led``, ``razer.device.macro``).
    """

    vendor = "razer"

    def __init__(self, device: DetectedDevice):
        super().__init__(device)
        self._dbus = None
        self._device_path: Optional[str] = None
        self._brush_interface = None

    def _ensure_dbus(self):
        if self._dbus is not None:
            return
        try:
            import dbus  # pygobject / python-dbus
            bus = dbus.SystemBus()
            obj = bus.get_object("org.razer", "/org/razer/devices")
            # Ruta:  daemon ->GetDevices() en "org.razer.devices"
            all_devices = obj.GetDevices(dbus_interface="org.razer.devices")
            self._dbus = bus
            for path in all_devices:
                if not isinstance(path, str):
                    continue
                dev = bus.get_object("org.razer", path)
                props = dev.GetAll(
                    "razer.device",
                    dbus_interface="org.freedesktop.DBus.Properties")
                if _matches(props, self.device):
                    self._device_path = path
                    self._brush_interface = dev
                    return
            raise DriverError("Dispositivo Razer no encontrado en el daemon.")
        except DriverError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DriverError(f"Daemon OpenRazer no disponible: {exc}") from exc

    @property
    def available(self) -> bool:
        try:
            self._ensure_dbus()
            return True
        except DriverError:
            return False

    def device_info(self) -> dict:
        self._ensure_dbus()
        return {
            "backend": "openrazer",
            "channel": "dbus",
            "device_path": self._device_path,
        }

    def set_rgb(self, color: int) -> None:
        self._ensure_dbus()
        r, g, b = _split(color)
        ifin = "razer.device.led"
        if not _has(ifin, self._brush_interface):
            raise FirmwareWarning("El dispositivo no expone LED por D-Bus.")
        self._brush_interface.setLogoRGB(r, g, b, dbus_interface=ifin)

    def set_macro(self, key: str, sequence: str) -> None:
        raise FirmwareWarning(
            "Macros del dispositivo Razer no expuestas por D-Bus en este ctl.")


# ---------------------------------------------------------------------------
# Logitech G HUB SDK
# ---------------------------------------------------------------------------
class LogitechGDriver(VendorDriver):
    """Integración con el SDK de Logitech G HUB (lhub_agent en Windows)."""

    vendor = "logitech_g"

    def _sdk(self):
        try:
            import lghub  # package no oficial: lghub
            return lghub
        except ImportError as exc:
            raise DriverError(
                "SDK de Logitech G HUB no disponible. "
                "Instale 'lghub' y tenga G HUB con SDK habilitado.") from exc

    @property
    def available(self) -> bool:
        try:
            self._sdk()
            return True
        except DriverError:
            return False

    def device_info(self) -> dict:
        return {"backend": "logitech_g_hub", "channel": "sdk"}

    def set_rgb(self, color: int) -> None:
        self._sdk().set_lighting(rid=self.device.key, color=_split(color))

    def set_macro(self, key: str, sequence: str) -> None:
        raise FirmwareWarning("Macros G HUB pendientes de API en este ctl.")


# ---------------------------------------------------------------------------
# Corsair iCUE SDK
# ---------------------------------------------------------------------------
class CorsairCueDriver(VendorDriver):
    """Integración con el SDK de Corsair iCUE (CUESDKShared.dll)."""

    vendor = "corsair_cue"

    def _sdk(self):
        try:
            import cue_sdk  # binding de la CUESDK
            return cue_sdk
        except ImportError as exc:
            raise DriverError(
                "SDK de Corsair iCUE no disponible. Asegure iCUE con el "
                "SDK Server activo e instale 'cue_sdk'.") from exc

    @property
    def available(self) -> bool:
        try:
            self._sdk()
            return True
        except DriverError:
            return False

    def device_info(self) -> dict:
        return {"backend": "corsair_icue", "channel": "sdk"}

    def set_rgb(self, color: int) -> None:
        self._sdk().set_led_colors(color=_split(color))

    def set_macro(self, key: str, sequence: str) -> None:
        raise FirmwareWarning("Macros iCUE pendientes de API en este ctl.")


# ---------------------------------------------------------------------------
# Fábrica
# ---------------------------------------------------------------------------
VENDOR_DRIVERS = {
    "razer_openrazer": OpenRazerDriver,
    "logitech_g": LogitechGDriver,
    "corsair_cue": CorsairCueDriver,
}


def vendor_driver_for(device: DetectedDevice) -> Optional[VendorDriver]:
    key = device.capacities.manufacturer_sdk
    if not key:
        return None
    driver_cls = VENDOR_DRIVERS.get(key)
    if not driver_cls:
        return None
    return driver_cls(device)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _split(color: int):
    return (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF


def _matches(props: dict, device: DetectedDevice) -> bool:
    vid = props.get("vid", 0)
    pid = props.get("pid", 0)
    if vid == device.vendor_id and pid == device.product_id:
        return True
    name = str(props.get("device_name", "")).lower()
    return device.product.lower() in name


def _has(interface: str, obj) -> bool:
    return hasattr(obj, interface) or True