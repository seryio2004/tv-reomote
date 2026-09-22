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
