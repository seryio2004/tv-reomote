import asyncio
import errno
import struct
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from backend.system_input import (
    BTN_LEFT, EV_KEY, EV_REL, EV_SYN, INPUT_EVENT, InputUnavailable, REL_WHEEL,
    REL_X, REL_Y, SystemInput, report,
)


class SystemInputTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.input = SystemInput()
        self.input._send = AsyncMock()

    @staticmethod
    def emitted(send):
        return list(struct.iter_unpack(
            "=HHi", b"".join(report(*frame) for call in send.call_args_list for frame in call.args[0])
        ))

    async def test_move_is_relative_and_keeps_fractional_pixels(self):
        await self.input.move(0.6, -0.6)
        await self.input.move(0.6, -0.6)
        self.assertEqual(self.emitted(self.input._send), [
            (EV_REL, REL_X, 1), (EV_REL, REL_Y, -1), (EV_SYN, 0, 0)
        ])

    async def test_click_and_scroll_emit_system_events(self):
        await self.input.click("left")
        await self.input.scroll(0, -550)
        self.assertEqual(self.emitted(self.input._send), [
            (EV_KEY, BTN_LEFT, 1), (EV_SYN, 0, 0),
            (EV_KEY, BTN_LEFT, 0), (EV_SYN, 0, 0),
            (EV_REL, REL_WHEEL, 5), (EV_SYN, 0, 0),
        ])

    async def test_arrow_key_reaches_the_desktop(self):
        await self.input.press("ArrowUp")
        self.assertEqual(self.emitted(self.input._send), [
            (EV_KEY, 103, 1), (EV_SYN, 0, 0),
            (EV_KEY, 103, 0), (EV_SYN, 0, 0),
        ])

    async def test_missing_daemon_is_reported(self):
        self.input._send = SystemInput._send.__get__(self.input)
        with tempfile.TemporaryDirectory() as directory:
            self.input.socket_path = str(Path(directory) / "missing.sock")
            with self.assertRaises(InputUnavailable):
                await self.input.click("left")

    async def test_stream_daemon_receives_packed_event_frames(self):
        self.input._send = SystemInput._send.__get__(self.input)
        self.input._socket = Mock()
        self.input._socket_type = socket.SOCK_STREAM
        loop = asyncio.get_running_loop()
        with patch.object(loop, "sock_sendall", new_callable=AsyncMock) as send:
            await self.input.move(4, -3)
            await self.input.move(2, 1)
        payload = b"".join(call.args[1] for call in send.call_args_list)
        self.assertEqual(list(struct.iter_unpack("=HHi", payload)), [
            (EV_REL, REL_X, 4), (EV_REL, REL_Y, -3), (EV_SYN, 0, 0),
            (EV_REL, REL_X, 2), (EV_REL, REL_Y, 1), (EV_SYN, 0, 0),
        ])
        await self.input.close()

    async def test_datagram_daemon_receives_native_input_events(self):
        self.input._send = SystemInput._send.__get__(self.input)
        self.input._socket = Mock()
        self.input._socket_type = socket.SOCK_DGRAM
        loop = asyncio.get_running_loop()
        with patch.object(loop, "sock_sendall", new_callable=AsyncMock) as send:
            await self.input.click("left")
        packets = [call.args[1] for call in send.call_args_list]
        self.assertTrue(all(len(packet) == INPUT_EVENT.size for packet in packets))
        self.assertEqual([INPUT_EVENT.unpack(packet)[2:] for packet in packets], [
            (EV_KEY, BTN_LEFT, 1), (EV_SYN, 0, 0),
            (EV_KEY, BTN_LEFT, 0), (EV_SYN, 0, 0),
        ])
        await self.input.close()

    async def test_connect_falls_back_to_stream_for_older_daemon(self):
        loop = asyncio.get_running_loop()
        datagram = Mock()
        stream = Mock()
        with patch("backend.system_input.socket.socket", side_effect=[datagram, stream]), \
                patch.object(loop, "sock_connect", new_callable=AsyncMock) as connect:
            connect.side_effect = [OSError(errno.EPROTOTYPE, "wrong socket type"), None]
            await self.input._connect()
        self.assertIs(self.input._socket, stream)
        self.assertEqual(self.input._socket_type, socket.SOCK_STREAM)
        datagram.close.assert_called_once()
        await self.input.close()

    async def test_status_accepts_both_socket_types(self):
        datagram = MagicMock()
        stream = MagicMock()
        datagram.__enter__.return_value.connect.side_effect = OSError(
            errno.EPROTOTYPE, "wrong socket type"
        )
        with patch("backend.system_input.socket.socket", side_effect=[datagram, stream]):
            self.assertTrue(self.input.available())
