from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from backend.browser import BrowserController, BrowserUnavailable
from backend.system_input import InputUnavailable, KEYS, SystemInput

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
browser = BrowserController()
system_input = SystemInput()

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await browser.close()
    await system_input.close()

app = FastAPI(title="TV Reomote", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

class NavigateRequest(BaseModel):
    url: str = Field(min_length=1, max_length=4096)
class KeyRequest(BaseModel):
    key: str = Field(min_length=1, max_length=64)
class TextRequest(BaseModel):
    text: str = Field(max_length=2000)
class MouseMoveRequest(BaseModel):
    dx: float = Field(ge=-1000, le=1000)
    dy: float = Field(ge=-1000, le=1000)
class ClickRequest(BaseModel):
    button: str = "left"
class ScrollRequest(BaseModel):
    dx: float = Field(default=0, ge=-3000, le=3000)
    dy: float = Field(default=0, ge=-3000, le=3000)

def browser_error(exc):
    if isinstance(exc, BrowserUnavailable):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=f"Error al controlar Chrome: {exc}")

def input_error(exc):
    if isinstance(exc, InputUnavailable):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=f"Error de entrada del sistema: {exc}")

@app.get("/")
async def root():
    return FileResponse(FRONTEND_DIR / "remote.html")

@app.get("/remote")
async def remote():
    return FileResponse(FRONTEND_DIR / "remote.html")

@app.get("/api/status")
async def status():
    result = await browser.status()
    result["input_connected"] = system_input.available()
    return result

@app.post("/api/navigate")
async def navigate(req: NavigateRequest):
    try:
        return await browser.navigate(req.url)
    except Exception as exc:
        raise browser_error(exc)

@app.post("/api/back")
async def back():
    try:
        return await browser.back()
    except Exception as exc:
        raise browser_error(exc)

@app.post("/api/forward")
async def forward():
    try:
        return await browser.forward()
    except Exception as exc:
        raise browser_error(exc)

@app.post("/api/reload")
async def reload():
    try:
        return await browser.reload()
    except Exception as exc:
        raise browser_error(exc)

@app.post("/api/home")
async def home():
    try:
        return await browser.home()
    except Exception as exc:
        raise browser_error(exc)

@app.post("/api/close-popups")
async def close_popups():
    try:
        return await browser.close_popups()
    except Exception as exc:
        raise browser_error(exc)

@app.post("/api/fullscreen")
async def toggle_fullscreen():
    try:
        return await browser.toggle_fullscreen()
    except Exception as exc:
        raise browser_error(exc)

@app.post("/api/key")
async def key(req: KeyRequest):
    if req.key not in KEYS:
        raise HTTPException(status_code=400, detail="Tecla no permitida.")
    try:
        await system_input.press(req.key)
        return {"status": "ok"}
    except Exception as exc:
        raise input_error(exc)

@app.post("/api/type")
async def type_text(req: TextRequest):
    try:
        await browser.type_text(req.text)
        return {"status": "ok"}
    except Exception as exc:
        raise browser_error(exc)

@app.post("/api/mouse/move")
async def mouse_move(req: MouseMoveRequest):
    try:
        pos = await system_input.move(req.dx, req.dy)
        return {"status": "ok", **pos}
    except Exception as exc:
        raise input_error(exc)

@app.post("/api/mouse/click")
async def mouse_click(req: ClickRequest):
    if req.button not in {"left", "right", "middle"}:
        raise HTTPException(status_code=400, detail="Botón de ratón no permitido.")
    try:
        await system_input.click(req.button)
        return {"status": "ok"}
    except Exception as exc:
        raise input_error(exc)

@app.post("/api/mouse/scroll")
async def mouse_scroll(req: ScrollRequest):
    try:
        await system_input.scroll(req.dx, req.dy)
        return {"status": "ok"}
    except Exception as exc:
        raise input_error(exc)
