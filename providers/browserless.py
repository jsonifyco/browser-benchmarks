import os
import sys
import time
import json
import uuid
import urllib.parse
from pathlib import Path
from typing import Any
from playwright.sync_api import sync_playwright
from .core import Adapter, RunContext, capture_cdp_or_playwright_screenshot


class BrowserlessAdapter(Adapter):
    GOOGLE_HOSTS = {"google.com", "www.google.com", "news.google.com", "youtube.com", "www.youtube.com"}

    def __init__(self, source: str, source_config: dict[str, Any]) -> None:
        super().__init__(source, source_config)
        self.api_key = self.config.get("api_key")
        if not self.api_key:
            raise RuntimeError("api_key not found in config")

    def build_request_url(self, url: str) -> str:
        hostname = urllib.parse.urlparse(url).hostname or ""
        params = {
            "token": self.api_key,
            "proxy": self.config["proxy"],
            "proxySticky": str(self.config["proxy_sticky"]).lower(),
            "proxyLocaleMatch": str(self.config["proxy_locale_match"]).lower(),
            "humanlike": str(self.config["humanlike"]).lower(),
        }
        if self.config.get("captcha"):
            params["captcha"] = "true"
        if self.config.get("system_timeout_seconds"):
            params["timeout"] = str(self.config["system_timeout_seconds"])
        if hostname in self.GOOGLE_HOSTS or hostname.endswith(".google.com"):
            params["proxyPreset"] = "px_ipv6"
        return f"{self.config['endpoint']}?{urllib.parse.urlencode(params)}"

    @staticmethod
    def append_query_params(endpoint: str, params: dict[str, str]) -> str:
        parsed = urllib.parse.urlparse(endpoint)
        query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        query.update(params)
        return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))

    def execute_bql(self, endpoint: str, payload: dict[str, Any], include_launch: bool = False) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if include_launch:
            headers["X-Browserless-Launch"] = json.dumps(self.config["launch"])
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        req_timeout = self.config.get("request_timeout", (self.config.get("page_timeout_ms", 60000) + self.config.get("wait_after_load_ms", 60000)) / 1000 + 30)
        try:
            with urllib.request.urlopen(request, timeout=req_timeout) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {message[:700]}") from exc
        if response_payload.get("errors"):
            messages = []
            for item in response_payload["errors"]:
                messages.append(item.get("message") if isinstance(item, dict) else str(item))
            raise RuntimeError(" | ".join(messages)[:1000])
        return response_payload

    @staticmethod
    def start_session_query() -> str:
        return """
mutation StartSession($reconnectTimeout: Float!) {
  reconnect(timeout: $reconnectTimeout) {
    browserQLEndpoint
    browserWSEndpoint
  }
}
""".strip()

    @staticmethod
    def refresh_session_query() -> str:
        return """
mutation RefreshSession($reconnectTimeout: Float!) {
  reconnect(timeout: $reconnectTimeout) {
    browserQLEndpoint
  }
}
""".strip()

    @staticmethod
    def screenshot_query() -> str:
        return """
mutation CaptureScreenshot {
  screenshot(
    fullPage: true
    type: png
    optimizeForSpeed: true
  ) {
    base64
  }
}
""".strip()

    def wait_with_reconnect(self, reconnect_endpoint: str) -> str:
        remaining = self.config["wait_after_load_ms"]
        interval = max(1000, min(self.config["reconnect_keepalive_interval_ms"], self.config["reconnect_timeout_ms"] // 2))
        current_endpoint = reconnect_endpoint
        while remaining > 0:
            sleep_ms = min(interval, remaining)
            time.sleep(sleep_ms / 1000)
            remaining -= sleep_ms
            if remaining > 0:
                payload = {
                    "query": self.refresh_session_query(),
                    "variables": {"reconnectTimeout": self.config["reconnect_timeout_ms"]},
                    "operationName": "RefreshSession",
                }
                response_payload = self.execute_bql(current_endpoint, payload)
                current_endpoint = self.append_query_params(response_payload["data"]["reconnect"]["browserQLEndpoint"], {"token": self.api_key})
        return current_endpoint

    def capture(self, ctx: RunContext, url: str, index: int, attempt: int) -> dict[str, Any]:
        started = time.time()
        path = self.screenshot_path(ctx, url, index)
        path.parent.mkdir(parents=True, exist_ok=True)
        start_payload = {
            "query": self.start_session_query(),
            "variables": {
                "reconnectTimeout": self.config["reconnect_timeout_ms"],
            },
            "operationName": "StartSession",
        }
        response_payload = self.execute_bql(self.build_request_url(url), start_payload, include_launch=True)
        reconnect_data = response_payload["data"]["reconnect"]
        
        ws_params = {"token": self.api_key}
        if self.config.get("captcha"):
            ws_params["solveCaptchas"] = "true"
        ws_endpoint = self.append_query_params(reconnect_data["browserWSEndpoint"], ws_params)
        
        # Calculate a suitable connection/request timeout from page_timeout and wait_after_load
        req_timeout = self.config.get("request_timeout", (self.config["page_timeout_ms"] + self.config["wait_after_load_ms"]) / 1000 + 30)
        
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(ws_endpoint, timeout=req_timeout * 1000)
            try:
                context = browser.contexts[0] if browser.contexts else browser.new_context()
                page = context.pages[0] if context.pages else context.new_page()
                try:
                    page.goto(url, wait_until="load", timeout=self.config["page_timeout_ms"])
                except Exception:
                    page.goto(url, wait_until="domcontentloaded", timeout=self.config["page_timeout_ms"])
                page.wait_for_timeout(self.config["wait_after_load_ms"])
                screenshot_bytes = capture_cdp_or_playwright_screenshot(page, context)
                path.write_bytes(screenshot_bytes)
            finally:
                browser.close()
        local_path = str(path.resolve())
        return {
            "local_path": local_path,
            "session_id": "",
            "seconds": round(time.time() - started, 2),
        }

