import time
import json
import urllib.parse
import requests
from typing import Any
from playwright.sync_api import sync_playwright
from .core import Adapter, RunContext, capture_cdp_or_playwright_screenshot


class HyperbrowserAdapter(Adapter):
    def __init__(self, source: str, source_config: dict[str, Any]) -> None:
        super().__init__(source, source_config)
        self.api_key = self.config.get("api_key")
        if not self.api_key:
            raise RuntimeError("api_key not found in config")

    @property
    def headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key, "Content-Type": "application/json"}

    def session_payload(self) -> dict[str, Any]:
        return {
            "useUltraStealth": self.config["use_ultra_stealth"],
            "useStealth": self.config["use_stealth"],
            "useProxy": self.config["use_proxy"],
            "proxyCountry": self.config["proxy_country"],
            "region": self.config["region"],
            "operatingSystems": self.config["operating_systems"],
            "device": self.config["device"],
            "platform": self.config["platform"],
            "locales": self.config["locales"],
            "screen": {
                "width": self.config["viewport_width"],
                "height": self.config["viewport_height"],
            },
            "solveCaptchas": self.config["solve_captchas"],
            "adblock": self.config["adblock"],
            "trackers": self.config["trackers"],
            "annoyances": self.config["annoyances"],
            "acceptCookies": self.config["accept_cookies"],
            "timeoutMinutes": int((self.config["page_timeout_ms"] + self.config["wait_after_load_ms"]) / 60000) + 1,
            "enableWebRecording": False,
            "enableVideoWebRecording": False,
            "enableLogCapture": False,
            "disablePasswordManager": True,
        }

    def create_session(self) -> dict[str, Any]:
        response = requests.post(
            f"{self.config['api_url']}/api/session",
            headers=self.headers,
            json=self.session_payload(),
            timeout=(self.config["page_timeout_ms"] + self.config["wait_after_load_ms"]) / 1000 + 30,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Hyperbrowser create HTTP {response.status_code}: {response.text[:1000]}")
        try:
            session = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Hyperbrowser create returned invalid JSON: {response.text[:500]}") from exc
        if not session.get("id") or not session.get("wsEndpoint"):
            raise RuntimeError(f"Hyperbrowser create response is incomplete: {json.dumps(session)[:1000]}")
        return session

    def stop_session(self, session_id: str) -> str:
        try:
            response = requests.put(
                f"{self.config['api_url']}/api/session/{urllib.parse.quote(session_id, safe='')}/stop",
                headers={"x-api-key": self.api_key},
                timeout=(self.config["page_timeout_ms"] + self.config["wait_after_load_ms"]) / 1000 + 30,
            )
            if response.status_code >= 400:
                return f"HTTP {response.status_code}: {response.text[:700]}"
            return ""
        except Exception as exc:
            return str(exc)[:700]

    def capture(self, ctx: RunContext, url: str, index: int, attempt: int) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright

        started = time.time()
        path = self.screenshot_path(ctx, url, index)
        path.parent.mkdir(parents=True, exist_ok=True)
        session: dict[str, Any] | None = None

        try:
            session = self.create_session()
            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(
                    session["wsEndpoint"],
                    timeout=self.config["page_timeout_ms"] + self.config["wait_after_load_ms"] + 30000,
                )
                try:
                    context = browser.contexts[0] if browser.contexts else browser.new_context()
                    page = context.pages[0] if context.pages else context.new_page()
                    page.set_default_timeout(self.config["page_timeout_ms"])
                    try:
                        page.goto(url, wait_until="load", timeout=self.config["page_timeout_ms"])
                    except Exception:
                        page.goto(url, wait_until="domcontentloaded", timeout=self.config["page_timeout_ms"])
                    page.wait_for_timeout(self.config["wait_after_load_ms"])
                    screenshot_bytes = capture_cdp_or_playwright_screenshot(
                        page,
                        context,
                    )
                    if not screenshot_bytes:
                        raise RuntimeError("empty screenshot")
                    path.write_bytes(screenshot_bytes)
                finally:
                    browser.close()
        finally:
            if session and session.get("id"):
                self.stop_session(str(session["id"]))

        local_path = str(path.resolve())
        return {
            "local_path": local_path,
            "session_id": str(session.get("id") if session else ""),
            "seconds": round(time.time() - started, 2),
        }

