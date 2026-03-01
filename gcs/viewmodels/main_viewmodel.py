from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from gcs.config.connection_settings import (
    ConnectionSettings,
    load_connection_settings,
    save_connection_settings,
)
from gcs.mavlink.connection import MavlinkConnection
from gcs.mavlink.types import MavlinkEndpoint
from gcs.services.telemetry_service import TelemetryService


class MainViewModel(QObject):
    telemetry_updated = Signal(object)
    status_changed = Signal(str)
    connection_label_changed = Signal(str)
    connection_state_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._conn_settings = load_connection_settings()
        self._active_connection = self._get_active_connection(self._conn_settings)

        self._rx_bind_ip = self._active_connection["rx_ip"]
        self._rx_port = int(self._active_connection["rx_port"])
        rx_endpoint = MavlinkEndpoint(
            connection_string=f"udpin:{self._rx_bind_ip}:{self._rx_port}"
        )
        self.mav_connection = MavlinkConnection(rx_endpoint)
        self._tx_ip = self._active_connection["tx_ip"]
        self._tx_port = int(self._active_connection["tx_port"])
        self.telemetry = TelemetryService(
            self.mav_connection, tx_target=(self._tx_ip, self._tx_port)
        )

        self._telemetry_timer = QTimer(self)
        self._telemetry_timer.setInterval(200)
        self._telemetry_timer.timeout.connect(self._refresh_telemetry)
        self._telemetry_timer.start()

        self.connection_label_changed.emit(self._connection_label_text())
        QTimer.singleShot(0, self._maybe_auto_connect)

    def _refresh_telemetry(self):
        sample = self.telemetry.latest()
        if self.mav_connection.is_connected():
            if sample.has_fix:
                self.status_changed.emit("Conectado")
            else:
                self.status_changed.emit("Conectado (sin fix)")
        self.telemetry_updated.emit(sample)

    def toggle_connection(self):
        if self.telemetry.is_running():
            self.telemetry.stop()
            self.mav_connection.close()
            self.status_changed.emit("Desconectado")
            self.connection_state_changed.emit(False)
            return

        conn = self._active_connection
        rx_ip = conn["rx_ip"]
        rx_port = int(conn["rx_port"])
        tx_ip = conn["tx_ip"]
        tx_port = int(conn["tx_port"])
        if rx_ip != self._rx_bind_ip or rx_port != self._rx_port:
            self._rx_bind_ip = rx_ip
            self._rx_port = rx_port
            rx_endpoint = MavlinkEndpoint(
                connection_string=f"udpin:{self._rx_bind_ip}:{rx_port}"
            )
            self.mav_connection.set_endpoint(rx_endpoint)
        if tx_ip != self._tx_ip or tx_port != self._tx_port:
            self._tx_ip = tx_ip
            self._tx_port = tx_port
            self.telemetry.set_tx_target(self._tx_ip, self._tx_port)
            self.mav_connection.set_udp_target(self._tx_ip, self._tx_port)
        try:
            self.mav_connection.connect()
        except Exception as exc:
            self.status_changed.emit(f"Error RX: {exc!r}")
            return
        self.telemetry.start()
        self.status_changed.emit("Conectando...")
        self.connection_state_changed.emit(True)

    def apply_settings(self, settings: ConnectionSettings):
        self._conn_settings = settings
        save_connection_settings(self._conn_settings)
        self._active_connection = self._get_active_connection(self._conn_settings)
        self.connection_label_changed.emit(self._connection_label_text())
        if self.telemetry.is_running():
            self.telemetry.stop()
            self.mav_connection.close()
            self.status_changed.emit("Config actualizada, reconectar")
            self.connection_state_changed.emit(False)

    def connection_settings(self) -> ConnectionSettings:
        return self._conn_settings

    def connection_label(self) -> str:
        return self._connection_label_text()

    def is_connected(self) -> bool:
        return self.mav_connection.is_connected()

    def is_running(self) -> bool:
        return self.telemetry.is_running()

    def last_command_feedback(self) -> str:
        return self.telemetry.last_command_feedback()

    def send_arm_disarm(self) -> bool:
        if not self.telemetry.is_running() or not self.mav_connection.is_connected():
            self.status_changed.emit("No conectado")
            return False
        sample = self.telemetry.latest()
        if sample.armed:
            ok = self.telemetry.send_disarm()
            if not ok:
                self.status_changed.emit("Error enviando DISARM")
            return ok
        ok = self.telemetry.send_arm()
        if not ok:
            self.status_changed.emit("Error enviando ARM")
        return ok

    def send_goto(self, lat: float, lon: float) -> bool:
        if not self.telemetry.is_running() or not self.mav_connection.is_connected():
            self.status_changed.emit("No conectado")
            return False
        ok = self.telemetry.send_goto(lat, lon)
        feedback = self.telemetry.last_command_feedback()
        if not ok:
            self.status_changed.emit(feedback or "Error enviando GO TO")
            return False
        self.status_changed.emit(feedback or "GO TO enviado")
        return True

    def send_land(self) -> bool:
        if not self.mav_connection.is_connected():
            self.status_changed.emit("No conectado")
            return False
        ok = self.telemetry.send_land()
        if not ok:
            self.status_changed.emit("Error enviando LAND")
        return ok

    def send_takeoff(self) -> bool:
        if not self.telemetry.is_running() or not self.mav_connection.is_connected():
            self.status_changed.emit("No conectado")
            return False
        self.status_changed.emit("Enviando TAKEOFF...")
        ok = self.telemetry.send_takeoff()
        feedback = self.telemetry.last_command_feedback()
        if not ok:
            self.status_changed.emit(feedback or "Error enviando TAKEOFF")
            return False
        self.status_changed.emit(feedback or "TAKEOFF aceptado")
        return True

    def shutdown(self):
        if self.telemetry.is_running():
            self.telemetry.stop()
        if self.mav_connection.is_connected():
            self.mav_connection.close()

    def _connection_label_text(self) -> str:
        conn = self._active_connection
        return f"Conexión: {conn.get('name','-')}"

    @staticmethod
    def _get_active_connection(settings: ConnectionSettings) -> dict:
        index = min(max(settings.active_index, 0), len(settings.connections) - 1)
        return settings.connections[index]

    def _maybe_auto_connect(self):
        if self._active_connection.get("auto_connect"):
            self.toggle_connection()
