"""Desktop input through the Unix socket of ydotoold 0.1.8 or 1.x."""

import asyncio
import errno
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
# ydotoold 1.x receives one native Linux struct input_event per datagram.
INPUT_EVENT = struct.Struct("@llHHi")

KEYS = {
    "ArrowUp": (103,), "ArrowDown": (108,), "ArrowLeft": (105,), "ArrowRight": (106,),
    "Enter": (28,), "Escape": (1,), "Space": (57,), "Tab": (15,),
    "Shift+Tab": (42, 15), "Backspace": (14,), "Delete": (111,),
    "Home": (102,), "End": (107,), "PageUp": (104,), "PageDown": (109,),
}
BUTTONS = {"left": BTN_LEFT, "right": BTN_RIGHT, "middle": BTN_MIDDLE}


def report(*events):
    return b"".join(EVENT.pack(*event) for event in (*events, (EV_SYN, SYN_REPORT, 0)))


def input_event(event):
    return INPUT_EVENT.pack(0, 0, *event)


class SystemInput:
    def __init__(self):
        self.socket_path = os.getenv("YDOTOOL_SOCKET", "/tmp/.ydotool_socket")
        self._lock = asyncio.Lock()
        self._socket = None
        self._socket_type = None
        self._fraction_x = 0.0
        self._fraction_y = 0.0

    def available(self):
        for socket_type in (socket.SOCK_DGRAM, socket.SOCK_STREAM):
            try:
                with socket.socket(socket.AF_UNIX, socket_type) as client:
                    client.settimeout(0.2)
                    client.connect(self.socket_path)
                return True
            except OSError as exc:
                if exc.errno != errno.EPROTOTYPE:
                    return False
        return False

    async def _connect(self):
        loop = asyncio.get_running_loop()
        for socket_type in (socket.SOCK_DGRAM, socket.SOCK_STREAM):
            client = socket.socket(socket.AF_UNIX, socket_type)
            client.setblocking(False)
            try:
                await asyncio.wait_for(loop.sock_connect(client, self.socket_path), timeout=0.5)
            except OSError as exc:
                client.close()
                if exc.errno == errno.EPROTOTYPE:
                    continue
                raise
            except asyncio.TimeoutError:
                client.close()
                raise
            self._socket = client
            self._socket_type = socket_type
            return
        raise OSError("Tipo de socket de ydotoold no compatible")

    async def _send(self, events):
        try:
            if self._socket is None:
                await self._connect()
            loop = asyncio.get_running_loop()
            if self._socket_type == socket.SOCK_DGRAM:
                for frame in events:
                    for event in (*frame, (EV_SYN, SYN_REPORT, 0)):
                        await asyncio.wait_for(
                            loop.sock_sendall(self._socket, input_event(event)), timeout=0.5
                        )
            else:
                await asyncio.wait_for(
                    loop.sock_sendall(self._socket, b"".join(report(*frame) for frame in events)),
                    timeout=0.5,
                )
        except (OSError, asyncio.TimeoutError) as exc:
            self._close_socket()
            raise InputUnavailable(
                "Entrada del sistema no disponible. Ejecuta scripts/setup-host.sh y comprueba ydotoold."
            ) from exc

    def _close_socket(self):
        client, self._socket = self._socket, None
        self._socket_type = None
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
