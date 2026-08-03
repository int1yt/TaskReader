# Tool-Desktop — TaskReader 桌面版

从一句中文自然语言中提取任务/计划（动作、对象、时间、地点），输出结构化 JSON。
基于**本地 Ollama + qwen3**，数据不出本机，断网可离线运行。

- **规则通道**：确定性、零延迟，负责时间归一化、地点匹配、动词+宾语抽取。
- **LLM 通道**：本地 Ollama，仅当规则层识别不出动作时才调用（省算力）。
- **多级回退**：LLM 不可用 → 自动降级为纯规则，不会报错。

## 一键安装

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

脚本会依次完成（已装自动跳过，可重复执行）：
1. 缺 Python 3.12 时用 winget 自动安装
2. 创建 `.venv` 并安装依赖（jieba）
3. 缺 Ollama 时用 winget 自动安装
4. 启动 Ollama 服务并拉取模型 `qwen3:8b`（约 5.2GB，拉取需联网一次，之后全离线）
5. 写入 `task_reader/config.json`（host + model）

想换更小/更大的模型：`install.ps1 -Model qwen3:4b`

### macOS / Linux

```bash
bash install.sh              # 默认 qwen3:8b
bash install.sh qwen3:4b     # 指定模型
```

macOS 走 `brew install ollama`，Linux 走官方脚本，其余步骤同上。

## 使用

```bash
# Windows
run.bat "我下周三要交论文"
.\.venv\Scripts\python -m task_reader.cli "我们周五晚上六点在学校门口集合，然后一起去图书馆把书还了"

# macOS / Linux
./run.sh "我下周三要交论文"
.venv/bin/python -m task_reader.cli "我下周三要交论文"
```

常用参数：

```bash
--no-llm         # 纯规则模式，不依赖 LLM
--ref 2026-08-02 # 指定参考日期
--json --pretty  # JSON 输出
--stdin          # 管道批量输入，每行一句
```

## 目录结构

```
Tool-Desktop/
  install.ps1 / install.sh   # 一键安装脚本
  run.bat / run.sh           # 快捷运行入口
  requirements.txt           # 依赖（jieba）
  task_reader/               # 核心包（自包含，可独立拷贝）
    config.json              # 安装脚本自动生成（host + model）
    cli.py engine.py ...     # 解析器实现
    dicts/                   # 外置词典
```

## 卸载 / 重装

```bash
# 删除虚拟环境与模型缓存后重新执行 install.ps1 / install.sh 即可
Remove-Item -Recurse -Force .venv                    # Windows
rm -rf .venv                                         # macOS / Linux
ollama rm qwen3:8b                                   # 删除已拉取模型
```
