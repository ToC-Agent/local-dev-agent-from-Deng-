"""工具协议：schema + execute + permission + timeout + result。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

Permission = Literal["allow", "deny"]

MAX_RESULT_CHARS = 16_000

ToolHandler = Callable[[Path, dict[str, Any]], "ToolOutcome"]
PermissionFn = Callable[[Path, dict[str, Any]], Permission]


@dataclass
class ToolOutcome:
    ok: bool
    content: str
    extra: dict[str, Any] = field(default_factory=dict)

    def truncated(self, limit: int = MAX_RESULT_CHARS) -> ToolOutcome:
        if len(self.content) <= limit:
            return self
        head = self.content[:limit]
        note = f"\n\n[truncated] 输出过长，已截到 {limit} 字符 / 原 {len(self.content)} 字符。"
        return ToolOutcome(ok=self.ok, content=head + note, extra=self.extra)


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    execute: ToolHandler
    timeout: float
    permission: PermissionFn | None = None

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
