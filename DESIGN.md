# DESIGN：Local Developer Agent（M0–M4）

对照 Hermes 的分层，自己写一套精简实现。不克隆、不裁剪 Hermes 仓库。

## 分层对照

| Hermes 层 | 本仓库落点 | Milestone | 本阶段取舍 |
|-----------|------------|-----------|------------|
| 入口（CLI / TUI / Desktop / Remote） | `local_dev_agent/cli.py`、`__main__.py` | M4 | 只要 argparse，不要漂亮 TUI / Desktop / Remote |
| Agent Loop（构造上下文 → 调模型 → 工具 → 再调） | `local_dev_agent/loop/agent.py` | M4 | 同步循环；边跑边打印 Item |
| Model Gateway（多模型提供商） | `gateway/provider.py` 接口 + `gateway/bailian.py` | M2 | 只接百炼 OpenAI 兼容口 |
| Tool Runtime / Registry | `tools/registry.py` + `tools/*.py` | M3 | 七个本地工具；不做 MCP |
| Session / Thread 领域对象 | `domain/models.py` | M1 | Thread 绑定 workspace；Turn 含 Item 序列 |
| Skills / Memory / RAG | `harness/system_prompt.py` | M4 | 只要系统提示词，不要向量库 / AST / RAG |
| Browser / Office / Vision | （无） | M0 | 明确不做 |

数据流：

```
CLI（-p / --cwd / --model / --max-steps）
  → AgentLoop.run(task)
      → 把 Turn 里的 Item 编成 ChatMessage
      → ZhongtaiProvider / BailianProvider.complete(messages, tools=Registry.schemas)
      → 若有 tool_calls：权限检查 → execute → 记 ToolResult / FileChange / CommandExecution
      → 再调模型，直到纯文本 final 或 max_steps / Ctrl+C
```

## M0 边界

- 产品：Windows 本机 **Local Developer Agent**。
- 验收夹具：`fixtures/buggy_math`。Agent 自己定位 `//` 整数除法 → 改成 `/` → 跑 pytest → 必要时继续 → 测试变绿。
- 不做：浏览器、Office、视觉、MCP、多人 Agent、Desktop、Remote、漂亮 TUI、向量库 / AST / RAG。

## M1 领域模型

| 对象 | 含义 |
|------|------|
| `Thread` | 一次持久会话，绑定 `workspace_root` |
| `Turn` | 一次用户任务（一条 `-p`） |
| `Item` | 一次可观察行为 |

Item 种类：`UserMessage`、`AgentMessage`、`Reasoning`、`ToolCall`、`ToolResult`、`CommandExecution`、`FileChange`、`ApprovalRequest`、`Error`。

`ApprovalRequest` 本阶段不弹窗：路径越出工作区直接 deny，并记一条 Item。

## M2 Model Gateway

接口（`ModelProvider`）：

- `stream()`：SSE 增量，事件为 text / reasoning / tool_calls / usage / finish
- `complete()`：一次拿齐 `text / reasoning / tool_calls / usage`
- `count_tokens()`：按约 2 字符/token 估算
- `compact()`：保留 system + 最近消息，超限则截断

两家都走 OpenAI 兼容口（`gateway/openai_compat.py`），差别只在鉴权头：

| Provider | 默认地址 | 鉴权 | 默认模型 |
|----------|----------|------|----------|
| `ZhongtaiProvider`（默认） | `http://10.8.144.65:30191/v1` | `X-API-Key` | `qwen3.7-plus` |
| `BailianProvider` | 百炼 compatible-mode/v1 | `Authorization: Bearer` | `qwen-plus` |

- 环境变量：中台 `ZHONGTAI_*` / `AGENT_PROVIDER`；百炼 `DASHSCOPE_*`
- HTTP：`httpx.Client(..., trust_env=False)`
- 不把 Key 写入仓库，也不打印到日志
- 这是「换模型通道」，不是把 Agent 注册进中台应用市场

## M3 Tool Runtime

每个工具：`schema + execute + permission + timeout + result`。

| 工具 | 作用 |
|------|------|
| `read_file` | 读工作区内文本 |
| `write_file` | 新建或覆盖 |
| `apply_patch` | `old_text` / `new_text` 唯一替换 |
| `list_directory` | 列目录 |
| `search_files` | 正则/字面量搜索 |
| `shell_exec` | cwd=workspace，Windows 走 PowerShell |
| `git_diff` | `git status` + `git diff` |

路径只用 `pathlib`。`resolve_in_workspace()` 用 `resolve()` + `relative_to(root)` 防止 `..` 逃逸。大输出截到 16000 字符。

Shell 默认可跑 pytest / git / python；工作区外**写入**由文件工具直接 deny。Shell 本身只固定 cwd，不做完整 OS 沙箱（Windows 上完整约束成本过高，记为已知限制）。

## M4 Agent Loop

1. 构造上下文（system prompt + Turn 中的 Item）
2. `complete()`
3. 有 tool call：校验 JSON → 权限 → 超时执行 → 结果写回
4. 只有文本：当作 final
5. `max_steps`、Ctrl+C、单工具 timeout、坏 JSON 不打崩整轮
6. 每个 Item 立刻打印（`loop/printer.py`）

CLI：

```text
python -m local_dev_agent -p "任务" --cwd <workspace> [--provider zhongtai] [--model ...] [--max-steps 20]
```

## 关键函数（给后续自己改时对照）

| 函数 | 文件 | 干什么 |
|------|------|--------|
| `resolve_in_workspace` | `tools/sandbox.py` | 规范化路径并拒绝逃逸 |
| `ToolRegistry.execute` | `tools/registry.py` | 按名字找工具，带 timeout 跑 |
| `execute_apply_patch` | `tools/files.py` | 唯一子串替换 |
| `OpenAICompatProvider.complete` | `gateway/openai_compat.py` | 调 `/chat/completions` |
| `ZhongtaiProvider` | `gateway/zhongtai.py` | 中台通道，`X-API-Key` |
| `AgentLoop.run` | `loop/agent.py` | 整轮循环 |
| `AgentLoop._build_messages` | `loop/agent.py` | Item → OpenAI 消息（含 tool 角色） |

## 已知限制

- Thread 目前活在单次进程内，没有跨进程落盘（领域对象已具备，持久化可后续加）。
- `count_tokens` / `compact` 是估算 + 截断，不是官方 tokenizer。
- `apply_patch` 不是 unified diff，只做精确文本替换。
- `shell_exec` 不解析命令是否 `cd` 出工作区。
