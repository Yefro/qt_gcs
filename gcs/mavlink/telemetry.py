from dataclasses import dataclass


@dataclass
class TelemetrySample:
    lat: float = 0.0
    lon: float = 0.0
    alt_m: float = 0.0
    vx_m_s: float = 0.0
    vy_m_s: float = 0.0
    vz_m_s: float = 0.0
    heading_deg: float = 0.0
    has_fix: bool = False
    mode: str = "UNKNOWN"
    armed: bool = False
    last_ack_command: int | None = None
    last_ack_result: int | None = None
    last_ack_ts: float = 0.0
    target_system: int = 1
    target_component: int = 1
    base_mode: int = 0
    custom_mode: int = 0
