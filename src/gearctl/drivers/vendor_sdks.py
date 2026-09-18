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
# libratbag (Linux) — control real vía D-Bus del daemon ratbagd
# ---------------------------------------------------------------------------
class RatbagDriver(VendorDriver):
    """Control real de DPI, polling, botones y LED vía ``ratbagd``.

    Servicio D-Bus: ``org.freedesktop.ratbag1``.
    Requiere el daemon en ejecución (se auto-activa por D-Bus si está instalado).
    """

    vendor = "libratbag"
    BUS = "org.freedesktop.ratbag1"
    ROOT = "/org/freedesktop/ratbag1"
    PROPS = "org.freedesktop.DBus.Properties"

    def __init__(self, device: DetectedDevice):
        super().__init__(device)
        self._bus = None
        self._device_path: Optional[str] = None

    # --- conexión (GDBus, mismo patrón que ratbagctl) ---

    def _ensure(self):
        if self._bus is not None:
            return
        try:
            from gi.repository import Gio
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            props = Gio.DBusProxy.new_sync(
                bus, 0, None, self.BUS, self.ROOT,
                self.PROPS, None)
            devices = self._prop_get(props, "org.freedesktop.ratbag1.Manager",
                                     "Devices")
            want = f"usb:{self.device.vendor_id:04x}:{self.device.product_id:04x}:"
            for path in devices:
                dev_props = Gio.DBusProxy.new_sync(
                    bus, 0, None, self.BUS, path, self.PROPS, None)
                model = self._prop_get(
                    dev_props, "org.freedesktop.ratbag1.Device", "Model")
                if str(model).startswith(want):
                    self._bus = bus
                    self._device_path = str(path)
                    return
            raise DriverError(
                "Dispositivo no expuesto por ratbagd (¿soportado por libratbag?).")
        except DriverError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DriverError(f"ratbagd no disponible: {exc}") from exc

    @staticmethod
    def _prop_get(props_proxy, interface: str, prop: str):
        from gi.repository import GLib
        result = props_proxy.call_sync(
            "Get", GLib.Variant("(ss)", (interface, prop)), 0, -1, None)
        return result.unpack()[0]  # GDBus ya desenvuelve la variante

    def _get(self, path: str, interface: str, prop: str):
        from gi.repository import Gio
        props = Gio.DBusProxy.new_sync(
            self._bus, 0, None, self.BUS, path, self.PROPS, None)
        return self._prop_get(props, interface, prop)

    def _set(self, path: str, interface: str, prop: str,
             inner: "GLib.Variant") -> None:
        """Escribe una propiedad. `inner` debe tener el tipo declarado
        de la propiedad: p.ej. Variant('u', …) para ReportRate,
        Variant('v', Variant('u', …)) para Resolution (doble, como ratbagctl),
        Variant('(uuu)', …) para Color."""
        from gi.repository import Gio, GLib
        props = Gio.DBusProxy.new_sync(
            self._bus, 0, None, self.BUS, path, self.PROPS, None)
        payload = GLib.Variant("(ssv)", (interface, prop, inner))
        props.call_sync("Set", payload, 0, -1, None)

    def _call(self, path: str, interface: str, method: str,
              args=None) -> None:
        from gi.repository import Gio
        proxy = Gio.DBusProxy.new_sync(
            self._bus, 0, None, self.BUS, path, interface, None)
        proxy.call_sync(method, args, 0, -1, None)

    def _profiles(self) -> List[str]:
        self._ensure()
        return [str(p) for p in self._get(
            self._device_path, "org.freedesktop.ratbag1.Device", "Profiles")]

    def _active_profile(self) -> str:
        for path in self._profiles():
            if bool(self._get(path, "org.freedesktop.ratbag1.Profile", "IsActive")):
                return path
        return self._profiles()[0]

    def _resolutions(self, profile: str) -> List[str]:
        return [str(r) for r in self._get(
            profile, "org.freedesktop.ratbag1.Profile", "Resolutions")]

    def _commit(self) -> None:
        self._call(self._device_path, "org.freedesktop.ratbag1.Device",
                   "Commit", None)

    @property
    def available(self) -> bool:
        try:
            self._ensure()
            return True
        except DriverError:
            return False

    # --- VendorDriver ---

    def device_info(self) -> dict:
        self._ensure()
        profile = self._active_profile()
        return {
            "backend": "libratbag",
            "channel": "dbus",
            "device_path": self._device_path,
            "dpi": self.get_dpi(),
            "dpi_levels": self.list_dpi(),
            "report_rate": self.get_report_rate(),
            "report_rates": self.list_report_rates(),
        }

    def set_macro(self, key: str, sequence: str) -> None:
        raise FirmwareWarning(
            "Reasignación de botones vía ratbag pendiente en este ctl.")

    def set_rgb(self, color: int) -> None:
        self._ensure()
        r, g, b = _split(color)
        profile = self._active_profile()
        leds = self._get(profile, "org.freedesktop.ratbag1.Profile", "Leds")
        if not leds:
            raise FirmwareWarning("El dispositivo no expone LED vía ratbagd.")
        from gi.repository import GLib
        self._set(str(leds[0]), "org.freedesktop.ratbag1.Led", "Color",
                  GLib.Variant("(uuu)", (r, g, b)))
        self._commit()

    # --- Control real (Fase 1) ---

    def list_dpi(self) -> List[int]:
        """Niveles DPI disponibles del perfil activo."""
        self._ensure()
        profile = self._active_profile()
        levels = []
        for res in self._resolutions(profile):
            options = self._get(res, "org.freedesktop.ratbag1.Resolution",
                                "Resolutions")
            levels.append(int(self._get(res, "org.freedesktop.ratbag1.Resolution",
                                        "Resolution")))
        return levels

    def get_dpi(self) -> int:
        self._ensure()
        profile = self._active_profile()
        for res in self._resolutions(profile):
            if bool(self._get(res, "org.freedesktop.ratbag1.Resolution",
                              "IsActive")):
                return int(self._get(res, "org.freedesktop.ratbag1.Resolution",
                                     "Resolution"))
        raise DriverError("Sin resolución activa.")

    def set_dpi(self, dpi: int) -> None:
        """Fija el DPI activo.

        1. Si un slot ya tiene ese valor, solo se activa (no se reordena nada).
        2. Si no, se escribe en el slot activo.
        """
        self._ensure()
        from gi.repository import GLib
        profile = self._active_profile()
        slots = self._resolutions(profile)
        current = {res: int(self._get(res, "org.freedesktop.ratbag1.Resolution",
                                     "Resolution")) for res in slots}
        if dpi in current.values():
            target = next(res for res, val in current.items() if val == dpi)
            self._call(target, "org.freedesktop.ratbag1.Resolution",
                       "SetActive", None)
            self._commit()
            return
        active = self._active_profile_slot(profile, slots)
        options = [int(x) for x in self._get(
            active, "org.freedesktop.ratbag1.Resolution", "Resolutions")]
        if dpi not in options:
            raise DriverError(f"DPI {dpi} no soportado por este perfil.")
        self._set(active, "org.freedesktop.ratbag1.Resolution",
                  "Resolution", GLib.Variant("v", GLib.Variant("u", dpi)))
        self._commit()

    def _active_profile_slot(self, profile: str, slots: List[str]) -> str:
        for res in slots:
            if bool(self._get(res, "org.freedesktop.ratbag1.Resolution",
                              "IsActive")):
                return res
        _ = profile
        return slots[0]

    def list_report_rates(self) -> List[int]:
        self._ensure()
        profile = self._active_profile()
        return [int(x) for x in self._get(
            profile, "org.freedesktop.ratbag1.Profile", "ReportRates")]

    def get_report_rate(self) -> int:
        self._ensure()
        profile = self._active_profile()
        return int(self._get(profile, "org.freedesktop.ratbag1.Profile",
                             "ReportRate"))

    def set_report_rate(self, rate: int) -> None:
        self._ensure()
        profile = self._active_profile()
        if rate not in self.list_report_rates():
            raise DriverError(f"Polling {rate}Hz no soportado.")
        from gi.repository import GLib
        self._set(profile, "org.freedesktop.ratbag1.Profile", "ReportRate",
                  GLib.Variant("u", rate))
        self._commit()
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
    "libratbag": RatbagDriver,
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