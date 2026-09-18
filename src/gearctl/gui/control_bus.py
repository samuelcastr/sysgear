from __future__ import annotations

import logging
from typing import List

from ..db import models
from ..deteccion.detector import NodeDetector
from ..drivers.manager import DriverManager

log = logging.getLogger("gearctl.bus")


class NotFoundError(Exception):
    pass


class ControlBus:
    """Capa de servicios que conecta GUI con detección y drivers."""

    def __init__(self,
                 detector: NodeDetector,
                 drivers: DriverManager):
        self.detector = detector
        self.drivers = drivers
        self._devices: List[models.DetectedDevice] = []

    # --- detección ---

    def refresh(self) -> List[models.DetectedDevice]:
        try:
            self._devices = self.detector.scan()
        except Exception as exc:  # noqa: BLE001
            log.warning("Detección fallida: %s", exc)
            self._devices = []
            raise
        self.drivers.update_devices(self._devices)
        return self._devices

    def watch(self, on_change) -> None:
        self.detector.start_hotplug(on_change)

    def device(self, device_id: str) -> models.DetectedDevice:
        for dev in self._devices:
            if dev.key == device_id:
                return dev
        raise NotFoundError(f"Dispositivo {device_id} no conectado.")

    # --- acciones de control ---

    def set_macro(self, device_id: str, key: str, sequence: str) -> None:
        dev = self.device(device_id)
        backend = self.drivers.resolve(dev)
        backend.set_macro(key, sequence)

    def set_rgb(self, device_id: str, r: int, g: int, b: int) -> None:
        dev = self.device(device_id)
        backend = self.drivers.resolve(dev)
        color = (r << 16) | (g << 8) | b
        backend.set_rgb(color)

    def device_openrgb(self, device_id: str):
        dev = self.device(device_id)
        backend = self.drivers.resolve(dev)
        return backend