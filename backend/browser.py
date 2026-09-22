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
        # This process only owns the CDP client. Chrome belongs to the desktop session.
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
            self._browser = None
            try:
                if self._playwright is None:
                    self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.connect_over_cdp(
                    self.cdp_url, timeout=3000
                )
            except Exception as exc:
                self._browser = None
                raise BrowserUnavailable(
                    "No se pudo conectar con Chrome. Comprueba que scripts/start-browser.sh esté ejecutándose."
                ) from exc
            return self._browser

    async def page(self):
        browser = await self._connect()
        contexts = browser.contexts
        if not contexts:
            raise BrowserUnavailable("Chrome está conectado, pero no hay ningún contexto de navegador.")
        context = contexts[0]
        pages = [page for page in context.pages if not page.is_closed()]
        return pages[-1] if pages else await context.new_page()

    async def _run(self, operation):
        for attempt in range(2):
            browser = await self._connect()
            try:
                page = await self.page()
                return await operation(page)
            except BrowserUnavailable:
                raise
            except Exception as exc:
                if browser.is_connected():
                    raise
                self._browser = None
                if attempt:
                    raise BrowserUnavailable("Se perdió la conexión CDP con Chrome.") from exc
        raise BrowserUnavailable("Se perdió la conexión CDP con Chrome.")

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
        url = self.normalize_url(url)
        await self._run(lambda page: page.goto(url, wait_until="domcontentloaded", timeout=30000))
        return await self.status()

    async def back(self):
        await self._run(lambda page: page.go_back(wait_until="domcontentloaded", timeout=15000))
        return await self.status()

    async def forward(self):
        await self._run(lambda page: page.go_forward(wait_until="domcontentloaded", timeout=15000))
        return await self.status()

    async def reload(self):
        await self._run(lambda page: page.reload(wait_until="domcontentloaded", timeout=30000))
        return await self.status()

    async def home(self):
        return await self.navigate(self.home_url)

    async def type_text(self, text):
        await self._run(lambda page: page.keyboard.insert_text(text))

    async def status(self):
        async def snapshot(page):
            try:
                title = await asyncio.wait_for(page.title(), timeout=2)
            except asyncio.TimeoutError:
                raise
            except Exception:
                if self._browser is None or not self._browser.is_connected():
                    raise
                title = ""
            return {"connected": True, "url": page.url, "title": title}

        try:
            return await self._run(snapshot)
        except (BrowserUnavailable, asyncio.TimeoutError):
            return {"connected": False, "url": None, "title": None}
