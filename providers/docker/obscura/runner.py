import base64
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import uuid

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

def wait_for_port(process: subprocess.Popen, timeout_seconds: float = 20) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Obscura server exited with code {process.returncode}")
        try:
            with socket.create_connection(("127.0.0.1", 9222), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError("Timed out waiting for Obscura CDP server")

def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)

def capture(url: str, index: int, config: dict) -> dict:
    from playwright.sync_api import sync_playwright

    proxy_config = config.get("proxy", {})
    use_proxy = config.get("use_proxy", True)
    nav_timeout_ms = config.get("page_timeout_ms", 60000)
    wait_after_load_ms = config.get("wait_after_load_ms", 60000)
    url_timeout_ms = nav_timeout_ms + wait_after_load_ms + 30000
    viewport_width = config.get("viewport_width", 1440)
    viewport_height = config.get("viewport_height", 900)

    username, password = get_proxy_auth(index, proxy_config, session_prefix="ob")
    server = None

    server_env = os.environ.copy()
    server_env.update({
        "OBSCURA_NAV_TIMEOUT_MS": str(nav_timeout_ms),
        "OBSCURA_SCRIPT_DEADLINE_MS": str(nav_timeout_ms),
        "OBSCURA_FETCH_TIMEOUT_MS": str(nav_timeout_ms),
        "OBSCURA_CDP_COMMAND_TIMEOUT_MS": str(url_timeout_ms),
        "OBSCURA_RENDER_RESOURCE_DEADLINE_MS": "10000",
    })
    
    command = [
        "/usr/local/bin/obscura",
        "serve",
        "--host", "127.0.0.1",
        "--port", "9222",
        "--workers", "1",
    ]
    if config.get("stealth"):
        command.append("--stealth")
        
    if use_proxy and proxy_config.get("password_template"):
        proxy_url = f"http://{username}:{password}@{proxy_config.get('endpoint', '')}"
        command.extend(["--proxy", proxy_url])

    try:
        server = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            env=server_env,
            text=True,
        )
        wait_for_port(server)
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(
                "http://127.0.0.1:9222",
                timeout=min(nav_timeout_ms, 60000),
            )
            try:
                context = browser.new_context(
                    viewport={"width": viewport_width, "height": viewport_height},
                )
                page = context.new_page()
                try:
                    page.goto(url, wait_until="load", timeout=nav_timeout_ms)
                except Exception:
                    page.goto(url, wait_until="domcontentloaded", timeout=nav_timeout_ms)

                page.wait_for_timeout(wait_after_load_ms)
                client = context.new_cdp_session(page)
                try:
                    screenshot = client.send(
                        "Page.captureScreenshot",
                        {
                            "format": "png",
                            "fromSurface": True,
                            "captureBeyondViewport": True,
                        },
                    )
                    png_base64 = screenshot["data"]
                except Exception:
                    png_bytes = page.screenshot(type="png", full_page=True, timeout=30000)
                    png_base64 = base64.b64encode(png_bytes).decode('ascii')
                    
                if not png_base64:
                    raise RuntimeError("Obscura produced an empty screenshot")
                    
                return {
                    "status": "ok",
                    "screenshot": png_base64,
                }
            finally:
                context.close()
                browser.close()
    finally:
        stop_process(server)

if __name__ == "__main__":
    url = sys.argv[1]
    index = int(sys.argv[2])
    config = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    try:
        res = capture(url, index, config)
        print(json.dumps(res, ensure_ascii=True))
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)[:1200]}, ensure_ascii=True))
