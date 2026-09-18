"""gearctl — Punto de entrada del aplicativo de escritorio.

Uso:  python main.py  (o: pyinstaller main.py)
"""

from __future__ import annotations

import logging
import sys


def _bootstrap_path() -> None:
    """Permite ejecutar `python main.py` y con PyInstaller igualmente."""
    import os
    root = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(root, "src")
    if os.path.isdir(src) and src not in sys.path:
        sys.path.insert(0, src)


def main() -> int:
    _bootstrap_path()
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    from gearctl.db.device_db import default_database
    from gearctl.deteccion.detector import default_detector
    from gearctl.drivers.manager import default_manager
    from gearctl.gui.control_bus import ControlBus
    from gearctl.gui.app_window import run  # import tardío (PySide opcional)

    db = default_database()
    detector = default_detector(db)
    drivers = default_manager()
    bus = ControlBus(detector, drivers)

    return run(bus)


if __name__ == "__main__":
    sys.exit(main())