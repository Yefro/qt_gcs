from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gcs.config.connection_settings import ConnectionSettings


class ConnectionSettingsDialog(QDialog):
    def __init__(self, settings: ConnectionSettings, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Settings - Connection")
        self.setMinimumWidth(520)
        self._connections = [dict(item) for item in settings.connections]
        self._active_index = settings.active_index

        root = QGridLayout(self)

        self.list_widget = QListWidget()
        root.addWidget(QLabel("Conexiones"), 0, 0)
        root.addWidget(self.list_widget, 1, 0)

        form_box = QGroupBox("Detalles")
        form_layout = QFormLayout(form_box)

        self.name_input = QLineEdit()
        self.rx_ip_input = QLineEdit()
        self.rx_port_input = QSpinBox()
        self.rx_port_input.setRange(1, 65535)
        self.tx_ip_input = QLineEdit()
        self.tx_port_input = QSpinBox()
        self.tx_port_input.setRange(1, 65535)
        self.auto_connect_input = QCheckBox("Auto conectar al iniciar")

        form_layout.addRow("Nombre", self.name_input)
        form_layout.addRow("RX IP", self.rx_ip_input)
        form_layout.addRow("RX Puerto", self.rx_port_input)
        form_layout.addRow("TX IP", self.tx_ip_input)
        form_layout.addRow("TX Puerto", self.tx_port_input)
        form_layout.addRow("", self.auto_connect_input)

        root.addWidget(form_box, 0, 1, 2, 1)

        button_bar = QWidget()
        button_layout = QVBoxLayout(button_bar)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)

        self.add_button = QPushButton("Agregar")
        self.remove_button = QPushButton("Eliminar")
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addStretch(1)
        root.addWidget(button_bar, 1, 0, alignment=Qt.AlignBottom)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        root.addWidget(self.button_box, 2, 0, 1, 2)

        self.add_button.clicked.connect(self._add_connection)
        self.remove_button.clicked.connect(self._remove_connection)
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        for widget in (
            self.name_input,
            self.rx_ip_input,
            self.rx_port_input,
            self.tx_ip_input,
            self.tx_port_input,
            self.auto_connect_input,
        ):
            if hasattr(widget, "textChanged"):
                widget.textChanged.connect(self._on_field_changed)
            elif hasattr(widget, "valueChanged"):
                widget.valueChanged.connect(self._on_field_changed)
            else:
                widget.stateChanged.connect(self._on_field_changed)

        self._reload_list()
        if self._connections:
            index = min(max(self._active_index, 0), len(self._connections) - 1)
            self.list_widget.setCurrentRow(index)

    def settings(self) -> ConnectionSettings:
        index = self.list_widget.currentRow()
        if index < 0:
            index = 0
        return ConnectionSettings(connections=self._connections, active_index=index)

    def _reload_list(self):
        self.list_widget.clear()
        for item in self._connections:
            name = item.get("name") or "(sin nombre)"
            self.list_widget.addItem(name)

    def _add_connection(self):
        self._connections.append(
            {
                "name": "Nueva",
                "rx_ip": "0.0.0.0",
                "rx_port": 14550,
                "tx_ip": "127.0.0.1",
                "tx_port": 14550,
                "auto_connect": False,
            }
        )
        self._reload_list()
        self.list_widget.setCurrentRow(len(self._connections) - 1)

    def _remove_connection(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        self._connections.pop(row)
        if not self._connections:
            self._add_connection()
            return
        self._reload_list()
        self.list_widget.setCurrentRow(min(row, len(self._connections) - 1))

    def _on_selection_changed(self, row: int):
        if row < 0 or row >= len(self._connections):
            return
        item = self._connections[row]
        self.name_input.blockSignals(True)
        self.rx_ip_input.blockSignals(True)
        self.rx_port_input.blockSignals(True)
        self.tx_ip_input.blockSignals(True)
        self.tx_port_input.blockSignals(True)
        self.auto_connect_input.blockSignals(True)

        self.name_input.setText(item.get("name", ""))
        self.rx_ip_input.setText(item.get("rx_ip", ""))
        self.rx_port_input.setValue(int(item.get("rx_port", 14550)))
        self.tx_ip_input.setText(item.get("tx_ip", ""))
        self.tx_port_input.setValue(int(item.get("tx_port", 14550)))
        self.auto_connect_input.setChecked(bool(item.get("auto_connect", False)))

        self.name_input.blockSignals(False)
        self.rx_ip_input.blockSignals(False)
        self.rx_port_input.blockSignals(False)
        self.tx_ip_input.blockSignals(False)
        self.tx_port_input.blockSignals(False)
        self.auto_connect_input.blockSignals(False)

    def _on_field_changed(self, *args):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self._connections):
            return
        item = self._connections[row]
        item["name"] = self.name_input.text().strip() or "(sin nombre)"
        item["rx_ip"] = self.rx_ip_input.text().strip()
        item["rx_port"] = int(self.rx_port_input.value())
        item["tx_ip"] = self.tx_ip_input.text().strip()
        item["tx_port"] = int(self.tx_port_input.value())
        item["auto_connect"] = bool(self.auto_connect_input.isChecked())
        self._reload_list()
        self.list_widget.setCurrentRow(row)
