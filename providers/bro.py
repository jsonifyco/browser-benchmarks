import json
import os
import time
import uuid
from pathlib import Path
from typing import Any
import urllib.request

from bro import BroClient, commands
from .core import Adapter, RunContext


class BroAdapter(Adapter):
    def __init__(self, source: str, source_config: dict[str, Any]) -> None:
        super().__init__(source, source_config)
        self.api_key = self.config.get("api_key")
        if not self.api_key:
            raise RuntimeError("api_key not found in config")

    def session_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "enable_proxy": bool(self.config["enable_proxy"]),
            "rotate_proxy": bool(self.config.get("rotate_proxy", False)),
        }
        if self.config["enable_proxy"]:
            payload.update(
                {
                    "proxy_tier": self.config["proxy_tier"],
                    "proxy_policy": self.config["proxy_policy"],
                    "country": self.config["proxy_country"],
                }
            )
        return payload

    def download_screenshot(self, command_result: dict[str, Any], ctx: RunContext, url: str, index: int) -> str:
        command_list = (command_result.get("response") or {}).get("commands") or []
        cloud_url = None
        for step in command_list:
            if step.get("command") != "get_screenshot":
                continue

            if step.get("offloaded_data_url"):
                cloud_url = step["offloaded_data_url"]
                break
            
            data = step.get("data") or {}
            if data.get("image_url"):
                cloud_url = data["image_url"]
                break
            if data.get("image_urls"):
                cloud_url = data["image_urls"][0]
                break

        if not cloud_url:
            raise RuntimeError(f"image_url not found in command response: {json.dumps(command_result)[:1200]}")

        req = urllib.request.Request(cloud_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            png_data = response.read()

        local_file = self.screenshot_path(ctx, url, index)
        local_file.parent.mkdir(parents=True, exist_ok=True)
        local_file.write_bytes(png_data)
        
        return str(local_file.resolve())

    def capture(self, ctx: RunContext, url: str, index: int, attempt: int) -> dict[str, Any]:
        started = time.time()
        client = BroClient(api_key=self.api_key)
        
        if self.config.get("api_url"):
            client.base_url = self.config["api_url"]
            
        payload = self.session_payload()
        
        with client.create_session(**payload) as session:
            session_id = session.session_id
            
            result = session.execute([
                commands.open_url(url=url),
                commands.sleep(wait_time=self.config["wait_after_load_ms"] / 1000.0),
                commands.get_screenshot(mode="full_page"),
            ])
            
            if result.get("status") == "failed":
                raise RuntimeError(f"{result.get('error_name')}: {result.get('error_message')}")
            
            local_path = self.download_screenshot(result, ctx, url, index)
            
            return {
                "local_path": local_path,
                "session_id": session_id,
                "seconds": round(time.time() - started, 2),
            }
