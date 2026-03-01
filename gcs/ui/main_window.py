from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from gcs.core.bridge import Bridge
from gcs.mavlink.connection import MavlinkConnection
from gcs.mavlink.types import MavlinkEndpoint
from gcs.services.telemetry_service import TelemetryService


class WebPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        level_name = {
            QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel: "INFO",
            QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel: "WARN",
            QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel: "ERROR",
        }.get(level, "LOG")
        print(f"[JS {level_name}] {source_id}:{line_number} {message}")


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qt Map Click")
        self.resize(900, 600)

        layout = QGridLayout(self)

        self.rx_ip_input = QLineEdit("0.0.0.0")
        self.rx_port_input = QLineEdit("14550")
        self.tx_ip_input = QLineEdit("172.31.30.232")
        self.tx_port_input = QLineEdit("18570")
        self.connect_button = QPushButton("Conectar")
        self.arm_button = QPushButton("ARM")
        self.goto_button = QPushButton("GO TO")
        self.land_button = QPushButton("LAND")
        self.takeoff_button = QPushButton("TAKEOFF")
        self.status_label = QLabel("Desconectado")
        self.mode_label = QLabel("Modo: UNKNOWN")
        self.arm_button.setEnabled(False)
        self.goto_button.setEnabled(False)
        self.land_button.setEnabled(False)
        self.takeoff_button.setEnabled(False)

        layout.addWidget(QLabel("UDP RX IP:"), 0, 0)
        layout.addWidget(self.rx_ip_input, 0, 1)
        layout.addWidget(QLabel("RX Puerto:"), 0, 2)
        layout.addWidget(self.rx_port_input, 0, 3)
        layout.addWidget(self.connect_button, 0, 4)
        layout.addWidget(self.status_label, 0, 5)
        action_bar = QWidget(self)
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)
        action_layout.addWidget(self.arm_button)
        action_layout.addWidget(self.goto_button)
        action_layout.addWidget(self.land_button)
        action_layout.addWidget(self.takeoff_button)
        layout.addWidget(action_bar, 0, 6, 1, 3)

        layout.addWidget(QLabel("UDP TX IP:"), 1, 0)
        layout.addWidget(self.tx_ip_input, 1, 1)
        layout.addWidget(QLabel("TX Puerto:"), 1, 2)
        layout.addWidget(self.tx_port_input, 1, 3)
        layout.addWidget(self.mode_label, 1, 4, 1, 3)

        self.lat_input = QLineEdit()
        self.lng_input = QLineEdit()
        self.height_input = QLineEdit()
        self.lat_input.setReadOnly(True)
        self.lng_input.setReadOnly(True)
        self.height_input.setReadOnly(True)
        self.lat_input.setPlaceholderText("Latitud")
        self.lng_input.setPlaceholderText("Longitud")
        self.height_input.setPlaceholderText("Height (m)")

        layout.addWidget(QLabel("Latitud:"), 2, 0)
        layout.addWidget(self.lat_input, 2, 1)
        layout.addWidget(QLabel("Longitud:"), 2, 2)
        layout.addWidget(self.lng_input, 2, 3)
        layout.addWidget(QLabel("Height (m):"), 2, 4)
        layout.addWidget(self.height_input, 2, 5)

        self.web_view = QWebEngineView()
        self.web_view.setPage(WebPage(self.web_view))
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)

        html_path = Path(__file__).parent / "web" / "map.html"
        html_content = html_path.read_text(encoding="utf-8")
        self.web_view.setHtml(html_content, QUrl("https://app.local/"))
        layout.addWidget(self.web_view, 3, 0, 1, 8)

        self.bridge = Bridge()
        self.bridge.coordinatesChanged.connect(self.on_coordinates_changed)
        self._pending_goto: tuple[float, float] | None = None
        self._auto_zoomed = False

        channel = QWebChannel(self.web_view.page())
        channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(channel)

        self._rx_bind_ip = self.rx_ip_input.text().strip() or "0.0.0.0"
        self._rx_port = int(self.rx_port_input.text())
        rx_endpoint = MavlinkEndpoint(
            connection_string=f"udpin:{self._rx_bind_ip}:{self._rx_port}"
        )
        self.mav_connection = MavlinkConnection(rx_endpoint)
        self._tx_ip = self.tx_ip_input.text().strip()
        self._tx_port = int(self.tx_port_input.text())
        self.telemetry = TelemetryService(
            self.mav_connection, tx_target=(self._tx_ip, self._tx_port)
        )
        try:
            self.mav_connection.connect()
            self.mav_connection.set_udp_target(self._tx_ip, self._tx_port)
        except Exception as exc:
            self.status_label.setText(f"Error RX inicio: {exc!r}")

        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.setInterval(200)
        self.telemetry_timer.timeout.connect(self.refresh_telemetry)
        self.telemetry_timer.start()

        self.connect_button.clicked.connect(self.toggle_connection)
        self.arm_button.clicked.connect(self.send_arm_disarm)
        self.goto_button.clicked.connect(self.send_goto_to_marker)
        self.land_button.clicked.connect(self.send_land)
        self.takeoff_button.clicked.connect(self.send_takeoff)

        layout.setRowStretch(3, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

    @Slot(float, float)
    def on_coordinates_changed(self, lat, lng):
        self.lat_input.setText(f"{lat:.6f}")
        self.lng_input.setText(f"{lng:.6f}")
        self._pending_goto = (lat, lng)
        if not self.telemetry.is_running() or not self.mav_connection.is_connected():
            self.status_label.setText("Marcador listo (sin conexión)")
            return
        self.status_label.setText("Marcador listo")

    def set_drone_position(self, lat, lng, heading_deg=0.0):
        # Exposes Python -> JS updates for drone position.
        self.web_view.page().runJavaScript(
            f"window.setDronePosition({lat:.6f}, {lng:.6f}, {heading_deg:.2f});"
        )

    def refresh_telemetry(self):
        sample = self.telemetry.latest()
        if self.mav_connection.is_connected():
            if sample.has_fix:
                self.status_label.setText("Conectado")
            else:
                self.status_label.setText("Conectado (sin fix)")
        self.mode_label.setText(f"Modo: {sample.mode}")
        self.arm_button.setText("DISARM" if sample.armed else "ARM")
        self.height_input.setText(f"{sample.alt_m:.2f}")
        if not sample.has_fix:
            return
        if not self._auto_zoomed:
            self.web_view.page().runJavaScript(
                f"window.setMapView({sample.lat:.6f}, {sample.lon:.6f}, 17);"
            )
            self._auto_zoomed = True
        self.lat_input.setText(f"{sample.lat:.6f}")
        self.lng_input.setText(f"{sample.lon:.6f}")
        self.set_drone_position(sample.lat, sample.lon, sample.heading_deg)

    def toggle_connection(self):
        if self.telemetry.is_running():
            self.telemetry.stop()
            self.mav_connection.close()
            self.status_label.setText("Desconectado")
            self.connect_button.setText("Conectar")
            self.rx_ip_input.setEnabled(True)
            self.rx_port_input.setEnabled(True)
            self.tx_ip_input.setEnabled(True)
            self.tx_port_input.setEnabled(True)
            self.arm_button.setEnabled(False)
            self.goto_button.setEnabled(False)
            self.land_button.setEnabled(False)
            self.takeoff_button.setEnabled(False)
            return

        rx_ip = self.rx_ip_input.text().strip()
        rx_port_text = self.rx_port_input.text().strip()
        tx_ip = self.tx_ip_input.text().strip()
        tx_port_text = self.tx_port_input.text().strip()
        if (
            not rx_ip
            or not rx_port_text.isdigit()
            or not tx_ip
            or not tx_port_text.isdigit()
        ):
            self.status_label.setText("IP o puerto inválido")
            return
        rx_port = int(rx_port_text)
        tx_port = int(tx_port_text)
        if rx_ip != self._rx_bind_ip or rx_port != self._rx_port:
            self._rx_bind_ip = rx_ip
            self._rx_port = rx_port
            rx_endpoint = MavlinkEndpoint(
                connection_string=f"udpin:{self._rx_bind_ip}:{rx_port}"
            )
            self.mav_connection.set_endpoint(rx_endpoint)
            try:
                self.mav_connection.connect()
            except Exception as exc:
                self.status_label.setText(f"Error RX: {exc!r}")
                return
        if tx_ip != self._tx_ip or tx_port != self._tx_port:
            self._tx_ip = tx_ip
            self._tx_port = tx_port
            self.telemetry.set_tx_target(self._tx_ip, self._tx_port)
            self.mav_connection.set_udp_target(self._tx_ip, self._tx_port)
        elif not self.mav_connection.is_connected():
            try:
                self.mav_connection.connect()
            except Exception as exc:
                self.status_label.setText(f"Error RX: {exc!r}")
                return
        self.telemetry.start()
        self.status_label.setText("Conectando...")
        self.connect_button.setText("Desconectar")
        self.rx_ip_input.setEnabled(False)
        self.rx_port_input.setEnabled(False)
        self.tx_ip_input.setEnabled(False)
        self.tx_port_input.setEnabled(False)
        self.arm_button.setEnabled(True)
        self.goto_button.setEnabled(True)
        self.land_button.setEnabled(True)
        self.takeoff_button.setEnabled(True)

    def send_arm_disarm(self):
        if not self.telemetry.is_running() or not self.mav_connection.is_connected():
            self.status_label.setText("No conectado")
            return
        sample = self.telemetry.latest()
        if sample.armed:
            ok = self.telemetry.send_disarm()
            if not ok:
                self.status_label.setText("Error enviando DISARM")
        else:
            ok = self.telemetry.send_arm()
            if not ok:
                self.status_label.setText("Error enviando ARM")

    def send_goto_to_marker(self):
        if self._pending_goto is None:
            self.status_label.setText("Selecciona un marcador")
            return
        if not self.telemetry.is_running() or not self.mav_connection.is_connected():
            self.status_label.setText("No conectado")
            return
        lat, lon = self._pending_goto
        ok = self.telemetry.send_goto(lat, lon)
        feedback = self.telemetry.last_command_feedback()
        if not ok:
            self.status_label.setText(feedback or "Error enviando GO TO")
            print(f"[CMD] {feedback or 'GO TO rechazado'}")
            return
        self.status_label.setText(feedback or "GO TO enviado")
        print(f"[CMD] {feedback or 'GO TO enviado'}")

    def send_land(self):
        if not self.mav_connection.is_connected():
            self.status_label.setText("No conectado")
            return
        ok = self.telemetry.send_land()
        if not ok:
            self.status_label.setText("Error enviando LAND")

    def send_takeoff(self):
        if not self.telemetry.is_running() or not self.mav_connection.is_connected():
            self.status_label.setText("No conectado")
            return
        self.status_label.setText("Enviando TAKEOFF...")
        ok = self.telemetry.send_takeoff()
        feedback = self.telemetry.last_command_feedback()
        if not ok:
            self.status_label.setText(feedback or "Error enviando TAKEOFF")
            print(f"[CMD] {feedback or 'TAKEOFF rechazado'}")
            return
        self.status_label.setText(feedback or "TAKEOFF aceptado")
        print(f"[CMD] {feedback or 'TAKEOFF aceptado'}")
    def closeEvent(self, event):
        self.telemetry.stop()
        self.mav_connection.close()
        super().closeEvent(event)

