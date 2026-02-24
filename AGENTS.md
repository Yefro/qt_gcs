# AGENTS.md

## Objetivo
Mantener cambios pequeños, seguros y verificables. Prioriza correcciones de bugs y claridad del flujo de datos.

## Preferencias de trabajo
- Idioma: español.
- Estilo: conciso, directo, sin relleno.
- No modificar archivos en `dist`, `build`, `build_tmp`, `dist_build`, `__pycache__`, `.venv`.
- Evitar cambios en `gcs/ui/web/map.html` salvo que el objetivo sea UI/Mapa.

## Flujo recomendado
1. Leer/entender el flujo actual en `gcs/ui/main_window.py`, `gcs/services/telemetry_service.py`, `gcs/mavlink/connection.py`.
2. Cambios mínimos y localizados.
3. Si hay riesgo de regresión, sugerir prueba manual.

## Configuración
- La conexión MAVLink por defecto se define en `gcs/mavlink/types.py` y en la UI en `gcs/ui/main_window.py`.
- `gcs/config/settings.py` solo debe usarse si está conectado al flujo real.

## Pruebas
- Si se cambia lógica de telemetría o conexión, ejecutar la app y verificar conexión manualmente.
- Evitar introducir dependencias nuevas sin discutirlo.
