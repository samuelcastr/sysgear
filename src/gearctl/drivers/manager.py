from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..db.models import BackendType, DetectedDevice, DeviceCapabilities


class DriverError(Exception):
    pass


class FirmwareWarning(DriverError):
    """Se lanza cuando se intenta aplicar firmware/driver no verificado."""


class DriverBackend(ABC):
    """Interfaz común de todos los controladores (SDK o HID)."""

    name = "base"

    def __init__(self, device: DetectedDevice):
        self.device = device
        self._initialized = False

    def setup(self) -> None:
        """Ligera inicialización; puede lanzar DriverError si no aplica."""
        self._initialized = True

    @property
    def available(self) -> bool:
        try:
            self.setup()
        except (DriverError, FirmwareWarning, ImportError):
            return False
        return self._initialized

    # --- Funciones expuestas a la GUI ---

    @abstractmethod
    def device_info(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def set_macro(self, key: str, sequence: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_rgb(self, color: int) -> None:
        raise NotImplementedError


class HIDFallbackBackend(DriverBackend):
    """Fallback base: solo lectura de información, sin personalización."""

    name = "hid-fallback"

    def setup(self) -> None:
        # El fallback nunca debe fallar: si no hay hidapi, solo informa sin
        # capacidad de E/S de bajo nivel (nunca se ejecuta por defecto).
        super().setup()

    def device_info(self) -> dict:
        return {
            "vid": f"{self.device.vendor_id:04x}",
            "pid": f"{self.device.product_id:04x}",
            "vendor": self.device.vendor,
            "product": self.device.product,
            "path": self.device.path,
            "backend": self.name,
        }

    def set_macro(self, key: str, sequence: str) -> None:
        raise FirmwareWarning(
            "Este dispositivo no soporta macros (fallback HID).")

    def set_rgb(self, color: int) -> None:
        raise FirmwareWarning(
            "Este dispositivo no expone control RGB por HID genérico.")


class OpenRGBBackend(DriverBackend):
    """Control RGB genérico delegado a OpenRGB (vía su SDK HTTP)."""

    name = "openrgb"

    def setup(self) -> None:
        import urllib.request  # noqa: F401
        super().setup()

    def device_info(self) -> dict:
        return {"backend": self.name,
                "rgb": "genérico vía OpenRGB",
                "device": self.device.product}

    def set_macro(self, key: str, sequence: str) -> None:
        raise FirmwareWarning("OpenRGB solo gestiona iluminación.")

    def set_rgb(self, color: int) -> None:
        # Control RGB genérico delegado a OpenRGB.
        from ..rgb.openrgb import RGBController
        with RGBController() as ctrl:
            for device_id in ctrl.device_ids():
                ctrl.set_device_color(device_id,
                                      (color >> 16) & 0xFF,
                                      (color >> 8) & 0xFF,
                                      color & 0xFF)


class VendorSDKBackend(DriverBackend):
    """Capa frente a SDKs oficiales (Logitech G HUB, Corsair CUE, OpenRazer)."""

    name = "vendor-sdk"

    def __init__(self, device: DetectedDevice):
        super().__init__(device)
        self._driver = None

    def setup(self) -> None:
        sdk = self.device.capacities.manufacturer_sdk
        if not sdk:
            raise DriverError("SDK de fabricante no declarado para este modelo.")
        from .vendor_sdks import vendor_driver_for  # lazy import
        self._driver = vendor_driver_for(self.device)
        if self._driver is None:
            raise DriverError(
                f"No hay binding para el SDK '{sdk}' de este modelo.")
        if not self._driver.available:
            raise DriverError(
                f"SDK '{sdk}' declarado pero su daemon/servidor no está "
                "disponible. Se usará el fallback HID.")
        super().setup()

    def device_info(self) -> dict:
        return {
            "backend": self.name,
            "sdk": self.device.capacities.manufacturer_sdk,
            "kind": self.device.capacities.kind,
            "mode": self.device.capacities.mode.value,
            "vendor_driver": (self._driver.device_info()
                              if self._driver else None),
        }

    def set_macro(self, key: str, sequence: str) -> None:
        if not self.device.capacities.macro_keys:
            raise FirmwareWarning("Este modelo no soporta macros por SDK.")
        if self._driver is None:
            raise DriverError("SDK no inicializado.")
        self._driver.set_macro(key, sequence)

    def set_rgb(self, color: int) -> None:
        if not self.device.capacities.rgb_channels:
            raise FirmwareWarning("Este modelo no expone RGB por su SDK.")
        if self._driver is None:
            raise DriverError("SDK no inicializado.")
        self._driver.set_rgb(color)


def backend_for(device: DetectedDevice,
                backend_type: Optional[BackendType] = None) -> DriverBackend:
    """Selecciona el backend adecuado (SDK -> OpenRGB -> fallback HID)."""
    caps: DeviceCapabilities = device.capacities
    chosen = backend_type or caps.backend

    if chosen == BackendType.SDK:
        return VendorSDKBackend(device)
    if chosen == BackendType.OPENRGB:
        return OpenRGBBackend(device)
    return HIDFallbackBackend(device)


class DriverManager:
    """Resuelve y gestiona el backend de cada dispositivo conectado."""

    def __init__(self):
        self._backends: dict[str, DriverBackend] = {}

    def resolve(self, device: DetectedDevice) -> DriverBackend:
        if device.key in self._backends:
            return self._backends[device.key]
        backend = backend_for(device)
        try:
            backend.setup()
        except (DriverError, FirmwareWarning, ImportError):
            backend = HIDFallbackBackend(device)
            backend.setup()
        self._backends[device.key] = backend
        return backend

    def release(self, device: DetectedDevice) -> None:
        self._backends.pop(device.key, None)

    def update_devices(self, devices: List[DetectedDevice]) -> None:
        keys = {d.key for d in devices}
        for key in list(self._backends):
            if key not in keys:
                del self._backends[key]


def default_manager() -> DriverManager:
    return DriverManager()