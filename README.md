# TV Remote

Base mínima para controlar desde el móvil un reproductor web
abierto en Chromium en un portátil conectado a una TV.

## Arquitectura

- FastAPI dentro de Docker.
- `/remote`: mando para el móvil.
- `/player`: reproductor para la TV.
- WebSocket para enviar comandos al reproductor.
- Chromium se ejecuta en Ubuntu, fuera de Docker.

## 1. Arrancar el servidor

```bash
docker compose up -d --build
```

Comprueba:

```bash
docker compose ps
```

## 2. Abrir el reproductor en el portátil

Da permisos al script:

```bash
chmod +x scripts/start-kiosk.sh
```

Ejecuta:

```bash
./scripts/start-kiosk.sh
```

También puedes abrir manualmente:

```text
http://localhost:8000/player
```

## 3. Abrir el mando desde el móvil

Obtén la IP local del portátil:

```bash
hostname -I
```

Por ejemplo:

```text
192.168.1.50
```

Desde el móvil, conectado a la misma red:

```text
http://192.168.1.50:8000/remote
```

## Importante sobre las URLs

Esta primera versión usa un elemento HTML `<video>`.

Eso significa que la URL enviada debe apuntar a contenido que Chromium
pueda reproducir directamente.

Ejemplos habituales:

- MP4 accesible por HTTP/HTTPS.
- WebM.
- Otros formatos soportados por Chromium.

Una URL normal de una página de YouTube no es una URL directa de vídeo y
no funcionará simplemente asignándola al `<video>`.

El soporte para YouTube, Twitch y otras plataformas se puede añadir en una
segunda fase mediante un resolvedor de URLs, yt-dlp o un enfoque diferente
de reproducción.
