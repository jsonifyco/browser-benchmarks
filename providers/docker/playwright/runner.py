import base64
import json
import os
import sys
import uuid
import time

def get_proxy_auth(index: int, proxy_config: dict, session_prefix: str = "") -> tuple[str, str]:
    session = f"{session_prefix}{index:03d}{uuid.uuid4().hex[:10]}"
    country = str(proxy_config.get("country", "us"))
    ttl = str(proxy_config.get("ttl_minutes", 30))
    
    uname_tpl = proxy_config.get("username_template")
    pwd_tpl = proxy_config.get("password_template")
    
    username_val = proxy_config.get("username", "")
    password_val = proxy_config.get("password", "")
    
    if uname_tpl:
        username = uname_tpl.replace("{username}", username_val) \
                            .replace("{password}", password_val) \
                            .replace("{country}", country) \
                            .replace("{session}", session) \
                            .replace("{ttl}", ttl)
    else:
        username = username_val

    if pwd_tpl:
        password = pwd_tpl.replace("{username}", username_val) \
                          .replace("{password}", password_val) \
                          .replace("{country}", country) \
                          .replace("{session}", session) \
                          .replace("{ttl}", ttl)
    else:
        password = password_val

    return username, password

def run_playwright(url: str, index: int, config: dict) -> dict:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    
    proxy_config = config.get("proxy", {})
    use_proxy = config.get("use_proxy", True)
    nav_timeout_ms = config.get("page_timeout_ms", 60000)
    wait_after_load_ms = config.get("wait_after_load_ms", 60000)
    viewport_width = config.get("viewport_width", 1440)
    viewport_height = config.get("viewport_height", 900)
    
    username, password = get_proxy_auth(index, proxy_config)

    with sync_playwright() as p:
        launch_kwargs = {
            "headless": True,
            "args": [
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
                f"--window-size={viewport_width},{viewport_height}",
                "--force-device-scale-factor=1",
                "--lang=en-US,en;q=0.9",
                "--disable-quic",
                "--ignore-certificate-errors",
            ],
        }
        if use_proxy and proxy_config.get("password_template"):
            launch_kwargs["proxy"] = {
                "server": f"http://{proxy_config.get('endpoint', '')}",
                "username": username,
                "password": password
            }
            
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(viewport={"width": viewport_width, "height": viewport_height}, locale="en-US", timezone_id="America/New_York")
        page = context.new_page()
        
        try:
            try:
                page.goto(url, wait_until="load", timeout=nav_timeout_ms)
            except Exception:
                page.goto(url, wait_until="domcontentloaded", timeout=nav_timeout_ms)
                    
            page.wait_for_timeout(wait_after_load_ms)
            page.set_viewport_size({"width": viewport_width, "height": viewport_height})
            
            client = context.new_cdp_session(page)
            client.send("Page.enable")
            metrics = client.send("Page.getLayoutMetrics")
            content_size = metrics.get("cssContentSize") or metrics.get("contentSize") or {}
            width = min(max(int(content_size.get("width") or viewport_width), viewport_width), 20000)
            height = min(max(int(content_size.get("height") or viewport_height), viewport_height), 50000)
            
            try:
                client.send("Emulation.setDeviceMetricsOverride", {
                    "width": width,
                    "height": height,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                })
                screenshot = client.send("Page.captureScreenshot", {
                    "format": "png",
                    "fromSurface": True,
                })
            except Exception:
                client.send("Emulation.clearDeviceMetricsOverride")
                screenshot = client.send("Page.captureScreenshot", {
                    "format": "png",
                    "fromSurface": True,
                    "clip": {"x": 0, "y": 0, "width": viewport_width, "height": viewport_height, "scale": 1},
                })
                
            return {
                "status": "ok", 
                "screenshot": screenshot["data"], 
            }
        finally:
            context.close()
            browser.close()

if __name__ == "__main__":
    url = sys.argv[1]
    index = int(sys.argv[2])
    config = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    try:
        res = run_playwright(url, index, config)
        print(json.dumps(res, ensure_ascii=True))
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)[:1200]}, ensure_ascii=True))
