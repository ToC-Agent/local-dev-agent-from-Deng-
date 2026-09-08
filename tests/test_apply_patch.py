from pathlib import Path

from local_dev_agent.tools.files import execute_apply_patch
from local_dev_agent.tools.registry import build_default_registry


def test_apply_patch_replaces_unique_span(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    target = ws / "math_utils.py"
    target.write_text("return sum(values) // len(values)\n", encoding="utf-8")

    outcome = execute_apply_patch(
        ws,
        {
            "path": "math_utils.py",
            "old_text": "return sum(values) // len(values)",
            "new_text": "return sum(values) / len(values)",
        },
    )
    assert outcome.ok
    assert target.read_text(encoding="utf-8") == "return sum(values) / len(values)\n"


def test_apply_patch_missing_old_text(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "a.py").write_text("x = 1\n", encoding="utf-8")
    outcome = execute_apply_patch(
        ws,
        {"path": "a.py", "old_text": "not-here", "new_text": "y"},
    )
    assert not outcome.ok
    assert "未找到" in outcome.content


def test_apply_patch_rejects_ambiguous_old_text(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "a.py").write_text("foo\nfoo\n", encoding="utf-8")
    outcome = execute_apply_patch(
        ws,
        {"path": "a.py", "old_text": "foo", "new_text": "bar"},
    )
    assert not outcome.ok
    assert "2 次" in outcome.content


def test_registry_has_required_tools() -> None:
    names = set(build_default_registry().names())
    assert names == {
        "read_file",
        "write_file",
        "apply_patch",
        "list_directory",
        "search_files",
        "shell_exec",
        "git_diff",
    }
