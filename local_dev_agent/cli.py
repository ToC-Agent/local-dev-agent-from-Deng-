"""薄 CLI：python -m local_dev_agent -p \"任务\" --cwd <workspace>"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")

from local_dev_agent.config import load_settings
from local_dev_agent.gateway.bailian import BailianProvider
from local_dev_agent.loop.agent import AgentLoop
from local_dev_agent.tools.registry import build_default_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="local_dev_agent", description="Local Developer Agent")
    parser.add_argument("-p", "--prompt", required=True, help="用户任务")
    parser.add_argument("--cwd", default=".", help="workspace 根目录")
    parser.add_argument("--model", default=None, help="覆盖 DASHSCOPE_MODEL")
    parser.add_argument("--max-steps", type=int, default=20, dest="max_steps")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)
    workspace = Path(args.cwd).expanduser().resolve()
    if not workspace.is_dir():
        print(f"[error] workspace 不存在: {workspace}", flush=True)
        return 2

    try:
        settings = load_settings(model_override=args.model)
    except RuntimeError as exc:
        print(f"[error] {exc}", flush=True)
        return 2

    registry = build_default_registry()
    with BailianProvider(
        api_key=settings.api_key,
        base_url=settings.base_url,
        model=settings.model,
    ) as provider:
        agent = AgentLoop(
            provider=provider,
            registry=registry,
            workspace_root=workspace,
            max_steps=args.max_steps,
        )
        print(f"[thread] {agent.thread.id} workspace={workspace} model={settings.model}", flush=True)
        turn = agent.run(args.prompt)
        print(f"[turn] {turn.id} status={turn.status} items={len(turn.items)}", flush=True)
        if turn.status == "completed":
            return 0
        if turn.status == "cancelled":
            return 130
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
