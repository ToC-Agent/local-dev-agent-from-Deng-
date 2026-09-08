"""文件类工具：read / write / apply_patch / list / search。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from local_dev_agent.tools.base import ToolOutcome, ToolSpec
from local_dev_agent.tools.sandbox import resolve_in_workspace

SKIP_DIR_NAMES = {".git", ".venv", "venv", "__pycache__", ".local_dev_agent", ".pytest_cache"}
MAX_LIST_ENTRIES = 500
MAX_SEARCH_HITS = 50


def _detect_newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="")


def execute_read_file(workspace: Path, args: dict[str, Any]) -> ToolOutcome:
    path = resolve_in_workspace(workspace, str(args.get("path") or ""))
    if not path.is_file():
        return ToolOutcome(ok=False, content=f"文件不存在: {path}")
    text = _read_text(path)
    rel = path.relative_to(workspace.resolve())
    return ToolOutcome(ok=True, content=f"{rel.as_posix()}\n\n{text}")


def execute_write_file(workspace: Path, args: dict[str, Any]) -> ToolOutcome:
    path = resolve_in_workspace(workspace, str(args.get("path") or ""))
    content = args.get("content")
    if content is None:
        return ToolOutcome(ok=False, content="缺少 content")
    existed = path.exists()
    _write_text(path, str(content))
    rel = path.relative_to(workspace.resolve())
    action = "updated" if existed else "created"
    return ToolOutcome(
        ok=True,
        content=f"{action} {rel.as_posix()} ({len(str(content))} chars)",
        extra={"file_change": {"path": rel.as_posix(), "action": action}},
    )


def execute_apply_patch(workspace: Path, args: dict[str, Any]) -> ToolOutcome:
    path = resolve_in_workspace(workspace, str(args.get("path") or ""))
    old_text = args.get("old_text")
    new_text = args.get("new_text")
    if not isinstance(old_text, str) or not old_text:
        return ToolOutcome(ok=False, content="old_text 必须是非空字符串")
    if not isinstance(new_text, str):
        return ToolOutcome(ok=False, content="new_text 必须是字符串")
    if not path.is_file():
        return ToolOutcome(ok=False, content=f"文件不存在: {path}")

    original = _read_text(path)
    newline = _detect_newline(original)
    normalized = original.replace("\r\n", "\n")
    old_norm = old_text.replace("\r\n", "\n")
    new_norm = new_text.replace("\r\n", "\n")
    count = normalized.count(old_norm)
    if count == 0:
        return ToolOutcome(ok=False, content="old_text 未找到，请先 read_file 核对原文")
    if count > 1:
        return ToolOutcome(
            ok=False,
            content=f"old_text 出现 {count} 次，请补更多上下文使其唯一",
        )
    updated = normalized.replace(old_norm, new_norm, 1)
    if newline == "\r\n":
        updated = updated.replace("\n", "\r\n")
    _write_text(path, updated)
    rel = path.relative_to(workspace.resolve())
    return ToolOutcome(
        ok=True,
        content=f"patched {rel.as_posix()}",
        extra={"file_change": {"path": rel.as_posix(), "action": "patched"}},
    )


def execute_list_directory(workspace: Path, args: dict[str, Any]) -> ToolOutcome:
    path = resolve_in_workspace(workspace, str(args.get("path") or "."))
    if not path.exists():
        return ToolOutcome(ok=False, content=f"目录不存在: {path}")
    if not path.is_dir():
        return ToolOutcome(ok=False, content=f"不是目录: {path}")
    recursive = bool(args.get("recursive"))
    root = workspace.resolve()
    lines: list[str] = []
    if recursive:
        for item in sorted(path.rglob("*")):
            if any(part in SKIP_DIR_NAMES for part in item.parts):
                continue
            rel = item.relative_to(root).as_posix()
            suffix = "/" if item.is_dir() else ""
            lines.append(rel + suffix)
            if len(lines) >= MAX_LIST_ENTRIES:
                lines.append(f"[truncated] 超过 {MAX_LIST_ENTRIES} 条")
                break
    else:
        for item in sorted(path.iterdir()):
            if item.name in SKIP_DIR_NAMES:
                continue
            rel = item.relative_to(root).as_posix()
            suffix = "/" if item.is_dir() else ""
            lines.append(rel + suffix)
    if not lines:
        return ToolOutcome(ok=True, content="(空目录)")
    return ToolOutcome(ok=True, content="\n".join(lines))


def execute_search_files(workspace: Path, args: dict[str, Any]) -> ToolOutcome:
    import re

    pattern = str(args.get("pattern") or "")
    if not pattern:
        return ToolOutcome(ok=False, content="缺少 pattern")
    start = resolve_in_workspace(workspace, str(args.get("path") or "."))
    glob = str(args.get("glob") or "*.py")
    try:
        regex = re.compile(pattern)
    except re.error:
        regex = re.compile(re.escape(pattern))

    root = workspace.resolve()
    hits: list[str] = []
    files = [start] if start.is_file() else sorted(start.rglob(glob))
    for file_path in files:
        if not file_path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in file_path.parts):
            continue
        try:
            text = _read_text(file_path)
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                rel = file_path.relative_to(root).as_posix()
                hits.append(f"{rel}:{lineno}:{line.rstrip()}")
                if len(hits) >= MAX_SEARCH_HITS:
                    hits.append(f"[truncated] 超过 {MAX_SEARCH_HITS} 条匹配")
                    return ToolOutcome(ok=True, content="\n".join(hits))
    if not hits:
        return ToolOutcome(ok=True, content="无匹配")
    return ToolOutcome(ok=True, content="\n".join(hits))


def file_tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="read_file",
            description="读取工作区内一个文本文件的完整内容。先 search/list 再读。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对 workspace 的路径"},
                },
                "required": ["path"],
            },
            execute=execute_read_file,
            timeout=15,
        ),
        ToolSpec(
            name="write_file",
            description="写入（或覆盖）工作区内一个文本文件。已有文件优先用 apply_patch。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string", "description": "完整文件内容"},
                },
                "required": ["path", "content"],
            },
            execute=execute_write_file,
            timeout=15,
        ),
        ToolSpec(
            name="apply_patch",
            description="用 old_text/new_text 精确替换已有文件中的一段文本。old_text 必须唯一。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ["path", "old_text", "new_text"],
            },
            execute=execute_apply_patch,
            timeout=15,
        ),
        ToolSpec(
            name="list_directory",
            description="列出工作区内目录内容。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "default": "."},
                    "recursive": {"type": "boolean", "default": False},
                },
                "required": ["path"],
            },
            execute=execute_list_directory,
            timeout=15,
        ),
        ToolSpec(
            name="search_files",
            description="在工作区文本文件中搜索正则或字面量。",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "glob": {"type": "string", "default": "*.py"},
                },
                "required": ["pattern"],
            },
            execute=execute_search_files,
            timeout=20,
        ),
    ]
