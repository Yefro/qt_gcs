from dataclasses import dataclass
from typing import Optional


@dataclass
class MavlinkEndpoint:
    system_id: int = 255
    component_id: int = 190
    connection_string: str = "udpin:0.0.0.0:14550"
    baudrate: Optional[int] = None
    local_port: Optional[int] = None
