from __future__ import annotations

from typing import Dict, List, Optional

from .models import (
    BackendType,
    DeviceCapabilities,
    DetectedDevice,
    FirmwareMode,
)


def _pid(*, vid, pid, vendor, product, kind,
         mode=FirmwareMode.NONE, backend=BackendType.HID_FALLBACK,
         rgb_channels=0, profile_count=0, macro_keys=0, sdk=None):
    return DeviceCapabilities(
        vid_pid=f"{vid:04x}:{pid:04x}",
        vendor=vendor,
        vendor_id=vid,
        product_id=pid,
        product=product,
        kind=kind,
        mode=mode,
        backend=backend,
        rgb_channels=rgb_channels,
        profile_count=profile_count,
        macro_keys=macro_keys,
        manufacturer_sdk=sdk,
    )


class DeviceDatabase:
    """Catálogo local de modelos soportados y pasarela a una nube opcional."""

    def __init__(self, entries: Optional[List[DeviceCapabilities]] = None):
        self._entries: Dict[str, DeviceCapabilities] = {}
        self._seed_default()
        for entry in entries or []:
            self._entries[entry.key] = entry

    def _seed_default(self):
        """Catálogo base embebido (Logitech, Corsair, Razer, genéricos)."""
        base = [
            # --- Logitech G (backends reales se resolverían vía LGS/GHUB) ---
            _pid(vid=0x046d, pid=0xc539, vendor="Logitech",
                 product="G502 HERO", kind="mouse",
                 mode=FirmwareMode.RGB_MACROS,
                 backend=BackendType.SDK, rgb_channels=6,
                 profile_count=5, macro_keys=11, sdk="logitech_g"),
            _pid(vid=0x046d, pid=0xc092, vendor="Logitech",
                 product="G102/G203 LIGHTSYNC", kind="mouse",
                 mode=FirmwareMode.RGB_MACROS,
                 backend=BackendType.SDK, rgb_channels=1,
                 profile_count=1, macro_keys=6, sdk="libratbag"),
            _pid(vid=0x36ae, pid=0xfeab, vendor="SDINNOVATION",
                 product="Gaming Keyboard", kind="keyboard",
                 mode=FirmwareMode.NONE, backend=BackendType.HID_FALLBACK),
            _pid(vid=0x046d, pid=0xc545, vendor="Logitech",
                 product="PRO X Superlight", kind="mouse",
                 mode=FirmwareMode.RGB,
                 backend=BackendType.SDK, rgb_channels=4, sdk="logitech_g"),
            # --- Corsair iCUE ---
            _pid(vid=0x1b1c, pid=0x1b36, vendor="Corsair",
                 product="K70 RGB MX", kind="keyboard",
                 mode=FirmwareMode.RGB_MACROS,
                 backend=BackendType.SDK, rgb_channels=19,
                 profile_count=3, macro_keys=6, sdk="corsair_cue"),
            # --- Razer (OpenRazer / Cynosa lite en Linux) ---
            _pid(vid=0x1532, pid=0x022a, vendor="Razer",
                 product="DeathAdder Essential", kind="mouse",
                 mode=FirmwareMode.RGB,
                 backend=BackendType.SDK, rgb_channels=1,
                 profile_count=5, sdk="razer_openrazer"),
            _pid(vid=0x1532, pid=0x0225, vendor="Razer",
                 product="Cynosa Chroma", kind="keyboard",
                 mode=FirmwareMode.RGB_MACROS,
                 backend=BackendType.SDK, rgb_channels=3,
                 macro_keys=10, sdk="razer_openrazer"),
            # --- Genérico / fallback HID ---
            _pid(vid=0x046d, pid=0xc312, vendor="Logitech",
                 product="MX Master 2S", kind="mouse",
                 mode=FirmwareMode.NONE, backend=BackendType.HID_FALLBACK),
        ]
        for entry in base:
            self._entries[entry.key] = entry

    def lookup(self, vid: int, pid: int):
        KEY = f"{vid:04x}:{pid:04x}"
        return self._entries.get(KEY)

    def lookup_device(self, device: DetectedDevice):
        if isinstance(device, dict):
            device = self._from_dict(device)
        found = self.lookup(device.vendor_id, device.product_id)
        if found is None:
            found = DeviceCapabilities(
                vid_pid=device.key,
                vendor=device.vendor,
                vendor_id=device.vendor_id,
                product_id=device.product_id,
                product=device.product,
                kind="desconocido",
            )
        return found

    def _from_dict(self, data: dict) -> DetectedDevice:
        return DetectedDevice(
            vendor_id=data.get("vendor_id", 0),
            product_id=data.get("product_id", 0),
            vendor=data.get("vendor", "Desconocido"),
            product=data.get("product", "Periférico"),
            path=data.get("path"),
        )

    def add(self, entry: DeviceCapabilities) -> None:
        self._entries[entry.key] = entry

    def all(self) -> List[DeviceCapabilities]:
        return list(self._entries.values())

    def count(self) -> int:
        return len(self._entries)


def default_database() -> DeviceDatabase:
    return DeviceDatabase()