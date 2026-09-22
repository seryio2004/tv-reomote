import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# The controller can be unit tested without launching or installing a browser.
try:
    import playwright.async_api
except ImportError:
    sys.modules["playwright"] = types.ModuleType("playwright")
    sys.modules["playwright.async_api"] = types.SimpleNamespace(async_playwright=MagicMock())

from backend.browser import BrowserController


class BrowserControllerTests(unittest.IsolatedAsyncioTestCase):
    def make_browser(self, url):
        browser = MagicMock()
        browser.is_connected.return_value = True
        page = MagicMock()
        page.is_closed.return_value = False
        page.url = url
        page.title = AsyncMock(return_value=url)
        page.goto = AsyncMock()
        page.keyboard.insert_text = AsyncMock()
        context = MagicMock()
        context.pages = [page]
        browser.contexts = [context]
        return browser, page

    async def test_reconnects_when_chrome_restarts(self):
        old, _ = self.make_browser("https://old.example")
        new, _ = self.make_browser("https://new.example")
        playwright = MagicMock()
        playwright.chromium.connect_over_cdp = AsyncMock(side_effect=[old, new])
        playwright.stop = AsyncMock()
        controller = BrowserController()
        with patch("backend.browser.async_playwright") as factory:
            factory.return_value.start = AsyncMock(return_value=playwright)
            self.assertEqual((await controller.status())["url"], "https://old.example")
            old.is_connected.return_value = False
            self.assertEqual((await controller.status())["url"], "https://new.example")
            await controller.close()
        self.assertEqual(playwright.chromium.connect_over_cdp.await_count, 2)
        old.close.assert_not_called()
        new.close.assert_not_called()
        playwright.stop.assert_awaited_once()

    async def test_reconnects_when_cdp_is_lost_during_command(self):
        old, old_page = self.make_browser("https://old.example")
        new, new_page = self.make_browser("https://new.example")
        async def disconnect(*args, **kwargs):
            old.is_connected.return_value = False
            raise RuntimeError("CDP closed")
        old_page.goto.side_effect = disconnect
        playwright = MagicMock()
        playwright.chromium.connect_over_cdp = AsyncMock(side_effect=[old, new])
        controller = BrowserController()
        with patch("backend.browser.async_playwright") as factory:
            factory.return_value.start = AsyncMock(return_value=playwright)
            result = await controller.navigate("example.com")
        self.assertEqual(result["url"], "https://new.example")
        new_page.goto.assert_awaited_once()

    async def test_status_reports_disconnected_then_recovers(self):
        browser, _ = self.make_browser("https://new.example")
        playwright = MagicMock()
        playwright.chromium.connect_over_cdp = AsyncMock(side_effect=[OSError("closed"), browser])
        controller = BrowserController()
        with patch("backend.browser.async_playwright") as factory:
            factory.return_value.start = AsyncMock(return_value=playwright)
            self.assertFalse((await controller.status())["connected"])
            self.assertTrue((await controller.status())["connected"])

    async def test_close_popups_preserves_main_and_manual_tabs(self):
        browser, main_page = self.make_browser("https://main.example")
        manual_page = MagicMock()
        popup_page = MagicMock()
        for page in (main_page, manual_page, popup_page):
            page.is_closed.return_value = False
            page.close = AsyncMock()
        main_page.opener = AsyncMock(return_value=None)
        manual_page.opener = AsyncMock(return_value=None)
        popup_page.opener = AsyncMock(return_value=main_page)
        browser.contexts[0].pages = [main_page, manual_page, popup_page]
        controller = BrowserController()
        controller._connect = AsyncMock(return_value=browser)

        self.assertEqual(await controller.close_popups(), {"closed": 1})
        popup_page.close.assert_awaited_once_with(run_before_unload=False)
        main_page.close.assert_not_awaited()
        manual_page.close.assert_not_awaited()

    async def test_fullscreen_toggles_chrome_window_without_closing_browser(self):
        browser, page = self.make_browser("https://video.example")
        session = MagicMock()
        session.send = AsyncMock(side_effect=[
            {"windowId": 7, "bounds": {"windowState": "normal"}}, {},
            {"windowId": 7, "bounds": {"windowState": "fullscreen"}}, {},
        ])
        session.detach = AsyncMock()
        page.context.new_cdp_session = AsyncMock(return_value=session)
        controller = BrowserController()
        controller._connect = AsyncMock(return_value=browser)

        self.assertEqual(await controller.toggle_fullscreen(), {"fullscreen": True})
        self.assertEqual(await controller.toggle_fullscreen(), {"fullscreen": False})
        self.assertEqual(session.send.call_args_list[1].args, (
            "Browser.setWindowBounds",
            {"windowId": 7, "bounds": {"windowState": "fullscreen"}},
        ))
        self.assertEqual(session.send.call_args_list[3].args, (
            "Browser.setWindowBounds",
            {"windowId": 7, "bounds": {"windowState": "normal"}},
        ))
        self.assertEqual(session.detach.await_count, 2)
        browser.close.assert_not_called()
