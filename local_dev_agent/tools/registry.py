"""Tool Registry：工具不写死在 prompt 里，由注册表提供 schema 与执行。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Any

from local_dev_agent.tools.base import Permission, ToolOutcome, ToolSpec
from local_dev_agent.tools.files import file_tool_specs
from local_dev_agent.tools.sandbox import WorkspaceError
from local_dev_agent.tools.shell import shell_tool_specs


class ToolRegistry:
    def __init__(self, tools: list[ToolSpec] | None = None) -> None:
        self._tools: dict[str, ToolSpec] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: ToolSpec) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def openai_tools(self) -> list[dict[str, Any]]:
        return [tool.openai_schema() for tool in self._tools.values()]

    def check_permission(self, name: str, workspace: Path, args: dict[str, Any]) -> Permission:
        tool = self._tools.get(name)
        if tool is None:
            return "deny"
        if tool.permission is None:
            return "allow"
        return tool.permission(workspace, args)

    def execute(
        self,
        name: str,
        workspace: Path,
        args: dict[str, Any],
        timeout: float | None = None,
    ) -> ToolOutcome:
        tool = self._tools.get(name)
        if tool is None:
            return ToolOutcome(ok=False, content=f"未知工具: {name}")
        limit = timeout if timeout is not None else tool.timeout
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(tool.execute, workspace, args)
                outcome = future.result(timeout=limit)
        except WorkspaceError as exc:
            raise
        except FuturesTimeout:
            return ToolOutcome(ok=False, content=f"工具 {name} 超时（{int(limit)}s）")
        except Exception as exc:  # 单工具异常不应打崩整轮
            return ToolOutcome(ok=False, content=f"工具 {name} 异常: {type(exc).__name__}: {exc}")
        return outcome.truncated()


def build_default_registry() -> ToolRegistry:
    return ToolRegistry(file_tool_specs() + shell_tool_specs())
