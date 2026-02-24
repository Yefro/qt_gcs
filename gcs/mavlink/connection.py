import time
from typing import Optional

from pymavlink import mavutil

from gcs.mavlink.types import MavlinkEndpoint


class MavlinkConnection:
    def __init__(self, endpoint: MavlinkEndpoint):
        self.endpoint = endpoint
        self._connection = None

    def connect(self):
        """Connect to a MAVLink endpoint.

        Integrate pymavlink here to open the connection and start receiving.
        """
        if self._connection is not None:
            return
        print(f"[MAVLINK] Connecting to {self.endpoint.connection_string}...")
        try:
            if self.endpoint.baudrate is None:
                self._connection = mavutil.mavlink_connection(
                    self.endpoint.connection_string
                )
            else:
                self._connection = mavutil.mavlink_connection(
                    self.endpoint.connection_string, baud=self.endpoint.baudrate
                )
            print("[MAVLINK] Connection object created.")
        except Exception as exc:
            print(f"[MAVLINK] Connection failed: {exc!r}")
            raise

    def close(self):
        if self._connection is None:
            return
        try:
            print("[MAVLINK] Closing connection.")
            self._connection.close()
        except Exception:
            print("[MAVLINK] Error while closing connection.")
            pass
        self._connection = None

    def is_connected(self) -> bool:
        return self._connection is not None

    def connection(self):
        return self._connection

    def set_endpoint(self, endpoint: MavlinkEndpoint):
        if self._connection is not None:
            self.close()
        self.endpoint = endpoint

    def set_udp_target(self, ip: str, port: int) -> bool:
        """Prime a UDP server connection to send to a specific target.

        This ensures outbound MAVLink uses the desired remote address when
        the local socket is bound (udpin).
        """
        if self._connection is None:
            return False
        conn = self._connection
        if not getattr(conn, "udp_server", False):
            return False
        try:
            addr = (ip, int(port))
            conn.clients.add(addr)
            conn.clients_last_alive[addr] = time.time()
        except Exception:
            return False
        return True


class MavlinkHeartbeat:
    def __init__(self):
        self.last_timestamp = None
        self.system_status = None
        self.flight_mode = None

    def update_from_message(self, msg):
        self.last_timestamp = getattr(msg, "_timestamp", None)
        self.system_status = getattr(msg, "system_status", None)
        self.flight_mode = getattr(msg, "custom_mode", None)
