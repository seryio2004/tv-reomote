# TV Reomote

Mando web para controlar desde un móvil un navegador Chrome abierto en un portátil Ubuntu conectado a una TV.

## Arquitectura

```text
Móvil -> FastAPI/Docker :8000 -> Chrome DevTools Protocol :9222 -> Chrome -> HDMI -> TV
```

Chrome se ejecuta en Ubuntu, no dentro de Docker. FastAPI usa Playwright para conectarse por CDP al navegador existente.

## Funciones

- Abrir URLs completas.
- Atrás, adelante, recargar e inicio.
- Touchpad, clic izquierdo/derecho y scroll.
- Flechas, Enter, Escape, Space y Tab.
- Escritura de texto en el elemento enfocado.
- Accesos rápidos a YouTube, Netflix y Prime Video.

## Arranque

```bash
docker compose up -d --build
chmod +x scripts/*.sh
./scripts/start-browser.sh
```

Modo ventana:

```bash
BROWSER_MODE=window ./scripts/start-browser.sh
```

Modo kiosk:

```bash
BROWSER_MODE=kiosk ./scripts/start-browser.sh
```

El perfil persistente se guarda en `~/.local/share/tv-reomote/chrome-profile`.

Desde el móvil, conectado al mismo Wi-Fi, abre `http://IP_DEL_PORTATIL:8000`.

Comprueba backend y CDP con:

```bash
./scripts/check.sh
```

No expongas el puerto `9222` a la red local. Esta versión no incluye autenticación y está pensada para una primera prueba en una red doméstica de confianza.

## DRM

El proyecto no extrae ni retransmite streams: controla un navegador real. La compatibilidad final de Netflix/Prime con DRM depende del navegador y de la configuración de Linux; para estas plataformas conviene probar Google Chrome.
