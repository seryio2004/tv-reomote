import asyncio
import os
from urllib.parse import urlparse
from playwright.async_api import async_playwright

class BrowserUnavailable(RuntimeError):
    pass

class BrowserController:
    def __init__(self):
        self.cdp_url = os.getenv("BROWSER_CDP_URL", "http://127.0.0.1:9222")
        self.home_url = os.getenv("HOME_URL", "https://www.youtube.com/")
        self._playwright = None
        self._browser = None
        self._lock = asyncio.Lock()

    async def close(self):
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
        self._browser = None
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        self._playwright = None

    async def _connect(self):
        async with self._lock:
            if self._browser is not None and self._browser.is_connected():
                return self._browser
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            try:
                self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_url, timeout=3000)
            except Exception as exc:
                self._browser = None
                raise BrowserUnavailable("No se pudo conectar con Chrome. Comprueba que scripts/start-browser.sh esté ejecutándose.") from exc
            return self._browser

    async def page(self):
        browser = await self._connect()
        contexts = browser.contexts
        if not contexts:
            raise BrowserUnavailable("Chrome está conectado, pero no hay ningún contexto de navegador.")
        context = contexts[0]
        return context.pages[-1] if context.pages else await context.new_page()

    @staticmethod
    def normalize_url(url):
        url = url.strip()
        if not url:
            raise ValueError("La URL está vacía.")
        parsed = urlparse(url)
        if not parsed.scheme:
            url = "https://" + url
            parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Solo se permiten URLs http:// o https://.")
        if not parsed.netloc:
            raise ValueError("La URL no es válida.")
        return url

    async def navigate(self, url):
        page = await self.page()
        url = self.normalize_url(url)
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return await self.status()

    async def back(self):
        page = await self.page()
        await page.go_back(wait_until="domcontentloaded", timeout=15000)
        return await self.status()

    async def forward(self):
        page = await self.page()
        await page.go_forward(wait_until="domcontentloaded", timeout=15000)
        return await self.status()

    async def reload(self):
        page = await self.page()
        await page.reload(wait_until="domcontentloaded", timeout=30000)
        return await self.status()

    async def home(self):
        return await self.navigate(self.home_url)

    async def type_text(self, text):
        page = await self.page()
        await page.keyboard.insert_text(text)

    async def status(self):
        try:
            page = await self.page()
            try:
                title = await page.title()
            except Exception:
                title = ""
            return {"connected": True, "url": page.url, "title": title}
        except BrowserUnavailable:
            return {"connected": False, "url": None, "title": None}
