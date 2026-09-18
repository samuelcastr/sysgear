from __future__ import annotations

import hashlib
import re
import ssl
import tempfile
import urllib.request
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class TrustLevel(Enum):
    ALLOWED = "allowed"        # Huella verificada y firmada
    UNKNOWN = "unknown"        # Sin verificación disponible
    BLOCKED = "blocked"        # No coincide con ninguna huella conocida


@dataclass
class Verdict:
    level: TrustLevel
    message: str
    sha256: Optional[str] = None
    size: int = 0


class IntegrityError(Exception):
    pass


class SecurityPolicy:
    """Valida drivers y firmware descargados antes de la ejecución."""

    # TODO: poblarlo con claves públicas y huellas publicadas oficiosamente.
    TRUSTED_PUBLISHERS = {
        # nombre -> huella SHA256 de una build oficial conocida
        "logitech": "ab12cd34...",  # placeholder
        "corsair": "cd12ef34...",
        "razer": "ef12ab34...",
    }

    ALLOWED_EXTENSIONS = {".exe", ".inf", ".sys", ".bin", ".zip"}

    def __init__(self, verify_tls: bool = True):
        self.verify_tls = verify_tls
        self._context = self._build_context()

    def _build_context(self):
        if not self.verify_tls:
            return ssl._create_unverified_context()  # noqa: SLF001
        return ssl.create_default_context()

    # --- Descarga ---

    def fetch_driver(self, url: str, expected_sha256: Optional[str] = None,
                     publisher: Optional[str] = None) -> Verdict:
        """Descarga un driver y devuelve un veredicto de integridad.

        Nunca ejecuta nada: solo descarga y verifica la huella. El llamante
        decide (con el veredicto) si procede a instalarlo.
        """
        if not url.lower().startswith(("https://", "https://")):
            return Verdict(TrustLevel.BLOCKED,
                           "Solo se admiten descargas por HTTPS.")

        req = urllib.request.Request(
            url, headers={"User-Agent": "gearctl/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20,
                                        context=self._context) as resp:
                payload = resp.read()
        except Exception as exc:  # noqa: BLE001
            raise IntegrityError(f"Fallo de descarga: {exc}") from exc

        digest = hashlib.sha256(payload).hexdigest()
        size = len(payload)

        if expected_sha256:
            if _consttime_eq(digest, expected_sha256):
                return Verdict(TrustLevel.ALLOWED, "Huella SHA-256 verificada.",
                               digest, size)
            return Verdict(TrustLevel.BLOCKED,
                           "Huella no coincide con la esperada.", digest, size)

        if publisher:
            known = self.TRUSTED_PUBLISHERS.get(publisher)
            if known and _consttime_eq(digest, known):
                return Verdict(TrustLevel.ALLOWED,
                               "Publicador conocido verificado.", digest, size)

        return Verdict(TrustLevel.UNKNOWN,
                       "Sin huella de referencia; descargado pero no verificado.",
                       digest, size)

    # --- Verificación de archivo local ---

    def verify_file(self, path: str, expected_sha256: str) -> Verdict:
        p = Path(path)
        if not p.is_file():
            return Verdict(TrustLevel.BLOCKED, "Archivo no encontrado.")
        if p.suffix.lower() not in self.ALLOWED_EXTENSIONS:
            return Verdict(TrustLevel.BLOCKED,
                           f"Extensión no permitida: {p.suffix}")
        digest = _sha256_file(p)
        if _consttime_eq(digest, expected_sha256):
            return Verdict(TrustLevel.ALLOWED,
                           "Archivo local verificado.", digest, p.stat().st_size)
        return Verdict(TrustLevel.BLOCKED,
                       "Huella local no coincide.", digest, p.stat().st_size)

    # --- Sanitización de rutas de ejecución ---

    @staticmethod
    def is_safe_exec(entry_point: str) -> bool:
        """Política mínima: no ejecutar rutas relativas ni comandos con args."""
        entry = entry_point.strip()
        if any(ch in entry for ch in " ;&|`$"):
            return False
        if re.match(r"^[./~]|\\\\", entry):
            return False
        suffix = Path(entry.split()[0] if " " in entry else entry).suffix.lower()
        return suffix in {".exe", ".bat", ".sh"}


def _consttime_eq(a: str, b: str) -> bool:
    import hmac
    return hmac.compare_digest(a.lower(), b.lower())


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()