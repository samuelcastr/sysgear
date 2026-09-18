from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class FirmwareMode(Enum):
    """Capacidades de personalización de un dispositivo."""

    NONE = "none"            # Sin personalización, solo HID básico
    MACROS = "macros"        # Teclas programables / macros
    RGB = "rgb"              # Retroiluminación personalizable
    RGB_MACROS = "rgb_macros"  # RGB + teclas programables


class BackendType(Enum):
    """Backend de control que gestiona el dispositivo."""

    OPENRGB = "openrgb"        # Control RGB genérico vía OpenRGB
    SDK = "sdk"                # SDK/API oficial del fabricante
    HID_FALLBACK = "hid"      # Solo funcionalidad HID base


@dataclass
class DeviceCapabilities:
    """Funcionalidades de un modelo de dispositivo."""

    vid_pid: str = ""                 # Normalizado: "046d:c539"
    vendor: str = "Desconocido"
    vendor_id: int = 0
    product_id: int = 0
    product: str = "Periférico no identificado"
    kind: str = "mouse"               # mouse | keyboard
    mode: FirmwareMode = FirmwareMode.NONE
    backend: BackendType = BackendType.HID_FALLBACK
    rgb_channels: int = 0
    profile_count: int = 0
    macro_keys: int = 0
    manufacturer_sdk: Optional[str] = None

    @property
    def key(self) -> str:
        return f"{self.vendor_id:04x}:{self.product_id:04x}"


@dataclass
class DetectedDevice:
    """Dispositivo detectado en caliente."""

    vendor_id: int
    product_id: int
    vendor: str = "Desconocido"
    product: str = "Periférico no identificado"
    path: Optional[str] = None
    capacities: DeviceCapabilities = field(
        default_factory=DeviceCapabilities)
    is_connected: bool = True

    @property
    def key(self) -> str:
        return f"{self.vendor_id:04x}:{self.product_id:04x}"

    @property
    def supported(self) -> bool:
        return (
            self.capacities.mode != FirmwareMode.NONE
            or self.capacities.backend != BackendType.HID_FALLBACK
        )


def mode_supports_rgb(mode: FirmwareMode) -> bool:
    return mode in (FirmwareMode.RGB, FirmwareMode.RGB_MACROS)


def mode_supports_macros(mode: FirmwareMode) -> bool:
    return mode in (FirmwareMode.MACROS, FirmwareMode.RGB_MACROS)