# TV Reomote

Mando web para controlar desde un móvil un Chrome abierto en un PC Ubuntu conectado a una TV.

```text
Móvil -> FastAPI en Docker :8000 -> Chrome del host por CDP :9222
                                 -> ydotoold 1.x del host -> /dev/uinput
```

Chrome se ejecuta en la sesión gráfica. `ydotoold` se ejecuta en el host desde `/usr/local/bin/ydotoold` y crea `runtime/ydotool.sock`, un socket Unix de datagramas. El contenedor monta el directorio `runtime/`, por lo que puede usar un socket nuevo después de reiniciar el daemon sin recrear el contenedor. La API envía eventos nativos `struct input_event`. La consulta periódica a `/api/status` solo inspecciona el archivo del socket; no abre conexiones ni envía eventos al daemon.

## Instalar y arrancar

Se necesita Docker Engine, Python 3 y `ydotoold` 1.x en `/usr/local/bin`. Si tu distribución solo ofrece `ydotoold` 0.1.8 en `/usr/bin`, compila [ydotool v1.0.4](https://github.com/ReimuNotMoe/ydotool/releases/tag/v1.0.4) en el host:

```bash
sudo apt-get install -y git build-essential cmake
git clone --branch v1.0.4 --depth 1 https://github.com/ReimuNotMoe/ydotool.git /tmp/tv-remote-ydotool
cmake -S /tmp/tv-remote-ydotool -B /tmp/tv-remote-ydotool/build -DBUILD_DOCS=OFF -DSYSTEMD_USER_SERVICE=OFF
cmake --build /tmp/tv-remote-ydotool/build -j "$(nproc)"
sudo cmake --install /tmp/tv-remote-ydotool/build --prefix /usr/local
/usr/local/bin/ydotoold --version
```

Ejecuta después:

```bash
./scripts/setup-host.sh --docker
TV_REMOTE_UID="$(id -u)" TV_REMOTE_GID="$(id -g)" docker compose up -d --build
./scripts/start-browser.sh
./scripts/check.sh
```

El instalador es repetible: configura `tv-remote-ydotoold.service`, retira los servicios antiguos de proxy y API local, y configura Chrome para abrirse al iniciar la sesión gráfica. No sustituye `/usr/local/bin/ydotoold` por `/usr/bin/ydotoold`. Comprueba la versión mediante el ejecutable, sin consultar `dpkg-query`.

Para Docker Snap, coloca el proyecto dentro de tu carpeta personal. Si `docker compose` falla por permisos sobre `/var/run/docker.sock`, [habilita el uso de Docker como usuario normal](https://github.com/canonical/docker-snap/blob/main/README.md#running-docker-as-normal-user) o añade tu usuario al grupo `docker` si usas Docker Engine, y vuelve a iniciar sesión. El instalador deja configurado `ydotoold` y muestra un aviso claro aunque Docker aún no sea accesible.

## Uso y diagnóstico

Abre `http://IP_DEL_PC:8000` desde un móvil de la misma red. El cursor, clics, scroll y teclas usan `/dev/uinput`; navegar y escribir texto en Chrome usan CDP. `./scripts/check.sh` informa por separado del daemon Docker, API, CDP, servicio `ydotoold`, socket y `/dev/uinput`.

Para pantalla completa usa `BROWSER_MODE=fullscreen ./scripts/start-browser.sh`; para kiosk, `BROWSER_MODE=kiosk ./scripts/start-browser.sh`. El perfil se guarda en `~/.local/share/tv-reomote/chrome-profile` con Chrome y en `~/snap/chromium/common/tv-reomote-profile` con Chromium Snap. Puedes cambiarlo con `TV_REMOTE_PROFILE`.

Chrome necesita una sesión gráfica iniciada. Puedes ejecutar `./scripts/install-browser-autostart.sh` para añadirlo al inicio de sesión. El puerto CDP 9222 debe escuchar solo en `127.0.0.1`. La API no incluye autenticación; úsala en una red local de confianza.

La compatibilidad de Netflix y Prime Video con DRM depende de Chrome y de la configuración de Linux.
