# local-dev-agent

Windows 上的 Local Developer Agent（先做 M0–M4）。

## 给下一个 Cursor 对话的提示词（直接复制）

把下面整段发给新对话。先用 Cursor 打开 `./local-dev-agent`，再开始。

```text

【目标】
做一个能在 Windows 本机跑的开发者 Agent：打开 workspace，读/搜/改文件，跑 Shell，看结果，自动继续，最终给出答复。
交付：能跑的代码 + DESIGN.md。验收用我们自己埋的 bug，不必一上来修陌生大仓库。

【不要做】
浏览器、Office、视觉、MCP、多人 Agent、Desktop、Remote、漂亮 TUI、向量库/AST/RAG。
不要克隆或裁剪整个 Nous Hermes 仓库。只参考它的分层结构，自己写一套精简实现。
不要把 API Key 写入仓库或提交 .env。
不要改 git config，不要提交，除非用户明确要求。

【参考结构（Hermes 的层，不是它的代码）】
入口 CLI（薄）
  → Agent Loop
  → Model Gateway（接口，目前是百炼）
  → Tool Registry
  → read / search / write / patch / shell / git_diff
Core 不许依赖 React / Electron / Tauri。

【对照开发流程.md 必须落地的部分】

M0 边界
- 产品定义：Local Developer Agent。
- 验收：进入 fixtures/buggy_math，Agent 自己定位 bug → 修改 → 跑 pytest → 必要时继续改 → 测试变绿。

M1 领域模型
- Thread（持久会话，绑定 workspace_root）
- Turn（一次用户任务）
- Item（一次行为）
- Item 至少包括：UserMessage、AgentMessage、Reasoning、ToolCall、ToolResult、CommandExecution、FileChange、ApprovalRequest、Error
- ApprovalRequest 本阶段不弹窗：越出工作区直接 deny，并记一条 Item。

M2 Model Gateway
- 自己的接口：stream()、complete()、count_tokens()、compact()
- 只实现 BailianProvider（阿里云百炼 OpenAI 兼容口）
- 统一返回 text / reasoning / tool_calls / usage
- 从环境变量读：
  DASHSCOPE_API_KEY
  DASHSCOPE_BASE_URL（默认 https://dashscope.aliyuncs.com/compatible-mode/v1）
  DASHSCOPE_MODEL（默认 qwen-plus）
- 已实测：qwen-plus 能聊天，也能 function calling。
- count_tokens / compact 第一版可以很简单（估算 + 截断），但接口要在。

M3 Tool Runtime
- 必须有 Tool Registry，不要把工具写死在 prompt 里。
- 每个工具：schema + execute + permission + timeout + result
- 第一版工具：read_file、write_file、apply_patch、list_directory、search_files、shell_exec、git_diff
- apply_patch 可以做成 old_text / new_text 替换，不必一上来解析完整 unified diff。
- 路径只用 pathlib；禁止写死 Linux 路径。
- 所有文件操作必须限制在 workspace_root 内。
- shell_exec 的 cwd 固定为 workspace_root；Windows 上用 PowerShell。
- 工具大输出要截断。

M4 Agent Loop
- 构造上下文 → 调模型 → tool call → 权限检查 → 执行 → 结果写回 → 再调模型 → 直到 final
- 支持 max_steps、Ctrl+C 取消、单工具 timeout、异常恢复（坏 JSON 参数不要把整轮打崩）
- 从第一天就向外打印 Item（tool started / result / final），不要整轮结束才输出。
- 本阶段不用漂亮 CLI，有 argparse 即可：
  python -m local_dev_agent -p "任务" --cwd <workspace> [--model ...] [--max-steps 20]

【建议目录】
local-dev-agent\
  README.md                 
  DESIGN.md                 （M0-M4,方便后续与hermes结构进行参考）
  pyproject.toml
  .gitignore
  local_dev_agent\
    __init__.py
    __main__.py
    cli.py
    domain\models.py
    gateway\provider.py
    gateway\bailian.py
    tools\registry.py
    tools\*.py
    loop\agent.py
    harness\system_prompt.py
  fixtures\buggy_math\      （埋一个小 bug + pytest）
  tests\                    （至少测工作区路径沙箱、apply_patch）

【完成定义】
1. DESIGN.md 写完对照表。
2. 单元测试（沙箱/补丁）能过。

【实现时注意】
- 系统提示词单独放 harness/system_prompt.py，教模型：先搜再读，改完立刻跑测试，测试红就继续。
- Shell 默认允许在工作区内跑 pytest / git / python；工作区外写入直接 deny。

```

---

## 本机已具备

| 项 | 值 |
|----|----|
| 项目 | `E:\local-dev-agent` |
| 语言 | Python 3.11，Windows 原生 |
| 模型 | 阿里云百炼 `qwen-plus`，OpenAI 兼容口 |
| 结构 | 参考 Hermes 分层 |
| 验收 | `fixtures/buggy_math` 从测试红到绿 |
| 密钥 | 本地环境变量 `DASHSCOPE_*`，后续测试时需要改，当前用的是公司百炼的token|

## 安装

在 `E:\local-dev-agent` 打开终端（新开的终端才能读到用户级 `DASHSCOPE_*`）：

```powershell
uv venv --python D:\Python\Python311\python.exe
.\.venv\Scripts\Activate.ps1
uv pip install -e ".[dev]"
```

```powershell
$env:DASHSCOPE_API_KEY.Substring(0,6)   
```

## 先看红，再让 Agent 修，再看绿

```powershell
# 1) 夹具本身现在是红的
.\.venv\Scripts\python.exe -m pytest fixtures\buggy_math -q

# 2) 让 Agent 自己定位、修改、跑测试
.\.venv\Scripts\python.exe -m local_dev_agent -p "修复测试失败，改完立刻跑 pytest，直到变绿" --cwd fixtures\buggy_math

# 3) 再确认夹具已绿
.\.venv\Scripts\python.exe -m pytest fixtures\buggy_math -q
```

Agent 自己的单元测试（沙箱 / apply_patch）：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

通用用法：

```powershell（模型可选，轮次可选）
python -m local_dev_agent -p "任务" --cwd <workspace> [--model qwen-plus] [--max-steps 20]
```


分层说明见 `DESIGN.md`。

## 已知错误

- 若 Agent 报百炼 **401**：当前进程里的 `DASHSCOPE_API_KEY` 被拒绝。桌面/用户级 token 失效时，到百炼控制台重新生成，写入**用户级**环境变量后新开终端。不把 Key 写进仓库。
- Windows 控制台中文乱码时，可先执行 `chcp 65001`，或直接看 Agent 改过的文件与 pytest 结果。
