from __future__ import annotations

import logging

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover - dependencia alterna PyQt5
    try:
        from PyQt5 import QtCore, QtGui, QtWidgets  # type: ignore
    except ImportError:
        QtCore = QtGui = QtWidgets = None  # type: ignore

from ..db import models
from ..drivers.manager import FirmwareWarning
from .control_bus import ControlBus

log = logging.getLogger("gearctl.gui")


class DeviceStore(QtCore.QAbstractListModel):
    """Modelo Qt con la lista de periféricos conectados."""

    def __init__(self, bus: ControlBus, parent=None):
        super().__init__(parent)
        self.bus = bus
        self.items: list[models.DetectedDevice] = []

    def set_devices(self, devices: list[models.DetectedDevice]):
        self.beginResetModel()
        self.items = list(devices)
        self.endResetModel()

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        dev = self.items[index.row()]
        if role == QtCore.Qt.DisplayRole:
            tag = "✓" if dev.supported else "·"
            return f"{tag} {dev.vendor} {dev.product}  ({dev.key})"
        if role == QtCore.Qt.UserRole:
            return dev
        return None

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.items)


class MainWindow(QtWidgets.QMainWindow):
    """Panel de control unificado multiplataforma."""

    def __init__(self, bus: ControlBus):
        super().__init__()
        self.bus = bus
        self.setWindowTitle("gearctl — Control de mouse y teclado")
        self.resize(760, 480)

        layout = QtWidgets.QHBoxLayout()
        # Lista de dispositivos + detalle
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        self.store = DeviceStore(self.bus)
        self.device_list = QtWidgets.QListView()
        self.device_list.setModel(self.store)
        self.device_list.selectionModel().currentChanged.connect(self._on_select)
        splitter.addWidget(self.device_list)

        self.detail = self._build_detail()
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(1, 2)

        container = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(container)
        toolbar = self._build_toolbar()
        root.addWidget(toolbar)
        root.addWidget(splitter)
        self.setCentralWidget(container)

        self.status = self.statusBar()
        self._refresh()

    # --- construcción de controles ---

    def _build_toolbar(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QWidget()
        lay = QtWidgets.QHBoxLayout(bar)
        lay.setContentsMargins(8, 6, 8, 6)
        self.btn_refresh = QtWidgets.QPushButton("Actualizar")
        self.btn_refresh.clicked.connect(self._refresh)
        self.btn_openrgb = QtWidgets.QPushButton("RGB (OpenRGB)")
        self.btn_openrgb.clicked.connect(self._on_openrgb_clicked)
        disabled = QtWidgets.QLabel("Backend: HID fallback — SDK no vinculado")
        disabled.setStyleSheet("color:#888;")
        lay.addWidget(self.btn_refresh)
        lay.addWidget(self.btn_openrgb)
        lay.addStretch(1)
        lay.addWidget(disabled)
        return bar

    def _build_detail(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(panel)
        form.setContentsMargins(12, 12, 12, 12)

        self.info_vendor = QtWidgets.QLabel("-")
        self.info_product = QtWidgets.QLabel("-")
        self.info_vidpid = QtWidgets.QLabel("-")
        self.info_kind = QtWidgets.QLabel("-")
        self.info_support = QtWidgets.QLabel("-")

        form.addRow("Fabricante", self.info_vendor)
        form.addRow("Modelo", self.info_product)
        form.addRow("VID:PID", self.info_vidpid)
        form.addRow("Tipo", self.info_kind)
        form.addRow("Soporte", self.info_support)

        form.addRow("", QtWidgets.QLabel(""))  # separador

        self.rb_color = QtWidgets.QPushButton("Aplicar color RGB")
        self.rb_color.clicked.connect(self._on_apply_rgb)
        form.addRow(self.rb_color)

        self.cb_openrgb_dev = QtWidgets.QComboBox()
        form.addRow("Dispositivo RGB", self.cb_openrgb_dev)

        return panel

    # --- lógica ---

    def _refresh(self):
        try:
            devices = self.bus.refresh()
        except Exception as exc:  # noqa: BLE001
            self.status.showMessage(f"Error de detección: {exc}")
            devices = []
        self.store.set_devices(devices)
        self.status.showMessage(f"{len(devices)} dispositivo(s) detectado(s).")

    def _current(self) -> models.DetectedDevice | None:
        idx = self.device_list.selectionModel().currentIndex()
        dev = self.store.data(idx, QtCore.Qt.UserRole)
        return dev if dev else None

    def _on_select(self, current, *_):
        dev = self.store.data(current, QtCore.Qt.UserRole) if current.isValid() else None
        if not dev:
            for label in (self.info_vendor, self.info_product, self.info_vidpid,
                          self.info_kind, self.info_support):
                label.setText("-")
            return
        caps = dev.capacities
        self.info_vendor.setText(dev.vendor)
        self.info_product.setText(dev.product)
        self.info_vidpid.setText(dev.key)
        self.info_kind.setText(caps.kind)
        self.info_support.setText(
            f"{caps.mode.value} / backend {caps.backend.value}")

    def _on_apply_rgb(self):
        dev = self._current()
        if not dev:
            self.status.showMessage("Seleccione un dispositivo.")
            return
        try:
            color = QtGui.QColorDialog.getColor(QtGui.QColor(0, 255, 0), self)
            if not color.isValid():
                return
            self.bus.set_rgb(dev.key, color.red(), color.green(), color.blue())
            self.status.showMessage(
                f"Color aplicado a {dev.product} ({dev.key}).")
        except (FirmwareWarning, Exception) as exc:  # noqa: BLE001
            self.status.showMessage(f"No aplicado: {exc}")

    def _on_openrgb_clicked(self):
        try:
            from ..rgb.openrgb import RGBController, RGBError
            with RGBController() as ctrl:
                devices = ctrl.list_devices()
            self.cb_openrgb_dev.clear()
            for d in devices:
                self.cb_openrgb_dev.addItem(
                    f"{d['name']}  (leds: {d['leds']})", d["id"])
            self.status.showMessage(
                f"OpenRGB conectado: {len(devices)} dispositivo(s).")
        except (RGBError, ImportError) as exc:
            self.status.showMessage(f"OpenRGB no disponible: {exc}")


def run(bus: ControlBus) -> int:
    if QtWidgets is None:  # pragma: no cover
        log.error("Se requiere PySide6 (o PyQt5). Instale: pip install PySide6")
        return 1
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication()
    app.setApplicationName("gearctl")
    win = MainWindow(bus)
    win.show()
    return app.exec()