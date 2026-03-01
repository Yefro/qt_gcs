from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONNECTIONS = [
    {
        "name": "Default",
        "rx_ip": "0.0.0.0",
        "rx_port": 14550,
        "tx_ip": "172.31.30.232",
        "tx_port": 18570,
        "auto_connect": False,
    }
]


@dataclass
class ConnectionSettings:
    connections: list[dict]
    active_index: int


def _settings_path() -> Path:
    return Path(__file__).parent / "connection_settings.json"


def load_connection_settings() -> ConnectionSettings:
    path = _settings_path()
    if not path.exists():
        return ConnectionSettings(connections=list(DEFAULT_CONNECTIONS), active_index=0)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ConnectionSettings(connections=list(DEFAULT_CONNECTIONS), active_index=0)
    connections = data.get("connections") or list(DEFAULT_CONNECTIONS)
    active_index = int(data.get("active_index", 0))
    if not connections:
        connections = list(DEFAULT_CONNECTIONS)
        active_index = 0
    if active_index < 0 or active_index >= len(connections):
        active_index = 0
    return ConnectionSettings(connections=connections, active_index=active_index)


def save_connection_settings(settings: ConnectionSettings) -> None:
    path = _settings_path()
    payload = {
        "connections": settings.connections,
        "active_index": settings.active_index,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
