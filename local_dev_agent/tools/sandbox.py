"""路径沙箱：所有文件操作必须落在 workspace_root 内。只用 pathlib。"""

from __future__ import annotations

from pathlib import Path


class WorkspaceError(Exception):
    def __init__(self, message: str, requested: str) -> None:
        super().__init__(message)
        self.requested = requested


def resolve_in_workspace(workspace_root: Path, user_path: str | Path) -> Path:
    root = workspace_root.expanduser().resolve()
    raw = Path(user_path)
    candidate = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise WorkspaceError(
            f"路径越出工作区，已拒绝: {user_path}",
            requested=str(user_path),
        ) from exc
    return candidate
