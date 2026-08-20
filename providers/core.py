import base64
import re
import json
import subprocess
import tempfile
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from config import CFG


def slugify(url: str, index: int) -> str:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc or "no-host"
    path = parsed.path.strip("/") or "home"
    raw = f"{index:03d}_{host}_{path}"
    if parsed.query:
        raw += "_" + parsed.query[:60]
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._")
    return safe[:180] + ".png"


def capture_cdp_or_playwright_screenshot(page: Any, context: Any) -> bytes:
    try:
        client = context.new_cdp_session(page)
        screenshot = client.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
        return base64.b64decode(screenshot["data"])
    except Exception:
        pass
    try:
        return page.screenshot(full_page=True, type="png")
    except Exception:
        return page.screenshot(full_page=False, type="png")


@dataclass
class RunContext:
    urls: list[str]
    results_dir: Path
    run_id: str

    @property
    def reports_dir(self) -> Path:
        return self.results_dir / "reports"

    @property
    def tmp_dir(self) -> Path:
        return self.results_dir / "tmp"

    @property
    def screenshots_dir(self) -> Path:
        return self.results_dir / "screenshots"


class Adapter:
    def __init__(self, source: str, source_config: dict[str, Any]) -> None:
        self.source = source
        self.config = {}
        if hasattr(CFG, "COMMON"):
            self.config.update(CFG.COMMON)
        self.config.update(source_config)

    def screenshot_path(self, ctx: RunContext, url: str, index: int) -> Path:
        return ctx.screenshots_dir / self.source / slugify(url, index)

    def capture(self, ctx: RunContext, url: str, index: int, attempt: int) -> dict[str, Any]:
        raise NotImplementedError


class DockerAdapter(Adapter):
    def run_local(self, cmd: list[str], timeout: float | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def docker_build_args(self) -> list[str]:
        args: list[str] = []
        for key, value in self.config.get("docker_build_args", {}).items():
            args.extend(["--build-arg", f"{key}={value}"])
        return args

    def setup(self) -> None:
        image = self.config["docker_image"]
        inspect = self.run_local(["docker", "image", "inspect", image])
        if inspect.returncode != 0:
            if not self.config.get("auto_build_docker"):
                raise RuntimeError(f"Docker image not found: {image}")
                
            dockerfile_dir = Path(__file__).parent / "docker" / self.source
            if dockerfile_dir.exists():
                self.config["dockerfile_dir"] = dockerfile_dir
            elif hasattr(self, "get_docker_files"):
                # Fallback for dynamic strings if needed
                dockerfile_dir = Path(tempfile.gettempdir()) / f"docker_build_{self.source}"
                dockerfile_dir.mkdir(parents=True, exist_ok=True)
                for filename, content in self.get_docker_files().items():
                    (dockerfile_dir / filename).write_text(content, encoding="utf-8")
                self.config["dockerfile_dir"] = dockerfile_dir

            build = self.run_local(
                [
                    "docker",
                    "build",
                    "-t",
                    image,
                    *self.docker_build_args(),
                    str(self.config["dockerfile_dir"]),
                ]
            )
            if build.returncode != 0:
                raise RuntimeError(f"Docker build failed: {build.stdout[-1000:]} {build.stderr[-1000:]}")

    def capture(self, ctx: RunContext, url: str, index: int, attempt: int) -> dict[str, Any]:
        started = time.time()
        
        timeout_sec = (self.config.get("page_timeout_ms", 60000) + self.config.get("wait_after_load_ms", 3000)) / 1000.0 + 30.0

        docker_args = [
            "docker",
            "run",
            "--rm",
            self.config["docker_image"],
            url,
            str(index),
            json.dumps(dict(self.config), default=str)
        ]
        
        try:
            run = self.run_local(docker_args, timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"docker runner timed out after {timeout_sec}s")

        if run.returncode != 0:
            raise RuntimeError(f"docker runner failed (code {run.returncode}): {run.stdout[-500:]} {run.stderr[-500:]}")
            
        out_lines = [line.strip() for line in run.stdout.strip().split("\n") if line.strip().startswith("{")]
        if not out_lines:
            raise RuntimeError(f"docker runner produced no json output: {run.stdout[-500:]} {run.stderr[-500:]}")
            
        try:
            result = json.loads(out_lines[-1])
        except json.JSONDecodeError:
            raise RuntimeError(f"Failed to parse docker output: {out_lines[-1]}")
            
        if result.get("status") != "ok":
            raise RuntimeError(result.get("error", "Unknown error inside docker"))
            
        png_data = base64.b64decode(result["screenshot"])
        if not png_data:
            raise RuntimeError("docker screenshot missing or empty")

        local_file = self.screenshot_path(ctx, url, index)
        local_file.parent.mkdir(parents=True, exist_ok=True)
        local_file.write_bytes(png_data)
        
        local_path = str(local_file.resolve())
        
        return {
            "local_path": local_path,
            "session_id": "",
            "seconds": round(time.time() - started, 2),
        }

