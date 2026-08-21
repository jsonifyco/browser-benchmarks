# Dedicated Browser Evals: Anti-Bot Bypass Benchmark for Cloud Browsers & BaaS

> **An open-source benchmark evaluating how top Browser-as-a-Service (BaaS) providers and open-source frameworks bypass modern anti-bot protections (Cloudflare, DataDome, Akamai) across 400 protected websites.**

[**Read the full detailed blog post here**](https://getbro.ws/blog/cloud-browsers-benchmark)

## Overview
Most scraping and agent benchmarks evaluate UI interaction or high-level reasoning. This repository benchmarks the foundational infrastructure layer: **how effectively dedicated Browser-as-a-Service (cloud browser) providers and open-source browser engines passively bypass modern anti-bot systems.**

We evaluated real-world access rates and costs across 400 highly protected domains - comparing dedicated cloud browsers (bro, Browserbase, Browser Use, Browserless, Firecrawl, Hyperbrowser) against open-source solutions (Playwright, Selenium, Obscura) without relying on automated CAPTCHA solving.

*Note: The target URLs evaluated in this benchmark are listed in [`urls.csv`](urls.csv). We will periodically update this list to ensure the benchmark remains relevant.*

## Results

*The full results from our v1 benchmark run are available at [`official_results/v1/results.csv`](official_results/v1/results.csv) and [`official_results/v1/summary.csv`](official_results/v1/summary.csv).*

| Provider | Success Rate | Avg Cost / URL |
| --- | --- | --- |
| [**bro**](https://getbro.ws/) | **83.50%** | $0.0274 |
| [**browserbase**](https://www.browserbase.com/solutions/browser-agents) | **79.75%** | $0.0887 |
| [**browseruse**](https://browser-use.com/stealth-browsers) | **79.75%** | $0.0231 |
| [**browserless**](https://www.browserless.io/feature/browsers-as-a-service) | **75.50%** | $0.0542 |
| [**firecrawl**](https://www.firecrawl.dev/interact) | **73.50%** | $0.0359 |
| [**hyperbrowser**](https://www.hyperbrowser.ai/browser-sessions) | **63.25%** | $0.0577 |
| [**obscura**](https://github.com/h4ckf0r0day/obscura) | **39.50%** | $0.0499 |
| [**selenium**](https://github.com/seleniumhq/selenium) | **37.00%** | $0.0499 |
| [**playwright**](https://github.com/microsoft/playwright) | **36.25%** | $0.0499 |

## Methodology
The benchmark operates on extremely simple pipeline to determine if a browser successfully accessed a URL or got blocked:

1. **Open URL**
2. **Wait 60 seconds**: This long sleep timer ensures that all page content is fully loaded.
3. **Capture Screenshot**: A screenshot of the page is taken after the wait.
4. **Verification**: We manually verified the screenshot to see if the protection was bypassed and target data was loaded.

**Verification Pipeline**  
Since some sites partially load page but block primary content, a simple HTML check isn't enough. We fed all screenshots to an LLM (Gemini 3.1 Pro) asking it to label if the site was accessed properly. Then we manually verified almost 4k images to ensure label is correct.

## Setup & Installation

1. Create a virtual environment and install dependencies.
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Configure environment variables.
   Copy the example environment file and add your provider API keys.
   ```bash
   cp .env.example .env
   ```
   *Edit `.env` to include your necessary credentials for the providers you wish to test.*

## How to Run

To execute tests using the python environment in the `.venv` directory, use the `run_benchmark.py` script.

**Run all providers (generic run):**
```bash
python3 run_benchmark.py
```

**Run specific providers with a custom run name:**
```bash
python3 run_benchmark.py --providers bro,browserbase --run-name "my_custom_eval"
```

### Available Arguments for `run_benchmark.py`:
- `--urls`: Path to the CSV file containing URLs to benchmark (defaults to CFG.DEFAULT_URLS).
- `--run-name`: Name of the run. Overrides the default timestamp-based run name.
- `--results-dir`: Explicit path to the results directory.
- `--providers`: Comma-separated list of providers to evaluate (ie, `bro,browserbase`).
- `--exclude-providers`: Comma-separated list of providers to explicitly exclude from the run.
- `--limit`: Maximum number of URLs to process (e.g. `--limit 50`). If not specified, all URLs are processed.

## Providers Configuration

Below is a breakdown of the features used and the exact JSON configuration passed to each provider during the benchmark.

We deliberately disabled automated CAPTCHA solving to evaluate how these tools passively bypass protections based solely on their underlying browser fingerprint and routing setup. 

> **Note on Open Source Solutions:** If you want to benchmark the open source frameworks (Playwright, Selenium, Obscura), you will need to provide your own proxy endpoint (`CFG.PROXY_CONFIG.endpoint`, `CFG.PROXY_CONFIG.username_template` and `CFG.PROXY_CONFIG.password_template`) and credentials in `.env` (`PROXY_USERNAME` and `PROXY_PASSWORD`). The success rate for these bare engines is highly dependent on the quality of the IP pool used. We used the same proxy network we use in bro.

| Provider | Proxy | Stealth | Captcha Solver |
| --- | --- | --- | --- |
| [bro](https://getbro.ws/) | ✅ | ✅ | ❌ |
| [browserless](https://www.browserless.io/feature/browsers-as-a-service) | ✅ | ✅ | ❌ |
| [browserbase](https://www.browserbase.com/solutions/browser-agents) | ✅ | ✅ | ❌ |
| [browseruse](https://browser-use.com/stealth-browsers) | ✅ | ✅ | ✅ |
| [firecrawl](https://www.firecrawl.dev/interact) | ✅ | ✅ | ❌ |
| [hyperbrowser](https://www.hyperbrowser.ai/browser-sessions) | ✅ | ✅ | ❌ |
| [obscura](https://github.com/h4ckf0r0day/obscura) | ✅ | ✅ | ❌ |
| [playwright](https://github.com/microsoft/playwright) | ✅ | ❌ | ❌ |
| [selenium](https://github.com/seleniumhq/selenium) | ✅ | ❌ | ❌ |

_(browseruse doesn't have option to disable CAPTCHA solver)_

### Configs

<details>
<summary><b>bro</b></summary>

```json
{
    "enable_proxy": true,
    "rotate_proxy": true,
    "proxy_tier": "basic",
    "proxy_policy": "full",
    "country": "US"
}
```
</details>

<details>
<summary><b>browserless</b></summary>

```json
{
    "proxy": "residential",
    "proxySticky": true,
    "proxyLocaleMatch": true,
    "humanlike": true,
    "captcha": false,
    "launch": {
        "headless": true,
        "humanlike": true,
        "blockAds": true,
        "blockConsentModals": true
    }
}
```
</details>

<details>
<summary><b>browserbase</b></summary>

```json
{
    "proxies": true,
    "browserSettings": {
        "blockAds": true,
        "solveCaptchas": false
    }
}
```
</details>

<details>
<summary><b>browseruse</b></summary>

```json
{
    "country": "us",
    "stealth": "service_default",
    "requested_mode": "advanced_stealth",
    "proxy": "browser_use_residential_default"
}
```
</details>

<details>
<summary><b>firecrawl</b></summary>

```json
{
    "mode": "browser_sandbox_cdp",
    "network_location": "service_default",
    "proxy": "basic"
}
```
</details>

<details>
<summary><b>hyperbrowser</b></summary>

```json
{
    "useStealth": true,
    "useUltraStealth": false,
    "useProxy": true,
    "proxyCountry": "US",
    "region": "us",
    "solveCaptchas": false,
    "adblock": true,
    "trackers": true,
    "annoyances": true,
    "acceptCookies": true
}
```
</details>

<details>
<summary><b>obscura</b></summary>

```json
{
    "engine": "obscura",
    "build_features": [
        "render",
        "stealth"
    ],
    "stealth": true,
    "use_proxy": true
}
```
</details>

<details>
<summary><b>playwright</b></summary>

```json
{
    "use_proxy": true
}
```
</details>

<details>
<summary><b>selenium</b></summary>

```json
{
    "use_proxy": true
}
```
</details>
