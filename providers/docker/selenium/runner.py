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

def run_selenium(url: str, index: int, config: dict) -> dict:
    from seleniumwire import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    proxy_config = config.get("proxy", {})
    use_proxy = config.get("use_proxy", True)
    nav_timeout_ms = config.get("page_timeout_ms", 60000)
    wait_after_load_ms = config.get("wait_after_load_ms", 60000)
    viewport_width = config.get("viewport_width", 1440)
    viewport_height = config.get("viewport_height", 900)

    username, password = get_proxy_auth(index, proxy_config)
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--window-size={viewport_width},{viewport_height}")
    options.add_argument("--lang=en-US,en;q=0.9")
    
    driver_kwargs = {"service": Service(), "options": options}
    
    if use_proxy and proxy_config.get("password_template"):
        proxy_url = f"http://{username}:{password}@{proxy_config.get('endpoint', '')}"
        seleniumwire_options = {
            "proxy": {
                "http": proxy_url,
                "https": proxy_url,
                "no_proxy": "localhost,127.0.0.1",
            },
            "verify_ssl": False,
            "suppress_connection_errors": True,
        }
        driver_kwargs["seleniumwire_options"] = seleniumwire_options
        
    driver = webdriver.Chrome(**driver_kwargs)
    try:
        driver.set_page_load_timeout(nav_timeout_ms / 1000)
        try:
            driver.get(url)
        except Exception:
            pass
            
        time.sleep(wait_after_load_ms / 1000)
        
        try:
            width = driver.execute_script("return Math.max(document.body.scrollWidth, document.documentElement.scrollWidth, window.innerWidth);") or viewport_width
            height = driver.execute_script("return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, window.innerHeight);") or viewport_height
            driver.set_window_size(min(max(int(width), viewport_width), 20000), min(max(int(height), viewport_height), 50000))
            time.sleep(1)
        except Exception:
            pass
            
        screenshot_b64 = driver.get_screenshot_as_base64()
        if not screenshot_b64:
            raise RuntimeError("selenium save_screenshot produced empty file")
            
        return {
            "status": "ok", 
            "screenshot": screenshot_b64,
        }
    finally:
        driver.quit()

if __name__ == "__main__":
    url = sys.argv[1]
    index = int(sys.argv[2])
    config = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    try:
        res = run_selenium(url, index, config)
        print(json.dumps(res, ensure_ascii=True))
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)[:1200]}, ensure_ascii=True))
