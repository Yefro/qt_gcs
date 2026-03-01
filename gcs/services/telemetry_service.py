import math
import threading
import time
from collections import deque

from pymavlink import mavutil

from gcs.mavlink.connection import MavlinkConnection
from gcs.mavlink.telemetry import TelemetrySample


class TelemetryService:
    def __init__(
        self,
        connection: MavlinkConnection,
        tx_target: tuple[str, int] | None = None,
        verbose: bool = False,
    ):
        self._connection = connection
        self._tx_target = tx_target
        self._verbose = verbose
        self._latest = TelemetrySample()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._last_heartbeat_ts = 0.0
        self._last_autopilot_heartbeat_ts = 0.0
        self._last_command_feedback = ""
        self._ack_queue = deque(maxlen=64)

    def latest(self) -> TelemetrySample:
        with self._lock:
            return TelemetrySample(**self._latest.__dict__)

    def update_from_mavlink(self, msg):
        if msg is None:
            return
        msg_type = msg.get_type()
        if msg_type == "COMMAND_ACK":
            ack_ts = time.monotonic()
            ack_command = int(getattr(msg, "command", -1))
            ack_result = int(getattr(msg, "result", -1))
            with self._lock:
                self._latest.last_ack_command = ack_command
                self._latest.last_ack_result = ack_result
                self._latest.last_ack_ts = ack_ts
                self._ack_queue.append((ack_ts, ack_command, ack_result))
            return
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
            is_autopilot_hb = src_comp == mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1
            with self._lock:
                if is_autopilot_hb:
                    self._last_autopilot_heartbeat_ts = time.monotonic()
                    self._latest.mode = mode
                    self._latest.base_mode = int(getattr(msg, "base_mode", 0))
                    self._latest.custom_mode = int(getattr(msg, "custom_mode", 0))
                    self._latest.armed = bool(
                        msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
                    )
                    self._latest.target_system = src_sys
                    self._latest.target_component = src_comp
            return
        if msg_type == "ATTITUDE_QUATERNION":
            try:
                q1 = float(getattr(msg, "q1", 1.0))
                q2 = float(getattr(msg, "q2", 0.0))
                q3 = float(getattr(msg, "q3", 0.0))
                q4 = float(getattr(msg, "q4", 0.0))
            except Exception:
                return
            roll_rad, pitch_rad, yaw_rad = self._quat_to_euler(q1, q2, q3, q4)
            with self._lock:
                self._latest.roll_deg = math.degrees(roll_rad)
                self._latest.pitch_deg = math.degrees(pitch_rad)
                self._latest.yaw_deg = math.degrees(yaw_rad)
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
        self._log("[TELEMETRY] Starting telemetry thread.")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        self._log("[TELEMETRY] Telemetry thread stopped.")
        self.reset()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def reset(self):
        with self._lock:
            self._latest = TelemetrySample()

    def set_tx_target(self, ip: str, port: int):
        self._tx_target = (ip, int(port))

    def last_command_feedback(self) -> str:
        with self._lock:
            return self._last_command_feedback

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
            self._log(f"[TELEMETRY] Failed to send LAND: {exc!r}")
            return False
        self._log("[TELEMETRY] LAND command sent.")
        return True

    def send_takeoff(self, altitude_m: float = 10.0) -> bool:
        conn = self._connection.connection()
        if conn is None:
            with self._lock:
                self._last_command_feedback = "TAKEOFF sin conexion MAVLink"
            return False
        with self._lock:
            target_system = self._latest.target_system
            target_component = self._latest.target_component
            has_fix = self._latest.has_fix
            current_lat = self._latest.lat
            current_lon = self._latest.lon
            mode = self._latest.mode
            armed = self._latest.armed
            last_ap_hb_age_s = time.monotonic() - self._last_autopilot_heartbeat_ts
        if altitude_m <= 0:
            with self._lock:
                self._last_command_feedback = "TAKEOFF invalido: altura debe ser > 0"
            return False
        if self._last_autopilot_heartbeat_ts <= 0.0 or last_ap_hb_age_s > 2.0:
            with self._lock:
                self._last_command_feedback = (
                    "TAKEOFF bloqueado: sin HEARTBEAT reciente del autopiloto"
                )
            return False
        if mode == "UNKNOWN":
            with self._lock:
                self._last_command_feedback = "TAKEOFF bloqueado: modo UNKNOWN"
            return False
        if not armed:
            with self._lock:
                self._last_command_feedback = "TAKEOFF bloqueado: vehiculo no armado"
            return False
        target_lat = 0.0
        target_lon = 0.0
        # PX4 expects NAV_TAKEOFF altitude as target altitude for takeoff profile.
        # Use a direct relative target instead of current_alt + altitude_m.
        target_alt = float(altitude_m)
        if has_fix:
            target_lat = float(current_lat)
            target_lon = float(current_lon)
        sent_ts = time.monotonic()
        try:
            # For PX4, send TAKEOFF with explicit RELATIVE_ALT frame.
            # command_long has no frame field and can be interpreted as AMSL.
            conn.mav.command_int_send(
                target_system,
                target_component,
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0,
                1,
                0,
                0,
                0,
                0,
                int(target_lat * 1e7),
                int(target_lon * 1e7),
                target_alt,
            )
        except Exception as exc:
            with self._lock:
                self._last_command_feedback = f"TAKEOFF error de envio: {exc!r}"
            self._log(f"[TELEMETRY] Failed to send TAKEOFF: {exc!r}")
            return False
        ack_command, ack_result = self._wait_command_ack(
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, sent_ts
        )
        if ack_result is None:
            with self._lock:
                self._last_command_feedback = "TAKEOFF sin COMMAND_ACK"
            self._log("[TELEMETRY] TAKEOFF sent but no COMMAND_ACK received.")
            return False
        if ack_command != mavutil.mavlink.MAV_CMD_NAV_TAKEOFF:
            with self._lock:
                self._last_command_feedback = (
                    "TAKEOFF ACK de otro comando: "
                    f"{self._mav_cmd_name(ack_command)} "
                    f"result={self._mav_result_name(ack_result)}"
                )
            self._log(
                "[TELEMETRY] TAKEOFF got ACK for different command: "
                f"{self._mav_cmd_name(ack_command)} "
                f"result={self._mav_result_name(ack_result)}."
            )
            return False
        if ack_result in (
            mavutil.mavlink.MAV_RESULT_ACCEPTED,
            mavutil.mavlink.MAV_RESULT_IN_PROGRESS,
        ):
            with self._lock:
                self._last_command_feedback = (
                    "TAKEOFF ACK "
                    f"{self._mav_cmd_name(ack_command)} "
                    f"result={self._mav_result_name(ack_result)}"
                )
            self._log(f"[TELEMETRY] TAKEOFF ACK={self._mav_result_name(ack_result)}.")
            return True
        with self._lock:
            self._last_command_feedback = (
                "TAKEOFF rechazado "
                f"{self._mav_cmd_name(ack_command)} "
                f"result={self._mav_result_name(ack_result)}"
            )
        self._log(
            f"[TELEMETRY] TAKEOFF rejected ACK={self._mav_result_name(ack_result)}."
        )
        return False

    def send_arm(self) -> bool:
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
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                1,
                0,
                0,
                0,
                0,
                0,
                0,
            )
        except Exception as exc:
            self._log(f"[TELEMETRY] Failed to send ARM: {exc!r}")
            return False
        self._log("[TELEMETRY] ARM command sent.")
        return True

    def send_disarm(self) -> bool:
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
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
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
            self._log(f"[TELEMETRY] Failed to send DISARM: {exc!r}")
            return False
        self._log("[TELEMETRY] DISARM command sent.")
        return True

    def send_goto(
        self,
        lat: float,
        lon: float,
        alt_m: float | None = None,
        ground_speed: float = -1.0,
        flags: float = 1.0,
        confirmation: int = 0,
    ) -> bool:
        conn = self._connection.connection()
        if conn is None:
            with self._lock:
                self._last_command_feedback = "GO TO sin conexion MAVLink"
            return False
        with self._lock:
            target_system = self._latest.target_system
            target_component = self._latest.target_component
            current_alt = self._latest.alt_m
            has_fix = self._latest.has_fix
        if alt_m is None:
            if not has_fix:
                with self._lock:
                    self._last_command_feedback = "GO TO requiere fix o altitud explicita"
                return False
            alt_m = current_alt
        if self._tx_target is not None:
            self._connection.set_udp_target(*self._tx_target)
        sent_ts = time.monotonic()
        try:
            conn.mav.command_long_send(
                target_system,
                target_component,
                mavutil.mavlink.MAV_CMD_DO_REPOSITION,
                int(confirmation),
                float(ground_speed),
                float(flags),
                0.0,
                math.nan,
                float(lat),
                float(lon),
                float(alt_m),
            )
        except Exception as exc:
            with self._lock:
                self._last_command_feedback = f"GO TO error COMMAND_LONG: {exc!r}"
            self._log(f"[TELEMETRY] Failed to send GO TO COMMAND_LONG: {exc!r}")
            return False

        ack_command, ack_result = self._wait_command_ack(
            mavutil.mavlink.MAV_CMD_DO_REPOSITION, sent_ts
        )
        if (
            ack_command == mavutil.mavlink.MAV_CMD_DO_REPOSITION
            and ack_result
            in (
                mavutil.mavlink.MAV_RESULT_ACCEPTED,
                mavutil.mavlink.MAV_RESULT_IN_PROGRESS,
            )
        ):
            with self._lock:
                self._last_command_feedback = (
                    "GO TO ACK "
                    f"{self._mav_cmd_name(ack_command)} "
                    f"result={self._mav_result_name(ack_result)}"
                )
            self._log(
                "[TELEMETRY] GO TO ACK "
                f"{self._mav_cmd_name(ack_command)} "
                f"result={self._mav_result_name(ack_result)}."
            )
            return True

        if ack_result is None:
            with self._lock:
                self._last_command_feedback = "GO TO sin COMMAND_ACK"
            self._log("[TELEMETRY] GO TO sent but no COMMAND_ACK received.")
            return False
        elif ack_command != mavutil.mavlink.MAV_CMD_DO_REPOSITION:
            with self._lock:
                self._last_command_feedback = (
                    "GO TO ACK de otro comando: "
                    f"{self._mav_cmd_name(ack_command)} "
                    f"result={self._mav_result_name(ack_result)}"
                )
            self._log(
                "[TELEMETRY] GO TO got ACK for different command: "
                f"{self._mav_cmd_name(ack_command)} "
                f"result={self._mav_result_name(ack_result)}."
            )
            return False
        with self._lock:
            self._last_command_feedback = (
                "GO TO rechazado "
                f"{self._mav_cmd_name(ack_command)} "
                f"result={self._mav_result_name(ack_result)}"
            )
        self._log(
            "[TELEMETRY] GO TO rejected "
            f"{self._mav_cmd_name(ack_command)} "
            f"result={self._mav_result_name(ack_result)}."
        )
        return False

    def _run(self):
        self._log("[TELEMETRY] Run loop started.")
        while not self._stop_event.is_set():
            if not self._connection.is_connected():
                try:
                    self._connection.connect()
                except Exception as exc:
                    self._log(f"[TELEMETRY] Connection attempt failed: {exc!r}")
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
                    self._log(f"[TELEMETRY] Error receiving MAVLink message: {exc!r}")
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
                self._log(
                    f"[TELEMETRY] RX {msg_type} sys={src_sys} comp={src_comp} (drain={drained})."
                )
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
            self._log("[TELEMETRY] Heartbeat sent.")
        except Exception as exc:
            self._log(f"[TELEMETRY] Failed to send heartbeat: {exc!r}")

    def _wait_command_ack(
        self, command: int, sent_ts: float, timeout_s: float = 1.5
    ) -> tuple[int | None, int | None]:
        deadline = time.monotonic() + timeout_s
        last_other_command = None
        last_other_result = None
        while time.monotonic() < deadline:
            with self._lock:
                for ack_ts, ack_command, ack_result in self._ack_queue:
                    if ack_ts < sent_ts:
                        continue
                    if ack_command == command:
                        return ack_command, ack_result
                    last_other_command = ack_command
                    last_other_result = ack_result
            time.sleep(0.02)
        if last_other_result is not None:
            return last_other_command, last_other_result
        return None, None

    def _mav_cmd_name(self, command: int | None) -> str:
        if command is None:
            return "UNKNOWN_CMD"
        try:
            return mavutil.mavlink.enums["MAV_CMD"][int(command)].name
        except Exception:
            return f"MAV_CMD_{command}"

    def _mav_result_name(self, result: int) -> str:
        try:
            return mavutil.mavlink.enums["MAV_RESULT"][int(result)].name
        except Exception:
            return str(result)

    @staticmethod
    def _quat_to_euler(q1: float, q2: float, q3: float, q4: float) -> tuple[float, float, float]:
        # MAVLink ATTITUDE_QUATERNION uses (w, x, y, z) = (q1, q2, q3, q4)
        w, x, y, z = q1, q2, q3, q4
        sinr_cosp = 2.0 * (w * x + y * z)
        cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        sinp = 2.0 * (w * y - z * x)
        if abs(sinp) >= 1.0:
            pitch = math.copysign(math.pi / 2.0, sinp)
        else:
            pitch = math.asin(sinp)

        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        return roll, pitch, yaw

    def _log(self, message: str):
        if self._verbose:
            print(message)
