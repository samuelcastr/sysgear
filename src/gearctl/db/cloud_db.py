from __future__ import annotations

import hashlib
import json
from typing import List, Optional

from .device_db import DeviceDatabase
from .models import DeviceCapabilities


class CloudDBError(Exception):
    pass


class CloudDatabaseSync:
    """Sincroniza el catálogo desde una URL remota; la local actúa de respaldo."""

    def __init__(self, url: str = "", local_db: Optional[DeviceDatabase] = None,
                 allow_http: bool = True, timeout: float = 6.0):
        self.url = url
        self.local_db = local_db or DeviceDatabase()
        self._allow_http = allow_http
        self._timeout = timeout

    def _validate_url(self) -> None:
        if not self.url:
            return
        if not self.url.startswith("https://") and not self._allow_http:
            raise CloudDBError(
                "Conexión no segura: se requiere HTTPS para la base de datos remota.")

    def _digest(self, payload: bytes) -> str:
        # TODO: comparar contra checksum firmado publicado por el servidor
        return hashlib.sha256(payload).hexdigest()

    def fetch_and_merge(self, existing: Optional[List[DeviceCapabilities]] = None) -> List[DeviceCapabilities]:
        """Descarga el catálogo remoto y lo fusiona con el local.

        Uso de respaldo: si la nube no responde, se usa el catálogo local.
        """
        self._validate_url()
        if not self.url:
            return self.local_db.all()

        try:
            import urllib.request

            req = urllib.request.Request(
                self.url,
                headers={"User-Agent": "gearctl/1.0",
                         "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                payload = resp.read()

            digest = self._digest(payload)
            data = json.loads(payload.decode("utf-8"))
            # TODO: verificar digests con la clave pública del proveedor
            entries = self._parse_json(data)
            local_entries = (existing or self.local_db.all())
            return self._merge(entries, local_entries)
        except Exception as exc:  # noqa: BLE001 — fail-open a catálogo local
            if isinstance(exc, CloudDBError):
                raise
            return self.local_db.all()

    def _parse_json(self, data) -> List[DeviceCapabilities]:
        entries = []
        for item in data.get("devices", []):
            try:
                device = DeviceCapabilities(
                    vid_pid=item["vid_pid"],
                    vendor=item.get("vendor", "Desconocido"),
                    vendor_id=int(item["vendor_id"], 0),
                    product_id=int(item["product_id"], 0),
                    product=item.get("product", "Periférico"),
                    kind=item.get("kind", "mouse"),
                    mode=item.get("mode", "none"),
                    backend=item.get("backend", "hid"),
                    rgb_channels=int(item.get("rgb_channels", 0)),
                    profile_count=int(item.get("profile_count", 0)),
                    macro_keys=int(item.get("macro_keys", 0)),
                    manufacturer_sdk=item.get("sdk"),
                )
                entries.append(device)
            except (KeyError, ValueError):
                continue
        return entries

    def _merge(self, remote: List[DeviceCapabilities],
               local: List[DeviceCapabilities]) -> List[DeviceCapabilities]:
        merged = {e.key: e for e in local}
        for e in remote:
            merged[e.key] = e  # el remoto gana en conflicto
        return list(merged.values())

    def load_local_json(self, path: str) -> List[DeviceCapabilities]:
        """Carga el catálogo local desde un JSON (reseeds del catálogo opcional)."""
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        entries = self._parse_json(data)
        for entry in entries:
            self.local_db.add(entry)
        return entries