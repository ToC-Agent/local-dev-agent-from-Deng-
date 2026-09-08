from pathlib import Path

import pytest

from local_dev_agent.tools.registry import build_default_registry
from local_dev_agent.tools.sandbox import WorkspaceError, resolve_in_workspace


def test_allows_relative_path_inside_workspace(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    resolved = resolve_in_workspace(ws, "a/b.py")
    assert resolved == (ws / "a" / "b.py").resolve()


def test_allows_absolute_path_inside_workspace(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    inside = (ws / "ok.txt").resolve()
    assert resolve_in_workspace(ws, inside) == inside


def test_rejects_parent_escape(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")
    with pytest.raises(WorkspaceError):
        resolve_in_workspace(ws, "../secret.txt")


def test_write_file_outside_workspace_is_denied(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    outside = tmp_path / "pwned.txt"
    registry = build_default_registry()
    with pytest.raises(WorkspaceError):
        registry.execute(
            "write_file",
            ws,
            {"path": str(outside), "content": "hacked"},
        )
    assert not outside.exists()


def test_read_file_parent_escape_is_denied(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")
    registry = build_default_registry()
    with pytest.raises(WorkspaceError):
        registry.execute("read_file", ws, {"path": "../secret.txt"})
