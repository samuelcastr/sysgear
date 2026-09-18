from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from typing import Callable, List, Optional

from ..db.models import DetectedDevice
from ..db.device_db import DeviceDatabase


def _is_linux() -> bool:
    return sys.platform.startswith("linux")


def _is_windows() -> bool:
    return sys.platform.startswith("win")


class HardwareError(Exception):
    pass


class DetectionSource(ABC):
    """Fuente de enumeración de periféricos HID/USB."""

    @abstractmethod
    def list_devices(self) -> List[DetectedDevice]:
        raise NotImplementedError

    def display_name(self) -> str:
        return self.__class__.__name__


class HidApiSource(DetectionSource):
    """Enumeración multiplataforma vía hidapi (pyhidapi)."""

    def list_devices(self) -> List[DetectedDevice]:
        try:
            import hid  # https://github.com/adafruit/python-hid
        except ImportError as exc:
            raise HardwareError(
                "pyhidapi no disponible. Instale: pip install hidapi") from exc

        devices: List[DetectedDevice] = []
        for info in hid.enumerate(0, 0):  # todos los dispositivos
            if not isinstance(info, dict):
                continue
            devices.append(DetectedDevice(
                vendor_id=info.get("vendor_id", 0),
                product_id=info.get("product_id", 0),
                vendor=info.get("manufacturer_string") or "Desconocido",
                product=info.get("product_string") or "Periférico",
                path=info.get("path"),
            ))
        return devices


class UdevSource(DetectionSource):
    """Detección en Linux basada en udev (netlink / bloques de entrada)."""

    UDEV_TYPE_RE = (
        # Gamepads / ratones / teclados emplean el driver input de kernel
    )

    def list_devices(self) -> List[DetectedDevice]:
        if not _is_linux():
            raise HardwareError("udev solo está disponible en Linux.")
        # Lector opcional: si libudev no está, se degrada a /sys bus.
        try:
            import pyudev  # opcional, no se exige como dependencia base
            return self._via_pyudev(pyudev)
        except ImportError:
            return self._via_sysfs()

    def _via_pyudev(self, pyudev) -> List[DetectedDevice]:
        context = pyudev.Context()
        devices: List[DetectedDevice] = []
        for dev in context.list_devices(subsystem="input",
                                        ID_INPUT_MOUSE="1"):
            vid = dev.attributes.get("idVendor") or dev.get("ID_VENDOR_ID")
            pid = dev.attributes.get("idProduct") or dev.get("ID_MODEL_ID")
            if not vid or not pid:
                continue
            devices.append(DetectedDevice(
                vendor_id=int(vid, 16),
                product_id=int(pid, 16),
                vendor=dev.get("ID_VENDOR") or "Desconocido",
                product=dev.get("ID_MODEL") or "Periférico",
                path=dev.device_node or dev.device_path,
            ))
        # Eliminar duplicados del mismo VID/PID (múltiples interfaces input)
        return self._dedupe(devices)

    def _via_sysfs(self) -> List[DetectedDevice]:
        base = "/sys/class/input"
        devices: List[DetectedDevice] = []
        if not os.path.isdir(base):
            return devices
        try:
            import glob
            for node in glob.glob(os.path.join(base, "mouse*")):
                vid = self._read_sysattr(node, "device/id/vendor")
                pid = self._read_sysattr(node, "device/id/product")
                if not vid or not pid:
                    continue
                devices.append(DetectedDevice(
                    vendor_id=int(vid, 16),
                    product_id=int(pid, 16),
                    vendor=os.path.basename(node),
                    product=os.path.basename(node),
                    path=node,
                ))
        except OSError:
            return devices
        return self._dedupe(devices)

    @staticmethod
    def _read_sysattr(base: str, rel: str) -> Optional[str]:
        path = os.path.join(base, rel)
        try:
            with open(path, "r") as fh:
                return fh.read().strip()
        except (OSError, FileNotFoundError):
            return None

    @staticmethod
    def _dedupe(devices: List[DetectedDevice]) -> List[DetectedDevice]:
        seen: set[str] = set()
        result: List[DetectedDevice] = []
        for dev in devices:
            if dev.key not in seen:
                seen.add(dev.key)
                result.append(dev)
        return result


class WinUsbSource(DetectionSource):
    """Enumeración en Windows vía WinUSB / pyusb."""

    def list_devices(self) -> List[DetectedDevice]:
        if not _is_windows():
            raise HardwareError("WinUSB solo está disponible en Windows.")
        try:
            import usb.core  # pyusb
        except ImportError as exc:
            raise HardwareError(
                "pyusb no disponible. Instale: pip install pyusb") from exc

        devices: List[DetectedDevice] = []
        for device in usb.core.find(find_all=True):
            devices.append(DetectedDevice(
                vendor_id=device.idVendor or 0,
                product_id=device.idProduct or 0,
                vendor=device.manufacturer or "Desconocido",
                product=device.product or "Periférico",
                path=hex(getattr(device, "bus", 1)) + ":" + hex(getattr(device, "address", 1)),
            ))
        return self._dedupe(devices)

    @staticmethod
    def _dedupe(devices: List[DetectedDevice]) -> List[DetectedDevice]:
        seen: set[str] = set()
        result: List[DetectedDevice] = []
        for dev in devices:
            if dev.key not in seen:
                seen.add(dev.key)
                result.append(dev)
        return result


class NodeDetector:
    """Orquesta la detección de dispositivos conectados (hotplug)."""

    def __init__(self,
                 db: Optional[DeviceDatabase] = None,
                 sources: Optional[List[DetectionSource]] = None,
                 refresh: bool = False):
        self.db = db or DeviceDatabase()
        self._sources = sources or self._default_sources()
        self._refresh = refresh
        self.listeners: List[Optional[Callable[[List[DetectedDevice]], None]]] = []

    def _default_sources(self) -> List[DetectionSource]:
        sources: List[DetectionSource] = []
        if _is_windows():
            sources.append(WinUsbSource())
            sources.append(HidApiSource())  # respaldo si pyusb falla
        else:
            sources.append(HidApiSource())
            sources.append(UdevSource())
        return sources

    def scan(self) -> List[DetectedDevice]:
        """Enumera los dispositivos conectados y les asigna capacidades."""
        found: List[DetectedDevice] = []
        errors = []
        for source in self._sources:
            try:
                found.extend(source.list_devices())
            except HardwareError as exc:
                errors.append(f"{source.display_name()}: {exc}")
        # Deduplicar entre distintas fuentes
        dedupe: dict[str, DetectedDevice] = {}
        for dev in found:
            key = (dev.key, dev.path)
            if key not in dedupe:
                dedupe[key] = dev
        result = list(dedupe.values())
        for dev in result:
            dev.capacities = self.db.lookup_device(dev)
        if errors:
            raise HardwareError("; ".join(errors))
        return result

    def start_hotplug(self, on_change) -> None:
        """Suscribe a eventos de conexión/desconexión (udev en Linux).

        En implementaciones sin daemon, se usa polling periódico.
        """
        self.listeners.append(on_change)
        if _is_linux():
            self._start_udev_hotplug()
        else:
            self._start_polling()

    def _start_udev_hotplug(self) -> None:
        try:
            import threading

            import pyudev

            def worker():
                context = pyudev.Context()
                monitor = pyudev.Monitor.from_netlink(context)
                monitor.filter_by(subsystem="input")
                for _ in monitor:
                    self._emit()

            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
        except ImportError:
            self._start_polling()

    def _start_polling(self, interval: float = 2.0) -> None:
        import time
        import threading

        def worker():
            previous = set(_key(d) for d in self.scan())
            while True:
                time.sleep(interval)
                try:
                    current = set(_key(d) for d in self.scan())
                except HardwareError:
                    continue
                if current != previous:
                    self._emit()
                    previous = current

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _emit(self) -> None:
        try:
            devices = self.scan()
        except HardwareError:
            devices = []
        for listener in self.listeners:
            if listener:
                listener(devices)


def _key(device: DetectedDevice) -> str:
    return f"{device.key}@{device.path}"


def default_detector(db: Optional[DeviceDatabase] = None) -> NodeDetector:
    return NodeDetector(db=db)