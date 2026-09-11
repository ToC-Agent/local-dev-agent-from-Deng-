"""M4 Agent Loop：构造上下文 → 模型 → 工具 → 写回 → 直到 final。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from local_dev_agent.domain.models import (
    AgentMessage,
    ApprovalRequest,
    CommandExecution,
    ErrorItem,
    FileChange,
    Item,
    Reasoning,
    Thread,
    ToolCall,
    ToolResult,
    Turn,
    UserMessage,
    new_id,
)
from local_dev_agent.gateway.provider import ChatMessage, ModelProvider, ModelResponse
from local_dev_agent.harness.system_prompt import SYSTEM_PROMPT
from local_dev_agent.loop.printer import emit
from local_dev_agent.tools.registry import ToolRegistry
from local_dev_agent.tools.sandbox import WorkspaceError

CONTEXT_TOKEN_LIMIT = 24_000


class AgentLoop:
    def __init__(
        self,
        provider: ModelProvider,
        registry: ToolRegistry,
        workspace_root: Path,
        max_steps: int = 20,
        print_items: bool = True,
    ) -> None:
        self.provider = provider
        self.registry = registry
        self.workspace_root = workspace_root.expanduser().resolve()
        self.max_steps = max_steps
        self.print_items = print_items
        self.thread = Thread(workspace_root=self.workspace_root)

    def run(self, task: str) -> Turn:
        turn = self.thread.add_turn(task)
        self._add(turn, UserMessage(content=task))
        try:
            for step in range(self.max_steps):
                messages = self.provider.compact(
                    self._build_messages(turn),
                    CONTEXT_TOKEN_LIMIT,
                )
                try:
                    response = self.provider.complete(
                        messages,
                        tools=self.registry.openai_tools(),
                    )
                except KeyboardInterrupt:
                    self._add(turn, ErrorItem(message="用户取消（Ctrl+C）"))
                    turn.status = "cancelled"
                    return turn
                except Exception as exc:
                    detail = f"{type(exc).__name__}: {exc}"
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    if status == 401:
                        detail += (
                            "。模型通道返回 401：Key 无效或未带对请求头。"
                            "中台请核对 ZHONGTAI_API_KEY（X-API-Key）；百炼请核对 DASHSCOPE_API_KEY。"
                        )
                    self._add(
                        turn,
                        ErrorItem(
                            message="模型调用失败",
                            detail=detail,
                        ),
                    )
                    turn.status = "failed"
                    return turn

                if response.reasoning:
                    self._add(turn, Reasoning(content=response.reasoning))

                if response.tool_calls:
                    self._run_tool_calls(turn, response)
                    continue

                text = (response.text or "").strip()
                if text:
                    self._add(turn, AgentMessage(content=text))
                    turn.status = "completed"
                    return turn

                self._add(
                    turn,
                    ErrorItem(message="模型返回空内容，继续下一步", detail=f"step={step}"),
                )

            self._add(turn, ErrorItem(message=f"达到 max_steps={self.max_steps}，停止"))
            turn.status = "failed"
            return turn
        except KeyboardInterrupt:
            self._add(turn, ErrorItem(message="用户取消（Ctrl+C）"))
            turn.status = "cancelled"
            return turn

    def _add(self, turn: Turn, item: Item) -> Item:
        turn.add(item)
        if self.print_items:
            emit(item)
        return item

    def _run_tool_calls(self, turn: Turn, response: ModelResponse) -> None:
        prepared: list[tuple[str, str, dict[str, Any]]] = []
        for call in response.tool_calls:
            call_id = call.id or new_id()
            raw = call.arguments or ""
            try:
                parsed = json.loads(raw) if raw.strip() else {}
                if not isinstance(parsed, dict):
                    raise ValueError("工具参数必须是 JSON 对象")
            except (json.JSONDecodeError, ValueError) as exc:
                self._add(
                    turn,
                    ToolCall(
                        tool_name=call.name,
                        arguments={},
                        tool_call_id=call_id,
                        raw_arguments=raw,
                    ),
                )
                self._add(
                    turn,
                    ErrorItem(message="工具参数 JSON 无效，已跳过该次调用", detail=str(exc)),
                )
                self._add(
                    turn,
                    ToolResult(
                        tool_name=call.name,
                        tool_call_id=call_id,
                        content=f"参数不是合法 JSON 对象: {exc}\nraw={raw[:500]}",
                        ok=False,
                    ),
                )
                continue

            self._add(
                turn,
                ToolCall(
                    tool_name=call.name,
                    arguments=parsed,
                    tool_call_id=call_id,
                    raw_arguments=raw,
                ),
            )
            prepared.append((call.name, call_id, parsed))

        for name, call_id, parsed in prepared:
            self._execute_one(turn, name, call_id, parsed)

    def _execute_one(
        self,
        turn: Turn,
        name: str,
        call_id: str,
        args: dict[str, Any],
    ) -> None:
        if self.registry.get(name) is None:
            self._add(
                turn,
                ToolResult(
                    tool_name=name,
                    tool_call_id=call_id,
                    content=f"未知工具: {name}",
                    ok=False,
                ),
            )
            return

        if self.registry.check_permission(name, self.workspace_root, args) == "deny":
            denied = ApprovalRequest(
                reason="权限检查拒绝",
                requested=name,
                approved=False,
            )
            self._add(turn, denied)
            self._add(
                turn,
                ToolResult(
                    tool_name=name,
                    tool_call_id=call_id,
                    content="权限拒绝",
                    ok=False,
                ),
            )
            return

        try:
            outcome = self.registry.execute(name, self.workspace_root, args)
        except WorkspaceError as exc:
            self._add(
                turn,
                ApprovalRequest(
                    reason=str(exc),
                    requested=exc.requested,
                    approved=False,
                ),
            )
            self._add(
                turn,
                ToolResult(
                    tool_name=name,
                    tool_call_id=call_id,
                    content=str(exc),
                    ok=False,
                ),
            )
            return
        except Exception as exc:
            self._add(
                turn,
                ErrorItem(message=f"工具 {name} 未捕获异常", detail=str(exc)),
            )
            self._add(
                turn,
                ToolResult(
                    tool_name=name,
                    tool_call_id=call_id,
                    content=f"异常: {exc}",
                    ok=False,
                ),
            )
            return

        extra = outcome.extra or {}
        change = extra.get("file_change")
        if change:
            self._add(
                turn,
                FileChange(
                    path=str(change.get("path") or ""),
                    action=str(change.get("action") or "updated"),
                    summary=outcome.content,
                ),
            )
        command = extra.get("command_execution")
        if command:
            self._add(
                turn,
                CommandExecution(
                    command=str(command.get("command") or ""),
                    exit_code=int(command.get("exit_code") or 0),
                    stdout=str(command.get("stdout") or ""),
                    stderr=str(command.get("stderr") or ""),
                ),
            )
        self._add(
            turn,
            ToolResult(
                tool_name=name,
                tool_call_id=call_id,
                content=outcome.content,
                ok=outcome.ok,
            ),
        )

    def _build_messages(self, turn: Turn) -> list[ChatMessage]:
        messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
        pending_calls: list[ToolCall] = []
        for item in turn.items:
            if isinstance(item, UserMessage):
                messages.append(ChatMessage(role="user", content=item.content))
            elif isinstance(item, AgentMessage):
                messages.append(ChatMessage(role="assistant", content=item.content))
            elif isinstance(item, ToolCall):
                pending_calls.append(item)
            elif isinstance(item, ToolResult):
                if pending_calls:
                    messages.append(
                        ChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                _to_request(call) for call in pending_calls
                            ],
                        )
                    )
                    pending_calls = []
                messages.append(
                    ChatMessage(
                        role="tool",
                        content=item.content,
                        tool_call_id=item.tool_call_id,
                        name=item.tool_name,
                    )
                )
        if pending_calls:
            messages.append(
                ChatMessage(
                    role="assistant",
                    content="",
                    tool_calls=[_to_request(call) for call in pending_calls],
                )
            )
        return messages


def _to_request(call: ToolCall):
    from local_dev_agent.gateway.provider import ToolCallRequest

    return ToolCallRequest(
        id=call.tool_call_id,
        name=call.tool_name,
        arguments=call.raw_arguments or json.dumps(call.arguments, ensure_ascii=False),
    )
