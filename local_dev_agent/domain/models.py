"""M1 领域模型：Thread / Turn / Item。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Union
from uuid import uuid4


def new_id() -> str:
    return uuid4().hex[:12]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class UserMessage:
    content: str
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    kind: Literal["user_message"] = "user_message"


@dataclass
class AgentMessage:
    content: str
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    kind: Literal["agent_message"] = "agent_message"


@dataclass
class Reasoning:
    content: str
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    kind: Literal["reasoning"] = "reasoning"


@dataclass
class ToolCall:
    tool_name: str
    arguments: dict
    tool_call_id: str
    raw_arguments: str = ""
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    kind: Literal["tool_call"] = "tool_call"


@dataclass
class ToolResult:
    tool_name: str
    tool_call_id: str
    content: str
    ok: bool = True
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    kind: Literal["tool_result"] = "tool_result"


@dataclass
class CommandExecution:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    kind: Literal["command_execution"] = "command_execution"


@dataclass
class FileChange:
    path: str
    action: str
    summary: str = ""
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    kind: Literal["file_change"] = "file_change"


@dataclass
class ApprovalRequest:
    """本阶段不弹窗：越出工作区直接 deny，并记一条 Item。"""

    reason: str
    requested: str
    approved: bool = False
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    kind: Literal["approval_request"] = "approval_request"


@dataclass
class ErrorItem:
    message: str
    detail: str = ""
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    kind: Literal["error"] = "error"


Item = Union[
    UserMessage,
    AgentMessage,
    Reasoning,
    ToolCall,
    ToolResult,
    CommandExecution,
    FileChange,
    ApprovalRequest,
    ErrorItem,
]


@dataclass
class Turn:
    user_task: str
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    status: Literal["running", "completed", "cancelled", "failed"] = "running"
    items: list[Item] = field(default_factory=list)

    def add(self, item: Item) -> Item:
        self.items.append(item)
        return item


@dataclass
class Thread:
    workspace_root: Path
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    turns: list[Turn] = field(default_factory=list)

    def add_turn(self, user_task: str) -> Turn:
        turn = Turn(user_task=user_task)
        self.turns.append(turn)
        return turn
