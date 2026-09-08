"""M2 Model Gateway 接口。第一家只接百炼。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Protocol


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: str


@dataclass
class ChatMessage:
    role: str
    content: str | None = None
    tool_call_id: str | None = None
    name: str | None = None
    tool_calls: list[ToolCallRequest] | None = None


@dataclass
class ModelResponse:
    text: str = ""
    reasoning: str = ""
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    finish_reason: str = ""


@dataclass
class ModelEvent:
    """stream() 的增量事件。kind: text / reasoning / tool_calls / usage / finish"""

    kind: str
    text: str = ""
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    usage: Usage | None = None
    finish_reason: str = ""


class ModelProvider(Protocol):
    def stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> Iterator[ModelEvent]: ...

    def complete(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> ModelResponse: ...

    def count_tokens(self, text: str) -> int: ...

    def compact(
        self,
        messages: list[ChatMessage],
        max_tokens: int,
    ) -> list[ChatMessage]: ...
