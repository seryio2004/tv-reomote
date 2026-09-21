import struct
import unittest
from unittest.mock import AsyncMock, Mock, patch

from backend.system_input import (
    BTN_LEFT, EV_KEY, EV_REL, EV_SYN, InputUnavailable, REL_WHEEL,
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
        with patch("asyncio.open_unix_connection", side_effect=OSError("missing")):
            with self.assertRaises(InputUnavailable):
                await self.input.click("left")

    async def test_socket_receives_packed_event_frames(self):
        writer = Mock()
        writer.is_closing.return_value = False
        writer.drain = AsyncMock()
        writer.wait_closed = AsyncMock()
        self.input._send = SystemInput._send.__get__(self.input)
        connect = AsyncMock(return_value=(None, writer))
        with patch("asyncio.open_unix_connection", new=connect):
            await self.input.move(4, -3)
            await self.input.move(2, 1)
        connect.assert_awaited_once()
        self.assertEqual(list(struct.iter_unpack("=HHi", writer.write.call_args.args[0])), [
            (EV_REL, REL_X, 2), (EV_REL, REL_Y, 1), (EV_SYN, 0, 0)
        ])
        await self.input.close()
        writer.close.assert_called_once()
