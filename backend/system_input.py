"""Desktop input through the datagram socket of ydotoold 1.x."""

import asyncio
import math
import os
import socket
import stat
import struct


class InputUnavailable(RuntimeError):
    pass


# Linux input-event-codes.h values, also used by libuInputPlus/ydotoold.
EV_SYN = 0
EV_KEY = 1
EV_REL = 2
SYN_REPORT = 0
REL_X = 0
REL_Y = 1
REL_HWHEEL = 6
REL_WHEEL = 8
BTN_LEFT = 0x110
BTN_RIGHT = 0x111
BTN_MIDDLE = 0x112
# ydotoold 1.x receives one native Linux struct input_event per datagram.
INPUT_EVENT = struct.Struct("@llHHi")

KEYS = {
    "ArrowUp": (103,), "ArrowDown": (108,), "ArrowLeft": (105,), "ArrowRight": (106,),
    "Enter": (28,), "Escape": (1,), "Space": (57,), "Tab": (15,),
    "Shift+Tab": (42, 15), "Backspace": (14,), "Delete": (111,),
    "Home": (102,), "End": (107,), "PageUp": (104,), "PageDown": (109,),
}
BUTTONS = {"left": BTN_LEFT, "right": BTN_RIGHT, "middle": BTN_MIDDLE}


def input_event(event):
    return INPUT_EVENT.pack(0, 0, *event)


class SystemInput:
    def __init__(self):
        self.socket_path = os.getenv("YDOTOOL_SOCKET", "runtime/ydotool.sock")
        self._lock = asyncio.Lock()
        self._socket = None
        self._socket_identity = None
        self._send_failed = False
        self._fraction_x = 0.0
        self._fraction_y = 0.0

    def available(self):
        # A status poll must never connect to ydotoold or send it a probe.
        identity = self._path_identity()
        return (identity is not None and os.access(self.socket_path, os.W_OK)
                and (not self._send_failed or identity != self._socket_identity))

    def _path_identity(self):
        try:
            info = os.stat(self.socket_path)
        except OSError:
            return None
        return (info.st_dev, info.st_ino, info.st_ctime_ns) if stat.S_ISSOCK(info.st_mode) else None

    async def _connect(self):
        loop = asyncio.get_running_loop()
        identity = self._path_identity()
        if identity is None:
            raise OSError("No existe el socket de ydotoold 1.x")
        client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        client.setblocking(False)
        try:
            await asyncio.wait_for(loop.sock_connect(client, self.socket_path), timeout=0.5)
        except BaseException:
            client.close()
            raise
        self._socket = client
        self._socket_identity = identity
        self._send_failed = False

    async def _send(self, events):
        try:
            identity = self._path_identity()
            if self._socket is not None and identity != self._socket_identity:
                self._close_socket()
            if self._socket is None:
                await self._connect()
            loop = asyncio.get_running_loop()
            for frame in events:
                for event in (*frame, (EV_SYN, SYN_REPORT, 0)):
                    await asyncio.wait_for(
                        loop.sock_sendall(self._socket, input_event(event)), timeout=0.5
                    )
        except (OSError, asyncio.TimeoutError) as exc:
            self._send_failed = True
            self._close_socket()
            raise InputUnavailable(
                "Entrada del sistema no disponible. Ejecuta scripts/setup-host.sh y comprueba ydotoold."
            ) from exc

    def _close_socket(self):
        client, self._socket = self._socket, None
        if client is not None:
            client.close()

    async def close(self):
        async with self._lock:
            self._close_socket()

    async def move(self, dx, dy):
        if not math.isfinite(dx) or not math.isfinite(dy):
            raise ValueError("Movimiento no válido.")
        async with self._lock:
            x = math.trunc(self._fraction_x + dx)
            y = math.trunc(self._fraction_y + dy)
            self._fraction_x += dx - x
            self._fraction_y += dy - y
            if x or y:
                events = []
                if x:
                    events.append((EV_REL, REL_X, x))
                if y:
                    events.append((EV_REL, REL_Y, y))
                await self._send((events,))
        return {"dx": x, "dy": y}

    async def click(self, button):
        if button not in BUTTONS:
            raise ValueError("Botón de ratón no permitido.")
        code = BUTTONS[button]
        async with self._lock:
            await self._send((((EV_KEY, code, 1),), ((EV_KEY, code, 0),)))

    async def press(self, key):
        if key not in KEYS:
            raise ValueError("Tecla no permitida.")
        codes = KEYS[key]
        down = tuple((EV_KEY, code, 1) for code in codes)
        up = tuple((EV_KEY, code, 0) for code in reversed(codes))
        async with self._lock:
            await self._send((down, up))

    async def scroll(self, dx, dy):
        if not math.isfinite(dx) or not math.isfinite(dy):
            raise ValueError("Desplazamiento no válido.")
        events = []
        if dx:
            events.append((EV_REL, REL_HWHEEL, -int(math.copysign(max(1, round(abs(dx) / 120)), dx))))
        if dy:
            events.append((EV_REL, REL_WHEEL, -int(math.copysign(max(1, round(abs(dy) / 120)), dy))))
        if events:
            async with self._lock:
                await self._send((events,))
