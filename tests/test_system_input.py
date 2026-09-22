import asyncio
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from backend.system_input import (
    BTN_LEFT, EV_KEY, EV_REL, EV_SYN, INPUT_EVENT, InputUnavailable, REL_WHEEL,
    REL_X, REL_Y, SystemInput,
)


class SystemInputTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.input = SystemInput()

    async def asyncTearDown(self):
        await self.input.close()

    @staticmethod
    def emitted(send):
        return [INPUT_EVENT.unpack(call.args[1])[2:] for call in send.call_args_list]

    async def test_move_is_relative_and_keeps_fractional_pixels(self):
        self.input._send = AsyncMock()
        await self.input.move(0.6, -0.6)
        await self.input.move(0.6, -0.6)
        self.assertEqual(self.input._send.call_args.args[0], ([(EV_REL, REL_X, 1), (EV_REL, REL_Y, -1)],))

    async def test_click_scroll_and_key_emit_frames(self):
        self.input._send = AsyncMock()
        await self.input.click("left")
        await self.input.scroll(0, -550)
        await self.input.press("ArrowUp")
        self.assertEqual([call.args[0] for call in self.input._send.call_args_list], [
            (((EV_KEY, BTN_LEFT, 1),), ((EV_KEY, BTN_LEFT, 0),)),
            ([(EV_REL, REL_WHEEL, 5)],),
            (((EV_KEY, 103, 1),), ((EV_KEY, 103, 0),)),
        ])

    async def test_volume_keys_emit_linux_media_codes(self):
        self.input._send = AsyncMock()
        for name, code in (("VolumeDown", 114), ("VolumeMute", 113), ("VolumeUp", 115)):
            await self.input.press(name)
            self.assertEqual(self.input._send.call_args.args[0], (
                ((EV_KEY, code, 1),), ((EV_KEY, code, 0),)
            ))

    async def test_missing_daemon_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            self.input.socket_path = str(Path(directory) / "missing.sock")
            with self.assertRaises(InputUnavailable):
                await self.input.click("left")

    async def test_datagram_daemon_receives_native_input_events(self):
        client = Mock()
        loop = asyncio.get_running_loop()
        with patch.object(self.input, "_path_identity", return_value=(1, 10)), \
                patch("backend.system_input.socket.socket", return_value=client) as factory, \
                patch.object(loop, "sock_connect", new_callable=AsyncMock), \
                patch.object(loop, "sock_sendall", new_callable=AsyncMock) as send:
            await self.input.click("left")
        factory.assert_called_once_with(socket.AF_UNIX, socket.SOCK_DGRAM)
        packets = [call.args[1] for call in send.call_args_list]
        self.assertTrue(all(len(packet) == INPUT_EVENT.size for packet in packets))
        self.assertEqual([INPUT_EVENT.unpack(packet)[2:] for packet in packets], [
            (EV_KEY, BTN_LEFT, 1), (EV_SYN, 0, 0),
            (EV_KEY, BTN_LEFT, 0), (EV_SYN, 0, 0),
        ])

    async def test_status_never_connects_to_daemon(self):
        with patch.object(self.input, "_path_identity", return_value=(1, 10)), \
                patch("backend.system_input.os.access", return_value=True), \
                patch("backend.system_input.socket.socket", side_effect=AssertionError("status opened socket")):
            for _ in range(100):
                self.assertTrue(self.input.available())

    async def test_reconnects_after_socket_is_recreated(self):
        first, second = Mock(), Mock()
        identity = (1, 10)
        loop = asyncio.get_running_loop()
        with patch.object(self.input, "_path_identity", side_effect=lambda: identity), \
                patch("backend.system_input.socket.socket", side_effect=[first, second]) as factory, \
                patch.object(loop, "sock_connect", new_callable=AsyncMock) as connect, \
                patch.object(loop, "sock_sendall", new_callable=AsyncMock) as send:
            await self.input.press("Enter")
            identity = (1, 11)
            await self.input.press("Escape")
        self.assertEqual(factory.call_count, 2)
        self.assertEqual(connect.await_count, 2)
        first.close.assert_called_once()
        self.assertEqual([call.args[0] for call in send.call_args_list], [first] * 4 + [second] * 4)
        self.assertEqual(INPUT_EVENT.unpack(send.call_args_list[4].args[1])[2:], (EV_KEY, 1, 1))

    async def test_failed_send_recovers_on_next_request(self):
        first, second = Mock(), Mock()
        identity = (1, 10)
        loop = asyncio.get_running_loop()
        with patch.object(self.input, "_path_identity", side_effect=lambda: identity), \
                patch("backend.system_input.os.access", return_value=True), \
                patch("backend.system_input.socket.socket", side_effect=[first, second]), \
                patch.object(loop, "sock_connect", new_callable=AsyncMock), \
                patch.object(loop, "sock_sendall", new_callable=AsyncMock) as send:
            send.side_effect = OSError("daemon stopped")
            with self.assertRaises(InputUnavailable):
                await self.input.press("Enter")
            self.assertFalse(self.input.available())
            identity = (1, 11)
            self.assertTrue(self.input.available())
            send.side_effect = None
            await self.input.press("Escape")
            self.assertIs(send.call_args.args[0], second)
