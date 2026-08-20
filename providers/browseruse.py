import urllib.parse
import time
from typing import Any
from playwright.sync_api import sync_playwright
from .core import Adapter, RunContext, capture_cdp_or_playwright_screenshot


class BrowserUseAdapter(Adapter):
    def __init__(self, source: str, source_config: dict[str, Any]) -> None:
        super().__init__(source, source_config)
        self.api_key = self.config.get("api_key")
        if not self.api_key:
            raise RuntimeError("api_key not found in config")

    def cdp_url(self) -> str:
        timeout_min = int((self.config["page_timeout_ms"] + self.config["wait_after_load_ms"]) / 60000) + 1
        query = {
            "apiKey": self.api_key,
            "proxyCountryCode": self.config["country"].lower(),
            "timeout": str(timeout_min),
            "browserScreenWidth": str(self.config["viewport_width"]),
            "browserScreenHeight": str(self.config["viewport_height"]),
        }
        if "stealth" in self.config:
            query["stealth"] = self.config["stealth"]
        if "requested_mode" in self.config:
            query["requestedMode"] = self.config["requested_mode"]
        if "proxy" in self.config:
            query["proxy"] = self.config["proxy"]
            
        return "wss://connect.browser-use.com?" + urllib.parse.urlencode(query)

    def capture(self, ctx: RunContext, url: str, index: int, attempt: int) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright

        started = time.time()
        path = self.screenshot_path(ctx, url, index)
        path.parent.mkdir(parents=True, exist_ok=True)

        connect_timeout_ms = self.config["page_timeout_ms"] + self.config["wait_after_load_ms"] + 30000

        browser = None
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(self.cdp_url(), timeout=connect_timeout_ms)
            try:
                context = browser.contexts[0] if browser.contexts else browser.new_context()
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(self.config["page_timeout_ms"])
                try:
                    page.goto(url, wait_until="load", timeout=self.config["page_timeout_ms"])
                except Exception:
                    page.goto(url, wait_until="domcontentloaded", timeout=self.config["page_timeout_ms"])
                page.wait_for_timeout(self.config["wait_after_load_ms"])
                screenshot_bytes = capture_cdp_or_playwright_screenshot(page, context)
                if not screenshot_bytes:
                    raise RuntimeError("empty screenshot")
                path.write_bytes(screenshot_bytes)
            finally:
                if browser:
                    browser.close()

        local_path = str(path.resolve())
        return {
            "local_path": local_path,
            "session_id": "",
            "seconds": round(time.time() - started, 2),
        }

