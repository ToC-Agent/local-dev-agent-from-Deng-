from pathlib import Path

from local_dev_agent.gateway.provider import ChatMessage, ModelResponse, ToolCallRequest
from local_dev_agent.loop.agent import AgentLoop
from local_dev_agent.tools.registry import build_default_registry


class ScriptedProvider:
    def __init__(self, replies: list[ModelResponse]) -> None:
        self.replies = list(replies)
        self.calls = 0

    def complete(self, messages: list[ChatMessage], tools=None) -> ModelResponse:
        self.calls += 1
        if not self.replies:
            return ModelResponse(text="fallback")
        return self.replies.pop(0)

    def stream(self, messages, tools=None):
        yield from ()

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 2)

    def compact(self, messages: list[ChatMessage], max_tokens: int) -> list[ChatMessage]:
        return list(messages)


def test_bad_json_tool_args_do_not_crash_turn(tmp_path: Path) -> None:
    provider = ScriptedProvider(
        [
            ModelResponse(
                tool_calls=[
                    ToolCallRequest(id="c1", name="read_file", arguments="{not-json"),
                ]
            ),
            ModelResponse(text="我已根据错误继续，任务结束。"),
        ]
    )
    loop = AgentLoop(
        provider=provider,
        registry=build_default_registry(),
        workspace_root=tmp_path,
        max_steps=5,
        print_items=False,
    )
    turn = loop.run("读一下不存在的文件")
    assert turn.status == "completed"
    kinds = [item.kind for item in turn.items]
    assert "error" in kinds
    assert "tool_result" in kinds
    assert "agent_message" in kinds
