import threading
import time

from pymavlink import mavutil

from gcs.mavlink.connection import MavlinkConnection
from gcs.mavlink.telemetry import TelemetrySample


class TelemetryService:
    def __init__(
        self, connection: MavlinkConnection, tx_target: tuple[str, int] | None = None
    ):
        self._connection = connection
        self._tx_target = tx_target
        self._latest = TelemetrySample()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._last_heartbeat_ts = 0.0

    def latest(self) -> TelemetrySample:
        with self._lock:
            return TelemetrySample(**self._latest.__dict__)

    def update_from_mavlink(self, msg):
        if msg is None:
            return
        msg_type = msg.get_type()
        if msg_type == "HEARTBEAT":
            try:
                mode = mavutil.mode_string_v10(msg)
            except Exception:
                mode = "UNKNOWN"
            try:
                src_sys = msg.get_srcSystem()
                src_comp = msg.get_srcComponent()
            except Exception:
                src_sys = 1
                src_comp = 1
            with self._lock:
                self._latest.mode = mode
                self._latest.target_system = src_sys
                self._latest.target_component = src_comp
            return
        if msg_type != "GLOBAL_POSITION_INT":
            return
        lat = msg.lat / 1e7
        lon = msg.lon / 1e7
        alt_m = msg.alt / 1000.0
        vx = msg.vx / 100.0
        vy = msg.vy / 100.0
        vz = msg.vz / 100.0
        heading = 0.0
        if getattr(msg, "hdg", 65535) != 65535:
            heading = msg.hdg / 100.0
        with self._lock:
            self._latest.lat = lat
            self._latest.lon = lon
            self._latest.alt_m = alt_m
            self._latest.vx_m_s = vx
            self._latest.vy_m_s = vy
            self._latest.vz_m_s = vz
            self._latest.heading_deg = heading
            self._latest.has_fix = True

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        print("[TELEMETRY] Starting telemetry thread.")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        print("[TELEMETRY] Telemetry thread stopped.")
        self.reset()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def reset(self):
        with self._lock:
            self._latest = TelemetrySample()

    def set_tx_target(self, ip: str, port: int):
        self._tx_target = (ip, int(port))

    def send_land(self) -> bool:
        conn = self._connection.connection()
        if conn is None:
            return False
        with self._lock:
            target_system = self._latest.target_system
            target_component = self._latest.target_component
        try:
            conn.mav.command_long_send(
                target_system,
                target_component,
                mavutil.mavlink.MAV_CMD_NAV_LAND,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            )
        except Exception as exc:
            print(f"[TELEMETRY] Failed to send LAND: {exc!r}")
            return False
        print("[TELEMETRY] LAND command sent.")
        return True

    def send_takeoff(self, altitude_m: float = 10.0) -> bool:
        conn = self._connection.connection()
        if conn is None:
            return False
        with self._lock:
            target_system = self._latest.target_system
            target_component = self._latest.target_component
        try:
            conn.mav.command_long_send(
                target_system,
                target_component,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                float(altitude_m),
            )
        except Exception as exc:
            print(f"[TELEMETRY] Failed to send TAKEOFF: {exc!r}")
            return False
        print("[TELEMETRY] TAKEOFF command sent.")
        return True

    def send_goto(self, lat: float, lon: float, alt_m: float | None = None) -> bool:
        conn = self._connection.connection()
        if conn is None:
            return False
        with self._lock:
            target_system = self._latest.target_system
            target_component = self._latest.target_component
            current_alt = self._latest.alt_m
            has_fix = self._latest.has_fix
        if alt_m is None:
            if not has_fix:
                return False
            alt_m = current_alt
        if self._tx_target is not None:
            self._connection.set_udp_target(*self._tx_target)
        type_mask = (
            (1 << 3)
            | (1 << 4)
            | (1 << 5)
            | (1 << 6)
            | (1 << 7)
            | (1 << 8)
            | (1 << 10)
            | (1 << 11)
        )
        try:
            conn.mav.set_position_target_global_int_send(
                int(time.time() * 1000) & 0xFFFFFFFF,
                target_system,
                target_component,
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                type_mask,
                int(lat * 1e7),
                int(lon * 1e7),
                float(alt_m),
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            )
        except Exception as exc:
            print(f"[TELEMETRY] Failed to send GO TO: {exc!r}")
            return False
        print(
            f"[TELEMETRY] GO TO sent lat={lat:.6f} lon={lon:.6f} alt={alt_m:.1f}m."
        )
        return True

    def _run(self):
        print("[TELEMETRY] Run loop started.")
        while not self._stop_event.is_set():
            if not self._connection.is_connected():
                try:
                    self._connection.connect()
                except Exception as exc:
                    print(f"[TELEMETRY] Connection attempt failed: {exc!r}")
                    time.sleep(1.0)
                    continue
            self._send_heartbeat_if_due()
            drained = 0
            while True:
                try:
                    msg = self._connection.connection().recv_match(
                        blocking=False
                    )
                except Exception as exc:
                    print(f"[TELEMETRY] Error receiving MAVLink message: {exc!r}")
                    msg = None
                if msg is None:
                    break
                drained += 1
                self.update_from_mavlink(msg)
                msg_type = msg.get_type()
                try:
                    src_sys = msg.get_srcSystem()
                    src_comp = msg.get_srcComponent()
                except Exception:
                    src_sys = "?"
                    src_comp = "?"
                print(f"[TELEMETRY] RX {msg_type} sys={src_sys} comp={src_comp} (drain={drained}).")
            if drained == 0:
                time.sleep(0.02)

    def _send_heartbeat_if_due(self):
        now = time.monotonic()
        if now - self._last_heartbeat_ts < 1.0:
            return
        self._last_heartbeat_ts = now
        if self._tx_target is not None:
            self._connection.set_udp_target(*self._tx_target)
        conn = self._connection.connection()
        if conn is None:
            return
        try:
            conn.mav.heartbeat_send(
                6,  # MAV_TYPE_GCS
                8,  # MAV_AUTOPILOT_INVALID
                0,  # base_mode
                0,  # custom_mode
                0,  # system_status
            )
            print("[TELEMETRY] Heartbeat sent.")
        except Exception as exc:
            print(f"[TELEMETRY] Failed to send heartbeat: {exc!r}")
