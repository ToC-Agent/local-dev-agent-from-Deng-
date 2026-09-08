"""阿里云百炼 OpenAI 兼容口。HTTP 必须用 httpx 且 trust_env=False。"""

from __future__ import annotations

import json
from typing import Any, Iterator

import httpx

from local_dev_agent.gateway.provider import (
    ChatMessage,
    ModelEvent,
    ModelResponse,
    ToolCallRequest,
    Usage,
)

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-plus"


def estimate_tokens(text: str) -> int:
    """第一版估算：中英混合按约 2 字符/token。"""
    if not text:
        return 0
    return max(1, (len(text) + 1) // 2)


def _message_to_payload(message: ChatMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role}
    if message.tool_call_id:
        payload["tool_call_id"] = message.tool_call_id
    if message.name:
        payload["name"] = message.name
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": tc.arguments},
            }
            for tc in message.tool_calls
        ]
        payload["content"] = message.content or ""
    else:
        payload["content"] = message.content if message.content is not None else ""
    return payload


def _parse_usage(data: dict[str, Any] | None) -> Usage:
    if not data:
        return Usage()
    return Usage(
        prompt_tokens=int(data.get("prompt_tokens") or 0),
        completion_tokens=int(data.get("completion_tokens") or 0),
        total_tokens=int(data.get("total_tokens") or 0),
    )


def _parse_tool_calls(raw: list[dict[str, Any]] | None) -> list[ToolCallRequest]:
    calls: list[ToolCallRequest] = []
    if not raw:
        return calls
    for item in raw:
        fn = item.get("function") or {}
        calls.append(
            ToolCallRequest(
                id=str(item.get("id") or ""),
                name=str(fn.get("name") or ""),
                arguments=str(fn.get("arguments") or ""),
            )
        )
    return calls


class BailianProvider:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = 120.0,
    ) -> None:
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY 为空")
        self.model = model
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout),
            trust_env=False,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> BailianProvider:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def count_tokens(self, text: str) -> int:
        return estimate_tokens(text)

    def compact(
        self,
        messages: list[ChatMessage],
        max_tokens: int,
    ) -> list[ChatMessage]:
        """保留 system + 最近消息，中间过长则截断。"""
        if not messages:
            return []
        if self._messages_tokens(messages) <= max_tokens:
            return list(messages)

        system = [m for m in messages if m.role == "system"][:1]
        rest = [m for m in messages if m.role != "system"]
        kept: list[ChatMessage] = []
        for message in reversed(rest):
            trial = system + list(reversed(kept + [message]))
            if self._messages_tokens(trial) > max_tokens and kept:
                break
            kept.append(message)
        kept.reverse()
        if len(kept) < len(rest):
            note = ChatMessage(
                role="system",
                content="[compact] 更早的对话已截断，请根据最近工具结果继续。",
            )
            return system + [note] + kept
        return system + kept

    def complete(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> ModelResponse:
        body = self._request_body(messages, tools, stream=False)
        response = self._client.post("/chat/completions", json=body)
        response.raise_for_status()
        data = response.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return ModelResponse(
            text=str(message.get("content") or ""),
            reasoning=str(
                message.get("reasoning_content")
                or message.get("reasoning")
                or ""
            ),
            tool_calls=_parse_tool_calls(message.get("tool_calls")),
            usage=_parse_usage(data.get("usage")),
            finish_reason=str(choice.get("finish_reason") or ""),
        )

    def stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> Iterator[ModelEvent]:
        body = self._request_body(messages, tools, stream=True)
        acc: dict[int, dict[str, str]] = {}
        with self._client.stream("POST", "/chat/completions", json=body) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    line = line[5:].strip()
                if line == "[DONE]":
                    break
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                usage_raw = chunk.get("usage")
                if usage_raw:
                    yield ModelEvent(kind="usage", usage=_parse_usage(usage_raw))
                choice = (chunk.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                finish = str(choice.get("finish_reason") or "")
                text = delta.get("content")
                if text:
                    yield ModelEvent(kind="text", text=str(text))
                reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                if reasoning:
                    yield ModelEvent(kind="reasoning", text=str(reasoning))
                for tc in delta.get("tool_calls") or []:
                    idx = int(tc.get("index") or 0)
                    slot = acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if tc.get("id"):
                        slot["id"] = str(tc["id"])
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["name"] += str(fn["name"])
                    if fn.get("arguments"):
                        slot["arguments"] += str(fn["arguments"])
                if finish:
                    calls = [
                        ToolCallRequest(
                            id=slot["id"] or f"call_{idx}",
                            name=slot["name"],
                            arguments=slot["arguments"],
                        )
                        for idx, slot in sorted(acc.items())
                        if slot["name"]
                    ]
                    if calls:
                        yield ModelEvent(kind="tool_calls", tool_calls=calls)
                    yield ModelEvent(kind="finish", finish_reason=finish)

    def _messages_tokens(self, messages: list[ChatMessage]) -> int:
        blob = json.dumps(
            [_message_to_payload(m) for m in messages],
            ensure_ascii=False,
        )
        return self.count_tokens(blob)

    def _request_body(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None,
        stream: bool,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [_message_to_payload(m) for m in messages],
            "stream": stream,
            "temperature": 0.2,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if stream:
            body["stream_options"] = {"include_usage": True}
        return body
