# local-dev-agent

Windows 本机上的 Local Developer Agent（当前做到 M0–M4）。

给模型一个工作区，它会读文件、改代码、跑命令，根据结果继续，直到给出答复。分层参考 Hermes，实现是自研精简版，不依赖 Electron / Tauri，也不接 MCP。

更细的里程碑对照见 [DESIGN.md](DESIGN.md)。

## 能做什么 / 先不做什么

**能做：** 在指定工作区内读、搜、写、打补丁；用 PowerShell 跑 `pytest` / `python` / `git`；把每一步（工具开始、结果、最终答复）打到终端。

**先不包含：** 浏览器、Office、视觉、MCP、多人或远程 Agent、桌面端、向量检索。

文件写入出了工作区会被拒绝。Shell 的当前目录固定在工作区根，但不会解析用户有没有 `cd` 出去。

## 环境

- Windows + Python 3.11+
- 阿里云百炼 API Key（OpenAI 兼容口）

在**用户级**环境变量里配置（不要写进仓库或 `.env`）：

| 变量 | 说明 |
|------|------|
| `DASHSCOPE_API_KEY` | 必填 |
| `DASHSCOPE_BASE_URL` | 可选，默认 `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `DASHSCOPE_MODEL` | 可选，默认 `qwen-plus` |

改完环境变量后需要新开终端。

## 安装

```powershell
git clone https://github.com/ToC-Agent/local-dev-agent-from-Deng-.git
cd local-dev-agent-from-Deng-
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

有 `uv` 也可以：`uv venv` 后 `uv pip install -e ".[dev]"`。

## 使用

```powershell
python -m local_dev_agent -p "要做的事" --cwd <工作区目录> [--model qwen-plus] [--max-steps 20]
```

| 参数 | 含义 |
|------|------|
| `-p` / `--prompt` | 任务 |
| `--cwd` | 工作区根目录，Agent 只能改这里面的文件 |
| `--model` | 覆盖默认模型 |
| `--max-steps` | 最多循环轮数，默认 20 |

中途停止：`Ctrl+C`。

## 验收夹具

`fixtures/buggy_math` 里有一个故意写错的 `mean`（整数除法）。Agent 应能自己定位、修改、跑测试，直到变绿。

仓库里当前版本**已经修好**。要当场看一遍循环，先把 `math_utils.py` 里的 `/` 改回 `//`，再执行：

```powershell
python -m pytest fixtures\buggy_math -q
# 期望失败

python -m local_dev_agent -p "修复测试失败，改完立刻跑 python -m pytest -q，直到变绿" --cwd fixtures\buggy_math

python -m pytest fixtures\buggy_math -q
# 期望通过
```

工程自身的单测（路径沙箱、`apply_patch`）：

```powershell
python -m pytest tests -q
```

## 结构

```
local_dev_agent/
  cli.py                 命令行入口
  domain/models.py       Thread / Turn / Item
  gateway/               模型接口，目前只接百炼
  tools/                 工具注册表与七个本地工具
  loop/agent.py          Agent 循环
  harness/               系统提示词
fixtures/buggy_math/     验收用小夹具
tests/                   沙箱与补丁单测
```

工具：`read_file`、`write_file`、`apply_patch`、`list_directory`、`search_files`、`shell_exec`、`git_diff`。
