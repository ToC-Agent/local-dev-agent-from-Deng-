"""从第一天就向外打印 Item，不要整轮结束才输出。"""

from __future__ import annotations

from local_dev_agent.domain.models import (
    AgentMessage,
    ApprovalRequest,
    CommandExecution,
    ErrorItem,
    FileChange,
    Item,
    Reasoning,
    ToolCall,
    ToolResult,
    UserMessage,
)


def format_item(item: Item) -> str:
    if isinstance(item, UserMessage):
        return f"[user] {item.content}"
    if isinstance(item, AgentMessage):
        return f"[final] {item.content}"
    if isinstance(item, Reasoning):
        return f"[reasoning] {item.content}"
    if isinstance(item, ToolCall):
        return f"[tool started] {item.tool_name} {item.arguments}"
    if isinstance(item, ToolResult):
        status = "ok" if item.ok else "fail"
        return f"[tool result] {item.tool_name} {status}\n{item.content}"
    if isinstance(item, CommandExecution):
        return f"[command] exit={item.exit_code} {item.command}"
    if isinstance(item, FileChange):
        return f"[file_change] {item.action} {item.path} {item.summary}".rstrip()
    if isinstance(item, ApprovalRequest):
        decision = "allow" if item.approved else "deny"
        return f"[approval] {decision} {item.reason} ({item.requested})"
    if isinstance(item, ErrorItem):
        extra = f" {item.detail}" if item.detail else ""
        return f"[error] {item.message}{extra}"
    return f"[item] {item}"


def emit(item: Item) -> None:
    print(format_item(item), flush=True)
