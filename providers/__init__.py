from .core import Adapter, RunContext
from .bro import BroAdapter
from .browserless import BrowserlessAdapter
from .browserbase import BrowserbaseAdapter
from .browseruse import BrowserUseAdapter
from .firecrawl import FirecrawlAdapter
from .hyperbrowser import HyperbrowserAdapter
from .playwright import PlaywrightAdapter
from .selenium import SeleniumAdapter
from .obscura import ObscuraAdapter
from config import CFG

def make_adapter(provider: str) -> Adapter:
    provider_config = CFG.PROVIDERS[provider]
    if provider == "bro":
        return BroAdapter(provider, provider_config)
    if provider == "browserless":
        return BrowserlessAdapter(provider, provider_config)
    if provider == "browserbase":
        return BrowserbaseAdapter(provider, provider_config)
    if provider == "browseruse":
        return BrowserUseAdapter(provider, provider_config)
    if provider == "firecrawl":
        return FirecrawlAdapter(provider, provider_config)
    if provider == "hyperbrowser":
        return HyperbrowserAdapter(provider, provider_config)
    if provider == "playwright":
        return PlaywrightAdapter(provider, provider_config)
    if provider == "selenium":
        return SeleniumAdapter(provider, provider_config)
    if provider == "obscura":
        return ObscuraAdapter(provider, provider_config)
    raise RuntimeError(f"Unsupported provider: {provider}")
