
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
