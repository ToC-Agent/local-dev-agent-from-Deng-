"""shell_exec / git_diff。cwd 固定为 workspace_root；Windows 用 PowerShell。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from local_dev_agent.tools.base import ToolOutcome, ToolSpec
from local_dev_agent.tools.sandbox import WorkspaceError, resolve_in_workspace

SHELL_TIMEOUT = 60.0
GIT_TIMEOUT = 30.0


def _shell_env() -> dict[str, str]:
    env = os.environ.copy()
    scripts = str(Path(sys.executable).resolve().parent)
    env["PATH"] = scripts + os.pathsep + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def _run_powershell(workspace: Path, command: str, timeout: float) -> subprocess.CompletedProcess[str]:
    prefix = (
        "$ErrorActionPreference='Continue'; "
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "$OutputEncoding = [Console]::OutputEncoding; "
    )
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            prefix + command,
        ],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=creationflags,
        env=_shell_env(),
    )


def _format_process(command: str, proc: subprocess.CompletedProcess[str]) -> str:
    parts = [
        f"$ {command}",
        f"exit_code={proc.returncode}",
    ]
    if proc.stdout:
        parts.append("--- stdout ---")
        parts.append(proc.stdout.rstrip())
    if proc.stderr:
        parts.append("--- stderr ---")
        parts.append(proc.stderr.rstrip())
    return "\n".join(parts)


def execute_shell_exec(workspace: Path, args: dict[str, Any]) -> ToolOutcome:
    command = str(args.get("command") or "").strip()
    if not command:
        return ToolOutcome(ok=False, content="缺少 command")
    try:
        proc = _run_powershell(workspace, command, timeout=SHELL_TIMEOUT)
    except subprocess.TimeoutExpired:
        return ToolOutcome(ok=False, content=f"命令超时（{int(SHELL_TIMEOUT)}s）: {command}")
    except OSError as exc:
        return ToolOutcome(ok=False, content=f"无法启动 PowerShell: {exc}")
    return ToolOutcome(
        ok=proc.returncode == 0,
        content=_format_process(command, proc),
        extra={
            "command_execution": {
                "command": command,
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        },
    )


def execute_git_diff(workspace: Path, args: dict[str, Any]) -> ToolOutcome:
    target = str(args.get("path") or "").strip()
    command = "git diff --no-color"
    if target:
        try:
            resolve_in_workspace(workspace, target)
        except WorkspaceError:
            raise
        command += f" -- {target}"
    try:
        diff_proc = _run_powershell(workspace, command, timeout=GIT_TIMEOUT)
        status_proc = _run_powershell(
            workspace, "git status --short", timeout=GIT_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        return ToolOutcome(ok=False, content="git 命令超时")
    except OSError as exc:
        return ToolOutcome(ok=False, content=f"无法启动 PowerShell: {exc}")

    chunks = [
        "=== git status --short ===",
        status_proc.stdout.rstrip() or "(clean)",
        "",
        "=== git diff ===",
        diff_proc.stdout.rstrip() or "(no diff)",
    ]
    if status_proc.stderr.strip():
        chunks.extend(["", "status stderr:", status_proc.stderr.rstrip()])
    if diff_proc.stderr.strip():
        chunks.extend(["", "diff stderr:", diff_proc.stderr.rstrip()])
    ok = status_proc.returncode == 0 or diff_proc.returncode == 0
    return ToolOutcome(ok=ok, content="\n".join(chunks))


def shell_tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="shell_exec",
            description=(
                "在 workspace 根目录用 PowerShell 执行命令。"
                "默认用来跑 pytest / python / git。不要 cd 到工作区外。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "PowerShell 命令"},
                },
                "required": ["command"],
            },
            execute=execute_shell_exec,
            timeout=SHELL_TIMEOUT,
        ),
        ToolSpec(
            name="git_diff",
            description="查看工作区 git status 与 git diff。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "可选，限制到某个相对路径"},
                },
            },
            execute=execute_git_diff,
            timeout=GIT_TIMEOUT,
        ),
    ]
