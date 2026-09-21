# TV Reomote

Mando web para controlar desde un móvil un navegador Chrome abierto en un PC Ubuntu conectado a una TV.

## Arquitectura

```text
Móvil -> FastAPI (Docker o Ubuntu) :8000 -> Chrome por CDP :9222 (navegación y texto)
                                    -> ydotoold del host -> /dev/uinput (cursor, clic, scroll y teclas)
```

El cursor visible se mueve con eventos de entrada del sistema. Chrome y la entrada del sistema tienen indicadores de conexión independientes en el mando. `ydotoold` siempre se ejecuta en Ubuntu; si la API está en Docker, un puente `socat` ofrece su socket en `runtime/ydotool.sock` para que Docker pueda montarlo.

## Arranque con Docker Compose

Instala y arranca el servicio de entrada en Ubuntu. El instalador usa `sudo` para instalar `ydotoold` y crear su servicio de systemd:

```bash
./scripts/setup-host.sh --docker
```

Arranca la API con el UID y GID del usuario que ejecutó el instalador. Así el contenedor puede abrir el socket privado `runtime/ydotool.sock`:

```bash
TV_REMOTE_UID="$(id -u)" TV_REMOTE_GID="$(id -g)" docker compose up -d --build
./scripts/start-browser.sh  # Solo para abrir Chrome ahora, sin esperar al próximo inicio de sesión
./scripts/check.sh
```

El navegador debe ejecutarse en la sesión gráfica de Ubuntu. Compose mantiene `network_mode: host` para conectar con Chrome por `127.0.0.1:9222` y monta únicamente el socket del puente de entrada. Si reinicias `tv-remote-socket-proxy.service`, recrea el contenedor con `TV_REMOTE_UID="$(id -u)" TV_REMOTE_GID="$(id -g)" docker compose up -d --force-recreate` para montar el socket nuevo.

El instalador reconoce Docker Engine instalado por paquetes o mediante Snap. Para Docker Snap, deja el proyecto dentro de tu carpeta personal, por ejemplo `~/codes/remote-tv`: Snap aísla `/tmp` y limita el acceso a archivos fuera de la carpeta personal. Si `docker compose` indica que no tienes permiso para acceder al daemon, sigue las [instrucciones del paquete Docker Snap para usarlo como usuario normal](https://github.com/canonical/docker-snap/blob/main/README.md#running-docker-as-normal-user) y vuelve a iniciar sesión antes de ejecutar Compose.

Después del primer `docker compose up`, la API arrancará al encender el portátil: el instalador habilita el servicio de Docker correspondiente, `ydotoold` y el puente de entrada; Compose aplica `restart: unless-stopped`. Si detienes o eliminas el contenedor manualmente, vuelve a ejecutar `docker compose up -d`. El instalador también configura Chrome para abrirse a pantalla completa al iniciar tu sesión gráfica.

## Arranque sin Docker

Si prefieres ejecutar también la API en Ubuntu, detén primero el contenedor para liberar el puerto 8000. El instalador crea el entorno Python y activa la API y `ydotoold` como servicios de systemd:

```bash
docker compose down
./scripts/setup-host.sh
./scripts/start-browser.sh  # Solo para abrir Chrome ahora, sin esperar al próximo inicio de sesión
./scripts/check.sh
```

El instalador está preparado para `ydotoold` 0.1.8 de Ubuntu. En esa versión el daemon crea `/tmp/.ydotool_socket` con acceso restringido; el servicio concede acceso solo al usuario que ejecutó el instalador. La API envía eventos mediante el protocolo de esa versión.

En este modo, los servicios `tv-remote-api` y `tv-remote-ydotoold` quedan habilitados para arrancar con Ubuntu. Chrome se abrirá a pantalla completa al iniciar tu sesión gráfica.

## Uso

Para pantalla completa usa `BROWSER_MODE=fullscreen ./scripts/start-browser.sh`; para modo kiosk, `BROWSER_MODE=kiosk ./scripts/start-browser.sh`. El perfil persistente se guarda en `~/.local/share/tv-reomote/chrome-profile` con Chrome y en `~/snap/chromium/common/tv-reomote-profile` con Chromium Snap. Puedes cambiarlo con `TV_REMOTE_PROFILE`.

El navegador necesita una sesión gráfica iniciada. Si los servicios ya estaban instalados, ejecuta `./scripts/install-browser-autostart.sh` una vez para añadir Chrome al inicio de sesión sin volver a instalar nada. Para que aparezca también sin escribir la contraseña tras encender el portátil, activa «Inicio de sesión automático» en Configuración → Sistema → Usuarios de Ubuntu. Esto permite acceder a tu sesión a cualquier persona que encienda el equipo.

Desde el móvil, conectado al mismo Wi-Fi, abre `http://IP_DEL_PC:8000`. El joystick mueve el cursor del escritorio; clic, scroll y flechas funcionan aunque Chrome no esté conectado. URLs y texto requieren Chrome por CDP.

Si aparece `Control desconectado`, consulta `systemctl status tv-remote-ydotoold.service`. Si aparece `Chrome desconectado`, comprueba que el navegador está abierto con el script anterior.

El puerto `9222` solo debe escuchar en `127.0.0.1`. La API no incluye autenticación: úsala únicamente en una red local de confianza.

## DRM

El proyecto controla un navegador real. La compatibilidad de Netflix y Prime Video con DRM depende del navegador y de la configuración de Linux; prueba Google Chrome para estas plataformas.
