from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from artificial_horizon import ArtificialHorizon
from gcs.core.bridge import Bridge
from gcs.ui.dialogs.connection_settings_dialog import ConnectionSettingsDialog
from gcs.viewmodels.main_viewmodel import MainViewModel


class WebPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        level_name = {
            QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel: "INFO",
            QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel: "WARN",
            QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel: "ERROR",
        }.get(level, "LOG")
        print(f"[JS {level_name}] {source_id}:{line_number} {message}")


class MainWindow(QWidget):
    def __init__(self, viewmodel: MainViewModel):
        super().__init__()
        self.setWindowTitle("Qt GCS")
        self.resize(900, 600)
        self.vm = viewmodel

        layout = QGridLayout(self)

        self.connection_label = QLabel("Conexión: -")
        self.connect_button = QPushButton("Conectar")
        self.status_label = QLabel("Desconectado")
        self.mode_label = QLabel("Modo: UNKNOWN")

        self.arm_button = QPushButton("ARM")
        self.goto_button = QPushButton("GO TO")
        self.land_button = QPushButton("LAND")
        self.takeoff_button = QPushButton("TAKEOFF")
        self.arm_button.setEnabled(False)
        self.goto_button.setEnabled(False)
        self.land_button.setEnabled(False)
        self.takeoff_button.setEnabled(False)

        top_bar = QWidget(self)
        top_bar.setObjectName("top_bar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 6, 10, 6)
        top_layout.setSpacing(10)

        self.settings_menu = QMenu(self)
        self.action_connection = self.settings_menu.addAction("Connection...")
        self.action_connection.triggered.connect(self.open_connection_settings)

        self.settings_button = QToolButton(top_bar)
        self.settings_button.setMenu(self.settings_menu)
        self.settings_button.setPopupMode(QToolButton.InstantPopup)
        self.settings_button.setObjectName("settings_button")
        self.settings_button.setIcon(
            self.style().standardIcon(QStyle.SP_FileDialogDetailedView)
        )

        top_layout.addWidget(self.settings_button)
        top_layout.addWidget(self.connection_label)
        top_layout.addWidget(self.connect_button)
        top_layout.addWidget(self.status_label)
        top_layout.addStretch(1)
        layout.addWidget(top_bar, 0, 0, 1, 8)
        self.status_label.setObjectName("status_label")
        self.connection_label.setObjectName("connection_label")

        self.connect_button.setIcon(self.style().standardIcon(QStyle.SP_DialogYesButton))
        self.connect_button.setObjectName("connect_button")
        self.mode_label.setObjectName("mode_label")

        self.setStyleSheet(
            "#top_bar { background: #0b0f1a; border-bottom: 1px solid #1c2335; }"
            "#connection_label { color: #e9f2ff; font-weight: 600; letter-spacing: 0.5px; }"
            "#status_label { color: #9afcff; background: rgba(18, 31, 58, 220); "
            "border: 1px solid #1fd5ff; border-radius: 10px; padding: 2px 8px; }"
            "QPushButton { background: #161f35; color: #9afcff; border: 1px solid #1fd5ff; "
            "padding: 6px 12px; border-radius: 8px; }"
            "QPushButton:hover { background: #1b2947; }"
            "QPushButton:pressed { background: #111a2f; }"
            "#connect_button { border-color: #25f7a5; color: #c7ffea; }"
            "#connect_button:hover { background: #152b2a; }"
            "#settings_button { background: #161f35; border: 1px solid #ff4fd8; "
            "border-radius: 8px; padding: 4px; }"
            "#settings_button:hover { background: #2a1b3f; }"
            "#settings_button::menu-indicator { image: none; }"
            "QMenu { background: #0f1422; color: #ffd3f5; border: 1px solid #ff4fd8; }"
            "QMenu::item:selected { background: #2a1b3f; }"
            "#mode_label { color: #9afcff; font-size: 11px; }"
        )

        action_bar = QWidget(self)
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)
        action_layout.addWidget(self.arm_button)
        action_layout.addWidget(self.goto_button)
        action_layout.addWidget(self.land_button)
        action_layout.addWidget(self.takeoff_button)

        self.web_view = QWebEngineView()
        self.web_view.setPage(WebPage(self.web_view))
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)

        html_path = Path(__file__).parent / "web" / "map.html"
        html_content = html_path.read_text(encoding="utf-8")
        self.web_view.setHtml(html_content, QUrl("https://app.local/"))

        self.horizon_widget = ArtificialHorizon()
        self.horizon_widget.setFixedSize(120, 120)
        self.horizon_widget.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.altitude_label = QLabel("Alt: 0.00 m")
        self.altitude_label.setAlignment(Qt.AlignCenter)
        self.altitude_label.setStyleSheet(
            "color: #f0f0f0; font-weight: 600; font-size: 12px;"
        )

        map_container = QWidget(self)
        map_layout = QGridLayout(map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.addWidget(self.web_view, 0, 0)
        overlay_panel = QWidget(map_container)
        overlay_panel.setObjectName("overlay_panel")
        overlay_panel.setStyleSheet(
            "#overlay_panel { background: rgba(20, 20, 20, 180); "
            "border-radius: 10px; padding: 8px; }"
        )
        overlay_layout = QVBoxLayout(overlay_panel)
        overlay_layout.setContentsMargins(8, 8, 8, 8)
        overlay_layout.setSpacing(8)
        overlay_layout.addWidget(self.horizon_widget, alignment=Qt.AlignCenter)
        overlay_layout.addWidget(self.altitude_label, alignment=Qt.AlignCenter)
        overlay_layout.addWidget(self.mode_label, alignment=Qt.AlignCenter)
        overlay_layout.addWidget(action_bar)
        map_layout.addWidget(
            overlay_panel,
            0,
            0,
            Qt.AlignRight | Qt.AlignBottom,
        )
        layout.addWidget(map_container, 1, 0, 1, 8)

        self.bridge = Bridge()
        self.bridge.coordinatesChanged.connect(self.on_coordinates_changed)
        self._pending_goto: tuple[float, float] | None = None
        self._auto_zoomed = False

        channel = QWebChannel(self.web_view.page())
        channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(channel)

        self.connect_button.clicked.connect(self.vm.toggle_connection)
        self.arm_button.clicked.connect(self.vm.send_arm_disarm)
        self.goto_button.clicked.connect(self.send_goto_to_marker)
        self.land_button.clicked.connect(self.vm.send_land)
        self.takeoff_button.clicked.connect(self.vm.send_takeoff)

        self.vm.telemetry_updated.connect(self.on_telemetry_updated)
        self.vm.status_changed.connect(self.status_label.setText)
        self.vm.connection_label_changed.connect(self.connection_label.setText)
        self.vm.connection_state_changed.connect(self.on_connection_state_changed)
        self.connection_label.setText(self.vm.connection_label())

        layout.setRowStretch(1, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

    @Slot(float, float)
    def on_coordinates_changed(self, lat, lng):
        self._pending_goto = (lat, lng)
        if not self.vm.is_running() or not self.vm.is_connected():
            self.status_label.setText("Marcador listo (sin conexión)")
            return
        self.status_label.setText("Marcador listo")

    def set_drone_position(self, lat, lng, heading_deg=0.0):
        self.web_view.page().runJavaScript(
            f"window.setDronePosition({lat:.6f}, {lng:.6f}, {heading_deg:.2f});"
        )

    def on_telemetry_updated(self, sample):
        self.mode_label.setText(f"Modo: {sample.mode}")
        self.arm_button.setText("DISARM" if sample.armed else "ARM")
        self.altitude_label.setText(f"Alt: {sample.alt_m:.2f} m")
        self.horizon_widget.setTargetPitchRoll(sample.pitch_deg, sample.roll_deg)
        if not sample.has_fix:
            return
        if not self._auto_zoomed:
            self.web_view.page().runJavaScript(
                f"window.setMapView({sample.lat:.6f}, {sample.lon:.6f}, 17);"
            )
            self._auto_zoomed = True
        self.set_drone_position(sample.lat, sample.lon, sample.heading_deg)

    def on_connection_state_changed(self, connected: bool):
        if connected:
            self.connect_button.setText("Desconectar")
            self.arm_button.setEnabled(True)
            self.goto_button.setEnabled(True)
            self.land_button.setEnabled(True)
            self.takeoff_button.setEnabled(True)
        else:
            self.connect_button.setText("Conectar")
            self.arm_button.setEnabled(False)
            self.goto_button.setEnabled(False)
            self.land_button.setEnabled(False)
            self.takeoff_button.setEnabled(False)

    def send_goto_to_marker(self):
        if self._pending_goto is None:
            self.status_label.setText("Selecciona un marcador")
            return
        lat, lon = self._pending_goto
        ok = self.vm.send_goto(lat, lon)
        feedback = self.vm.last_command_feedback()
        if not ok:
            print(f"[CMD] {feedback or 'GO TO rechazado'}")
            return
        print(f"[CMD] {feedback or 'GO TO enviado'}")

    def open_connection_settings(self):
        dialog = ConnectionSettingsDialog(self.vm.connection_settings(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.vm.apply_settings(dialog.settings())

    def closeEvent(self, event):
        self.vm.shutdown()
        super().closeEvent(event)
