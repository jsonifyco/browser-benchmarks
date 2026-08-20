import time
from typing import Any
from browserbase import Browserbase
from playwright.sync_api import sync_playwright
from .core import Adapter, RunContext, capture_cdp_or_playwright_screenshot


class BrowserbaseAdapter(Adapter):
    def __init__(self, source: str, source_config: dict[str, Any]) -> None:
        super().__init__(source, source_config)
        self.api_key = self.config.get("api_key")
        self.project_id = self.config.get("project_id")
        if not self.api_key or not self.project_id:
            raise RuntimeError("Browserbase api_key/project_id not found in config")

    def build_session_payload(self) -> dict[str, Any]:
        payload = {
            "region": self.config["region"],
            "keep_alive": False,
            "timeout": int((self.config["page_timeout_ms"] + self.config["wait_after_load_ms"]) / 1000) + 30,
            "user_metadata": {"runner": "codex-unified-benchmark", "source": self.source, "mode": self.config["mode"]},
        }
        payload.update(self.config["session_payload"])
        return payload

    def capture(self, ctx: RunContext, url: str, index: int, attempt: int) -> dict[str, Any]:
        from browserbase import Browserbase
        from playwright.sync_api import sync_playwright

        started = time.time()
        path = self.screenshot_path(ctx, url, index)
        path.parent.mkdir(parents=True, exist_ok=True)

        bb = Browserbase(api_key=self.api_key)
        session = bb.sessions.create(project_id=self.project_id, **self.build_session_payload())
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(session.connect_url)
            try:
                context = browser.contexts[0] if browser.contexts else browser.new_context()
                page = context.pages[0] if context.pages else context.new_page()
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
                browser.close()

        local_path = str(path.resolve())
        return {
            "local_path": local_path,
            "session_id": session.id,
            "seconds": round(time.time() - started, 2),
        }

