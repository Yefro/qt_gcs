# AGENTS.md

## Objetivo
Mantener cambios pequeños, seguros y verificables. Prioriza correcciones de bugs y claridad del flujo de datos.

## Preferencias de trabajo
- Idioma: español.
- Estilo: conciso, directo, sin relleno.
- No modificar archivos en `dist`, `build`, `build_tmp`, `dist_build`, `__pycache__`, `.venv`.
- Evitar cambios en `gcs/ui/web/map.html` salvo que el objetivo sea UI/Mapa.

## Flujo recomendado
1. Leer/entender el flujo actual en `gcs/ui/main_window.py`, `gcs/viewmodels/main_viewmodel.py`, `gcs/services/telemetry_service.py`, `gcs/mavlink/connection.py`.
2. Cambios mínimos y localizados.
3. Si hay riesgo de regresión, sugerir prueba manual.

## Configuración
- La conexión MAVLink por defecto se define en `gcs/mavlink/types.py` y en la UI en `gcs/ui/main_window.py`.
- `gcs/config/settings.py` solo debe usarse si está conectado al flujo real.

## Pruebas
- Si se cambia lógica de telemetría o conexión, ejecutar la app y verificar conexión manualmente.
- Evitar introducir dependencias nuevas sin discutirlo.

## Notas MAVLink/PX4 (contexto operativo)
- `EVENT (410)` es telemetría/eventos, no canal para comandar `TAKEOFF`.
- Confirmar `TAKEOFF` por `COMMAND_ACK` con `command=22` (`MAV_CMD_NAV_TAKEOFF`).
- Si aparece `COMMAND_ACK command=400 result=0`, eso es `ARM/DISARM` aceptado, no `TAKEOFF`.
- En PX4, para evitar `WARN [navigator] Already higher than takeoff altitude`, usar `TAKEOFF` con `COMMAND_INT` y `MAV_FRAME_GLOBAL_RELATIVE_ALT` (altitud relativa explícita).
- GO TO usa `MAV_CMD_DO_REPOSITION (192)` por `COMMAND_LONG` con parámetros tipo QGC: `param1=-1`, `param2=1`, `param4=NaN`, `param5/6/7` lat/lon/alt.
- No enviar `set_mode_send` en GO TO; el vehículo debe estar en un modo que acepte reposicionamiento.
- Si reaparece `WARN [commander] command 192 unsupported`, evaluar `COMMAND_INT` con frame explícito y/o fallback `set_position_target_global_int`.
- Mantener feedback de comando en UI/logs con nombre de `MAV_CMD` y `MAV_RESULT` para depurar ACK de comando equivocado.
