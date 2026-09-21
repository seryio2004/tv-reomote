from pathlib import Path
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="TV Remote")


class ConnectionManager:
    def __init__(self):
        self.connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead_connections = []

        for connection in self.connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)

        for connection in dead_connections:
            self.disconnect(connection)


manager = ConnectionManager()


class PlayRequest(BaseModel):
    url: str


class SeekRequest(BaseModel):
    seconds: float


class VolumeRequest(BaseModel):
    value: float


app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static",
)


@app.get("/")
async def root():
    return FileResponse(FRONTEND_DIR / "remote.html")


@app.get("/remote")
async def remote():
    return FileResponse(FRONTEND_DIR / "remote.html")


@app.get("/player")
async def player():
    return FileResponse(FRONTEND_DIR / "player.html")


@app.post("/api/play")
async def play(request: PlayRequest):
    await manager.broadcast({
        "type": "play",
        "url": request.url,
    })

    return {"status": "ok"}


@app.post("/api/pause")
async def pause():
    await manager.broadcast({
        "type": "pause",
    })

    return {"status": "ok"}


@app.post("/api/resume")
async def resume():
    await manager.broadcast({
        "type": "resume",
    })

    return {"status": "ok"}


@app.post("/api/stop")
async def stop():
    await manager.broadcast({
        "type": "stop",
    })

    return {"status": "ok"}


@app.post("/api/seek")
async def seek(request: SeekRequest):
    await manager.broadcast({
        "type": "seek",
        "seconds": request.seconds,
    })

    return {"status": "ok"}


@app.post("/api/volume")
async def volume(request: VolumeRequest):
    value = max(0.0, min(1.0, request.value))

    await manager.broadcast({
        "type": "volume",
        "value": value,
    })

    return {"status": "ok"}


@app.get("/api/status")
async def status():
    return {
        "status": "ok",
        "connected_clients": len(manager.connections),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            # Mantiene viva la conexión.
            # El player puede enviar eventos en versiones posteriores.
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(websocket)
