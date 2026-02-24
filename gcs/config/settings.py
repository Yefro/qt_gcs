from dataclasses import dataclass


@dataclass
class AppSettings:
    mavlink_connection: str = "udpout:172.31.30.232:18570"
    system_id: int = 255
    component_id: int = 190
