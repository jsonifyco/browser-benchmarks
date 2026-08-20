import os
import json
import time
import urllib.parse
import re
from threading import BoundedSemaphore, Lock
import requests
from typing import Any
from .core import Adapter, RunContext


class FirecrawlAdapter(Adapter):
    def __init__(self, source: str, source_config: dict[str, Any]) -> None:
        super().__init__(source, source_config)
        self.api_key = self.config.get("api_key")
        if not self.api_key:
            raise RuntimeError("api_key not found in config")

        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        )
        self.session_slots = BoundedSemaphore(self.config["max_active_sessions"])
        self.api_gate_lock = Lock()

    def request_json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = None
        # A single gate makes provider cooldown global instead of letting all 20
        # workers consume the same request-per-minute window independently.
        with self.api_gate_lock:
            req_timeout = (self.config["page_timeout_ms"] + self.config["wait_after_load_ms"]) / 1000 + 30
            for api_attempt in range(1, self.config["api_retry_attempts"] + 1):
                response = self.session.request(
                    method,
                    f"{self.config['api_url']}{path}",
                    timeout=req_timeout,
                    **kwargs,
                )
                if response.status_code != 429 or api_attempt >= self.config["api_retry_attempts"]:
                    break
                retry_after = response.headers.get("Retry-After", "")
                match = re.search(r"retry after\s+(\d+)s", response.text, re.IGNORECASE)
                delay = float(retry_after) if retry_after.isdigit() else float(match.group(1) if match else 15)
                time.sleep(max(1.0, min(delay, 65.0)))
        assert response is not None
        if response.status_code >= 400:
            raise RuntimeError(f"Firecrawl HTTP {response.status_code}: {response.text[:1000]}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Firecrawl returned invalid JSON: {response.text[:500]}") from exc
        if payload.get("success") is not True:
            raise RuntimeError(f"Firecrawl request failed: {json.dumps(payload, ensure_ascii=False)[:1000]}")
        return payload

    def create_browser_session(self) -> dict[str, Any]:
        json_payload = {
            "ttl": self.config["session_ttl_seconds"],
            "activityTtl": self.config["session_activity_ttl_seconds"],
            "streamWebView": self.config["stream_web_view"],
        }
        if "mode" in self.config:
            json_payload["mode"] = self.config["mode"]
        if "network_location" in self.config:
            json_payload["networkLocation"] = self.config["network_location"]
            
        payload = self.request_json(
            "POST",
            "/browser",
            json=json_payload,
        )
        if not payload.get("id") or not payload.get("cdpUrl"):
            raise RuntimeError("Firecrawl Browser Sandbox response is missing id or cdpUrl")
        return payload

    def delete_browser_session(self, session_id: str) -> dict[str, Any]:
        try:
            return self.request_json("DELETE", f"/browser/{urllib.parse.quote(session_id, safe='')}")
        except Exception as exc:
            return {"success": False, "error": str(exc)[:700]}

    def capture(self, ctx: RunContext, url: str, index: int, attempt: int) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright

        started = time.time()
        path = self.screenshot_path(ctx, url, index)
        path.parent.mkdir(parents=True, exist_ok=True)
        session_id = ""

        self.session_slots.acquire()
        try:
            try:
                session_payload = self.create_browser_session()
                session_id = str(session_payload["id"])
                with sync_playwright() as playwright:
                    browser = playwright.chromium.connect_over_cdp(
                        session_payload["cdpUrl"], timeout=self.config["page_timeout_ms"] + self.config["wait_after_load_ms"] + 30000
                    )
                    try:
                        context = browser.contexts[0] if browser.contexts else browser.new_context()
                        page = context.pages[0] if context.pages else context.new_page()
                        page.set_default_timeout(self.config["page_timeout_ms"])
                        page.set_viewport_size(
                            {
                                "width": self.config["viewport_width"],
                                "height": self.config["viewport_height"],
                            }
                        )
                        try:
                            page.goto(url, wait_until="load", timeout=self.config["page_timeout_ms"])
                        except Exception:
                            pass
                        page.wait_for_timeout(self.config["wait_after_load_ms"])
                        image = page.screenshot(
                            full_page=True,
                            type="png",
                            timeout=self.config["page_timeout_ms"],
                            animations="disabled",
                            caret="hide",
                        )
                        if not image:
                            raise RuntimeError("Firecrawl Browser Sandbox returned an empty screenshot")
                        if not image.startswith(b"\x89PNG\r\n\x1a\n"):
                            raise RuntimeError(f"Firecrawl screenshot is not PNG (magic={image[:12].hex()})")
                        path.write_bytes(image)
                    finally:
                        browser.close()
            finally:
                if session_id:
                    self.delete_browser_session(session_id)
        finally:
            self.session_slots.release()

        local_path = str(path.resolve())
        return {
            "local_path": local_path,
            "session_id": session_id,
            "seconds": round(time.time() - started, 2),
        }

