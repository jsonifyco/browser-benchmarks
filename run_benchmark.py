import csv
import sys
import time
import json
import random
import argparse
from datetime import datetime
from typing import Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from providers import make_adapter, Adapter, RunContext
from config import CFG


def load_urls(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or "url" not in reader.fieldnames:
            raise RuntimeError(f"'url' column not found in {path}")
        return [row["url"].strip() for row in reader if row.get("url", "").strip()]


def run_with_retries(adapter: Adapter, ctx: RunContext, url: str, index: int, retry_attempts: int, retry_backoff_seconds: float) -> dict[str, Any]:
    started = time.time()
    last_error = ""
    for attempt in range(1, retry_attempts + 1):
        try:
            captured = adapter.capture(ctx, url, index, attempt)
            local_path = captured.get("local_path")
            if not local_path:
                raise RuntimeError("missing local_path")
            return {
                "url": url,
                "index": index,
                "provider": adapter.source,
                "status": "ok",
                "local_path": local_path,
                "attempts": attempt,
                "seconds": round(time.time() - started, 2),
                "error": "",
                "session_id": captured.get("session_id", ""),
            }
        except Exception as exc:
            last_error = str(exc)[:2000]
            if attempt < retry_attempts:
                time.sleep(retry_backoff_seconds)

    return {
        "url": url,
        "index": index,
        "provider": adapter.source,
        "status": "error",
        "local_path": "",
        "attempts": retry_attempts,
        "seconds": round(time.time() - started, 2),
        "error": last_error,
        "session_id": "",
    }


def run_provider(provider: str, ctx: RunContext, retry_attempts: int, retry_backoff_seconds: float) -> list[dict[str, Any]]:
    adapter = make_adapter(provider)
    if hasattr(adapter, "setup"):
        adapter.setup()

    workers = int(adapter.config.get("workers", 1))
    
    results: list[dict[str, Any] | None] = [None] * len(ctx.urls)
    
    report_path = ctx.reports_dir / f"{provider}.json"
    existing_results_by_url = {}
    if report_path.exists():
        try:
            prev_data = json.loads(report_path.read_text(encoding="utf-8"))
            for item in prev_data:
                if item and item.get("status") == "ok" and item.get("url"):
                    existing_results_by_url[item["url"]] = item
        except Exception:
            pass

    for i, url in enumerate(ctx.urls):
        if url in existing_results_by_url:
            item = dict(existing_results_by_url[url])
            item["index"] = i + 1
            results[i] = item

    urls_to_run = sum(1 for r in results if r is None)
    actual_workers = min(workers, urls_to_run)
    done_count = len(ctx.urls) - urls_to_run

    print(f"[{provider}] Starting with {actual_workers} workers for {len(ctx.urls)} URLs ({done_count} already done)", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, actual_workers)) as executor:
        future_map = {}
        for index, url in enumerate(ctx.urls, start=1):
            if results[index - 1] is not None:
                continue
            future = executor.submit(run_with_retries, adapter, ctx, url, index, retry_attempts, retry_backoff_seconds)
            future_map[future] = (index, url)
        for future in as_completed(future_map):
            index, url = future_map[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {
                    "url": url,
                    "index": index,
                    "provider": provider,
                    "status": "error",
                    "local_path": "",
                    "attempts": 0,
                    "seconds": 0,
                    "error": f"Internal execution error: {exc}",
                    "session_id": "",
                }
            results[index - 1] = result
            label = "OK" if result["status"] == "ok" else "ERR"
            detail = result["local_path"] if label == "OK" else result.get("error", "")
            print(f"[{provider}] [{index:03d}/{len(ctx.urls):03d}] {label} {url} {detail[:240]}", flush=True)

    # Convert Nones to error objects just in case any futures didn't resolve
    for idx in range(len(results)):
        if results[idx] is None:
            results[idx] = {
                "url": ctx.urls[idx],
                "index": idx + 1,
                "provider": provider,
                "status": "error",
                "local_path": "",
                "attempts": 0,
                "seconds": 0,
                "error": "Unknown missing result",
                "session_id": "",
            }

    ctx.reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = ctx.reports_dir / f"{provider}.json"
    report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run simple screenshot benchmark.")
    parser.add_argument("--urls", type=Path, default=CFG.DEFAULT_URLS)
    parser.add_argument("--run-name", type=str, default="", help="Name of the run. If provided, overrides default timestamp.")
    parser.add_argument("--results-dir", type=Path, default=None, help="Explicit path to results directory.")
    parser.add_argument("--providers", default=",".join(CFG.DEFAULT_PROVIDERS))
    parser.add_argument("--exclude-providers", default="")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of URLs to process. Processes all if not specified.")
    args = parser.parse_args(argv)

    urls = load_urls(args.urls)
    if args.limit is not None and args.limit > 0:
        urls = urls[:args.limit]
        
    requested_providers = [p.strip().lower() for p in args.providers.split(",") if p.strip()]
    invalid = [p for p in requested_providers if p not in CFG.PROVIDERS]
    if invalid:
        raise RuntimeError(f"Unsupported providers: {', '.join(invalid)}")

    excludes = [p.strip().lower() for p in args.exclude_providers.split(",") if p.strip()]
    providers = [p for p in requested_providers if p not in excludes]
    if not providers:
        raise RuntimeError("No providers selected")

    if args.results_dir is None:
        if args.run_name:
            args.results_dir = Path(CFG.DEFAULT_RESULTS_DIR).parent / args.run_name
        else:
            default_run_name = datetime.now().strftime("run_%Y%m%d_%H%M%S")
            args.results_dir = Path(CFG.DEFAULT_RESULTS_DIR).parent / default_run_name

    args.results_dir.mkdir(parents=True, exist_ok=True)
    ctx = RunContext(
        urls=urls,
        results_dir=args.results_dir,
        run_id=args.results_dir.name,
    )

    all_provider_results = {}
    
    # Run providers sequentially to prevent cross-provider resource contention (like Docker CPU usage).
    # Concurrency is handled internally per-provider over the URLs.
    for provider in providers:
        try:
            results = run_provider(provider, ctx, int(CFG.COMMON.retry_attempts), float(CFG.COMMON.retry_backoff_seconds))
            all_provider_results[provider] = results
        except Exception as exc:
            print(f"[{provider}] SOURCE_ERR {exc}", flush=True)
            all_provider_results[provider] = []

    # Write combined CSV
    csv_path = ctx.results_dir / "results.csv"
    
    existing_rows = {}
    existing_fieldnames = ["url"]
    
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames:
                existing_fieldnames = list(reader.fieldnames)
            for row in reader:
                if row.get("url"):
                    existing_rows[row["url"]] = row

    for provider in providers:
        if provider not in existing_fieldnames:
            existing_fieldnames.append(provider)

    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=existing_fieldnames)
        writer.writeheader()
        
        for index, url in enumerate(urls, start=1):
            row = existing_rows.get(url, {"url": url}).copy()
            for provider in providers:
                provider_results = all_provider_results.get(provider, [])
                item = provider_results[index - 1] if index - 1 < len(provider_results) else None
                if item and item.get("status") == "ok":
                    row[provider] = item.get("local_path", "")
                else:
                    row[provider] = ""
            writer.writerow(row)
            
    print(f"Benchmark finished. Results saved to {args.results_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
