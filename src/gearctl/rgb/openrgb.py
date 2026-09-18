from __future__ import annotations

from typing import List, Optional, Tuple


class RGBError(Exception):
    pass


def _try_import_openrgb():
    """Importa dinámicamente el cliente; deja pista si falta."""
    try:
        from openrgb import OpenRGBClient as _Base  # noqa: F401
        from openrgb.utils import RGBColor  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise RGBError(
            "Falta la librería 'openrgb-python'. "
            "Instale: pip install openrgb-python (o espere el backend propio)") from exc
    return _Base


class RGBController:
    """Control de iluminación universal basado en el SDK de OpenRGB.

    El backend lo provee la librería oficial 'openrgb-python', que habla el
    protocolo nativo de OpenRGB. Esto sustituye a un cliente HTTP propio.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 6743):
        self.host = host
        self.port = port
        self._client = None

    @property
    def connected(self) -> bool:
        return self._client is not None

    def connect(self):
        if self._client is not None:
            return
        base = _try_import_openrgb()
        # El puerto por defecto de la lib es 6742; aquí se depende de la lib.
        self._client = base(host=self.host, port=self.port)

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.disconnect()
            finally:
                self._client = None

    def __enter__(self) -> "RGBController":
        self.connect()
        return self

    def __exit__(self, *exc):  # noqa: ANN002
        self.close()

    def device_ids(self) -> List[int]:
        self.connect()
        return [d.id for d in self._client.devices]

    def list_devices(self) -> List[dict]:
        self.connect()
        result = []
        for dev in self._client.devices:
            result.append({
                "id": dev.id,
                "name": dev.name,
                "type": str(dev.type),
                "leds": len(dev.leds),
                "active_mode": getattr(dev.active_mode, "id", None),
            })
        return result

    def set_device_color(self, device_id: int, r: int, g: int, b: int) -> None:
        """Activa el modo Direct y aplica un color uniforme al dispositivo."""
        self.connect()
        from openrgb.utils import RGBColor
        target = self._find(device_id)
        if target is None:
            raise RGBError(f"Dispositivo RGB {device_id} no encontrado.")
        target.load_modes()
        direct = self._find_direct_mode(target)
        if direct is not None:
            target.set_mode(direct)
        target.set_color(RGBColor(r, g, b))

    @staticmethod
    def _find_direct_mode(device):
        try:
            from openrgb.utils import RGBMode
        except Exception:  # noqa: BLE001
            RGBMode = None  # type: ignore
        for mode in device.modes:
            name = getattr(mode, "name", "").lower()
            if name == "direct" or (RGBMode is not None
                                    and getattr(mode, "mode", None) == RGBMode.Direct):
                return mode
        return None

    def set_all_devices_color(self, r: int, g: int, b: int) -> None:
        for device_id in self.device_ids():
            self.set_device_color(device_id, r, g, b)

    def set_active_mode(self, device_id: int, mode_index: int,
                        brightness: Optional[int] = None) -> None:
        self.connect()
        target = self._find(device_id)
        if target is None:
            raise RGBError(f"Dispositivo RGB {device_id} no encontrado.")
        target.load_modes()
        mode = target.modes[mode_index]
        mode.brightness = brightness if brightness is not None else mode.brightness
        target.set_mode(mode)

    def _find(self, device_id: int):
        for dev in self._client.devices:
            if dev.id == device_id:
                return dev
        return None


def available_devices() -> List[dict]:
    """Devuelve la lista de dispositivos de iluminación (cómodo para la GUI)."""
    try:
        with RGBController() as ctrl:
            if ctrl.connected:
                return ctrl.list_devices()
    except RGBError:
        pass
    return []