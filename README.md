# Qt GCS - Notas de uso

## MAVLink desde SITL (WSL) hacia la GCS en Windows

Para que el tráfico MAVLink llegue a la GCS en Windows, en la consola `pxh>` del SITL ejecuta:

```sh
mavlink stop-all
mavlink start -x -u 18570 -r 4000000 -f -m onboard -t 172.31.16.1
mavlink status
```

Esto fuerza el envío hacia la IP de Windows (`172.31.16.1`) y el puerto remoto `14550`.
