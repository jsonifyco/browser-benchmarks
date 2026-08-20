import os
from pathlib import Path
from dotenv import load_dotenv
from yacs.config import CfgNode as CN

ROOT = Path(__file__).resolve().parent

DEFAULT_ENV = ROOT / ".env"
load_dotenv(DEFAULT_ENV)

CFG = CN()

CFG.DEFAULT_RESULTS_DIR = str(ROOT / "results" / "current")
CFG.DEFAULT_URLS = str(ROOT / "urls.csv")

CFG.DEFAULT_PROVIDERS = [
    "bro",
    "browserless",
    "browserbase",
    "browseruse",
    "firecrawl",
    "hyperbrowser",
    "obscura",
    "playwright",
    "selenium",
]

CFG.COMMON = CN()
CFG.COMMON.page_timeout_ms = 60000
CFG.COMMON.wait_after_load_ms = 60000
CFG.COMMON.retry_attempts = 3
CFG.COMMON.retry_backoff_seconds = 8.0
CFG.COMMON.viewport_width = 1440
CFG.COMMON.viewport_height = 900

CFG.PROXY_CONFIG = CN()
CFG.PROXY_CONFIG.endpoint = ""          # add your proxy endpoint here
CFG.PROXY_CONFIG.username = os.environ.get("PROXY_USERNAME", "")
CFG.PROXY_CONFIG.password = os.environ.get("PROXY_PASSWORD", "")
CFG.PROXY_CONFIG.username_template = "{username}"       # ttl and country might be stored here, ie: "{username}_country_{country}_ttl_{ttl}m"
CFG.PROXY_CONFIG.password_template = "{password}"       # or here depending on proxy provider
CFG.PROXY_CONFIG.country = "us"
CFG.PROXY_CONFIG.ttl_minutes = 30

CFG.PROVIDERS = CN()

# Bro
CFG.PROVIDERS.bro = CN()
CFG.PROVIDERS.bro.workers = 40
CFG.PROVIDERS.bro.api_url = "https://api.getbro.ws"
CFG.PROVIDERS.bro.enable_proxy = True
CFG.PROVIDERS.bro.rotate_proxy = True
CFG.PROVIDERS.bro.proxy_tier = "basic"
CFG.PROVIDERS.bro.proxy_policy = "full"
CFG.PROVIDERS.bro.proxy_country = "US"
CFG.PROVIDERS.bro.api_key = os.environ.get("BRO_API_KEY", "")

# Browserless
CFG.PROVIDERS.browserless = CN()
CFG.PROVIDERS.browserless.workers = 10
CFG.PROVIDERS.browserless.endpoint = "https://production-sfo.browserless.io/stealth/bql"
CFG.PROVIDERS.browserless.system_timeout_seconds = 0
CFG.PROVIDERS.browserless.reconnect_timeout_ms = 10000
CFG.PROVIDERS.browserless.reconnect_keepalive_interval_ms = 5000
CFG.PROVIDERS.browserless.proxy = "residential"
CFG.PROVIDERS.browserless.proxy_sticky = True
CFG.PROVIDERS.browserless.proxy_locale_match = True
CFG.PROVIDERS.browserless.humanlike = True
CFG.PROVIDERS.browserless.captcha = False
CFG.PROVIDERS.browserless.launch = CN()
CFG.PROVIDERS.browserless.launch.headless = True
CFG.PROVIDERS.browserless.launch.humanlike = True
CFG.PROVIDERS.browserless.launch.blockAds = True
CFG.PROVIDERS.browserless.launch.blockConsentModals = True
CFG.PROVIDERS.browserless.launch.args = ["--window-size=1440,900", "--lang=en-US,en;q=0.9"]
CFG.PROVIDERS.browserless.api_key = os.environ.get("BROWSERLESS_API_KEY", "")

# Browserbase
CFG.PROVIDERS.browserbase = CN()
CFG.PROVIDERS.browserbase.workers = 20
CFG.PROVIDERS.browserbase.region = "us-west-2"
CFG.PROVIDERS.browserbase.mode = "basic_stealth"
CFG.PROVIDERS.browserbase.session_payload = CN()
CFG.PROVIDERS.browserbase.session_payload.proxies = True
CFG.PROVIDERS.browserbase.session_payload.browser_settings = CN()
CFG.PROVIDERS.browserbase.session_payload.browser_settings.blockAds = True
CFG.PROVIDERS.browserbase.session_payload.browser_settings.solveCaptchas = False
CFG.PROVIDERS.browserbase.api_key = os.environ.get("BROWSERBASE_API_KEY", "")
CFG.PROVIDERS.browserbase.project_id = os.environ.get("BROWSERBASE_PROJECT_ID", "")

# Browseruse
CFG.PROVIDERS.browseruse = CN()
CFG.PROVIDERS.browseruse.workers = 25
CFG.PROVIDERS.browseruse.country = "us"
CFG.PROVIDERS.browseruse.stealth = "service_default"
CFG.PROVIDERS.browseruse.requested_mode = "advanced_stealth"
CFG.PROVIDERS.browseruse.proxy = "browser_use_residential_default"
CFG.PROVIDERS.browseruse.api_key = os.environ.get("BROWSER_USE_API_KEY", "")

# Firecrawl
CFG.PROVIDERS.firecrawl = CN()
CFG.PROVIDERS.firecrawl.workers = 20
CFG.PROVIDERS.firecrawl.api_url = "https://api.firecrawl.dev/v2"
CFG.PROVIDERS.firecrawl.session_ttl_seconds = 900
CFG.PROVIDERS.firecrawl.session_activity_ttl_seconds = 600
CFG.PROVIDERS.firecrawl.max_active_sessions = 5
CFG.PROVIDERS.firecrawl.api_retry_attempts = 10
CFG.PROVIDERS.firecrawl.stream_web_view = False
CFG.PROVIDERS.firecrawl.mode = "browser_sandbox_cdp"
CFG.PROVIDERS.firecrawl.network_location = "service_default"
CFG.PROVIDERS.firecrawl.api_key = os.environ.get("FIRECRAWL_API_KEY", "")

# Hyperbrowser
CFG.PROVIDERS.hyperbrowser = CN()
CFG.PROVIDERS.hyperbrowser.workers = 25
CFG.PROVIDERS.hyperbrowser.api_url = "https://api.hyperbrowser.ai"
CFG.PROVIDERS.hyperbrowser.use_stealth = True
CFG.PROVIDERS.hyperbrowser.use_ultra_stealth = False
CFG.PROVIDERS.hyperbrowser.use_proxy = True
CFG.PROVIDERS.hyperbrowser.proxy_country = "US"
CFG.PROVIDERS.hyperbrowser.region = "us"
CFG.PROVIDERS.hyperbrowser.operating_systems = ["windows"]
CFG.PROVIDERS.hyperbrowser.device = ["desktop"]
CFG.PROVIDERS.hyperbrowser.platform = ["chrome"]
CFG.PROVIDERS.hyperbrowser.locales = ["en"]
CFG.PROVIDERS.hyperbrowser.solve_captchas = False
CFG.PROVIDERS.hyperbrowser.adblock = True
CFG.PROVIDERS.hyperbrowser.trackers = True
CFG.PROVIDERS.hyperbrowser.annoyances = True
CFG.PROVIDERS.hyperbrowser.accept_cookies = True
CFG.PROVIDERS.hyperbrowser.api_key = os.environ.get("HYPERBROWSER_API_KEY", "")

# Obscura
CFG.PROVIDERS.obscura = CN()
CFG.PROVIDERS.obscura.workers = 6
CFG.PROVIDERS.obscura.engine = "obscura"
CFG.PROVIDERS.obscura.version = "v0.2.0"
CFG.PROVIDERS.obscura.build_features = ["render", "stealth"]
CFG.PROVIDERS.obscura.stealth = True
CFG.PROVIDERS.obscura.docker_image = "evals-obscura-stealth:0.2.0"
CFG.PROVIDERS.obscura.docker_build_args = CN()
CFG.PROVIDERS.obscura.docker_build_args.OBSCURA_VERSION = "v0.2.0"
CFG.PROVIDERS.obscura.auto_build_docker = True
CFG.PROVIDERS.obscura.use_proxy = True
CFG.PROVIDERS.obscura.proxy = CFG.PROXY_CONFIG.clone()

# Playwright
CFG.PROVIDERS.playwright = CN()
CFG.PROVIDERS.playwright.workers = 4
CFG.PROVIDERS.playwright.engine = "playwright"
CFG.PROVIDERS.playwright.docker_image = "evals-playwright-benchmark:latest"
CFG.PROVIDERS.playwright.auto_build_docker = True
CFG.PROVIDERS.playwright.use_proxy = True
CFG.PROVIDERS.playwright.proxy = CFG.PROXY_CONFIG.clone()

# Selenium
CFG.PROVIDERS.selenium = CN()
CFG.PROVIDERS.selenium.workers = 4
CFG.PROVIDERS.selenium.engine = "selenium"
CFG.PROVIDERS.selenium.docker_image = "evals-selenium-benchmark:latest"
CFG.PROVIDERS.selenium.auto_build_docker = True
CFG.PROVIDERS.selenium.use_proxy = True
CFG.PROVIDERS.selenium.proxy = CFG.PROXY_CONFIG.clone()
