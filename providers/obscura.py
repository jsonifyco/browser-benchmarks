from typing import Any
from .core import DockerAdapter, RunContext

class ObscuraAdapter(DockerAdapter):
    def __init__(self, source: str, source_config: dict[str, Any]) -> None:
        super().__init__(source, source_config)

    def capture(self, ctx: RunContext, url: str, index: int, attempt: int) -> dict[str, Any]:
        return super().capture(ctx, url, index, attempt)