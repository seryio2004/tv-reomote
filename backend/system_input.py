"""Desktop input through the ydotoold 0.1.8 Unix socket on Ubuntu.

The packaged 0.1.8 client does not register its documented relative-move
command. The daemon's protocol is the packed uInputRawData structure:
uint16 event type, uint16 code, int32 value, all in native byte order.
"""

import asyncio
import math
import os
import socket
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
EVENT = struct.Struct("=HHi")

KEYS = {
    "ArrowUp": (103,), "ArrowDown": (108,), "ArrowLeft": (105,), "ArrowRight": (106,),
    "Enter": (28,), "Escape": (1,), "Space": (57,), "Tab": (15,),
    "Shift+Tab": (42, 15), "Backspace": (14,), "Delete": (111,),
    "Home": (102,), "End": (107,), "PageUp": (104,), "PageDown": (109,),
}
BUTTONS = {"left": BTN_LEFT, "right": BTN_RIGHT, "middle": BTN_MIDDLE}


def report(*events):
    return b"".join(EVENT.pack(*event) for event in (*events, (EV_SYN, SYN_REPORT, 0)))


class SystemInput:
    def __init__(self):
        self.socket_path = os.getenv("YDOTOOL_SOCKET", "/tmp/.ydotool_socket")
        self._lock = asyncio.Lock()
        self._writer = None
        self._fraction_x = 0.0
        self._fraction_y = 0.0

    def available(self):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(0.2)
                client.connect(self.socket_path)
            return True
        except OSError:
            return False

    async def _send(self, events):
        try:
            if self._writer is None or self._writer.is_closing():
                _, self._writer = await asyncio.wait_for(
                    asyncio.open_unix_connection(self.socket_path), timeout=0.5
                )
            self._writer.write(b"".join(report(*frame) for frame in events))
            await asyncio.wait_for(self._writer.drain(), timeout=0.5)
        except (OSError, asyncio.TimeoutError) as exc:
            await self._close_writer()
            raise InputUnavailable(
                "Entrada del sistema no disponible. Ejecuta scripts/setup-host.sh y comprueba ydotoold."
            ) from exc

    async def _close_writer(self):
        writer, self._writer = self._writer, None
        if writer is not None:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=0.5)
            except (OSError, asyncio.TimeoutError):
                pass

    async def close(self):
        async with self._lock:
            await self._close_writer()

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
