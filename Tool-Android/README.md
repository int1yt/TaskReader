# Tool-Android — TaskReader 手机版

在 Android 手机上本地提取中文任务（动作、对象、时间、地点），输出结构化 JSON。
基于 **Termux + Ollama + qwen3 小模型**，数据不出手机，断网可离线运行。

> **零基础用户**：按照下文「零基础三步走」操作即可，全程无需任何电脑知识，
> 安装脚本会自动检测环境并引导你。

---

## 零基础三步走（大约 10 分钟）

### 第 1 步：安装 Termux（仅需一次）

1. 用手机浏览器打开 **F-Droid 应用商店**：<https://f-droid.org>
2. 下载并安装 F-Droid（一个安装应用的应用）
3. 打开 F-Droid，搜索 **Termux**，点「安装」
   > ⚠️ 不要从手机自带应用商店 / Play 商店装 Termux，版本太旧会安装失败

### 第 2 步：把 Tool-Android 拷贝到手机

| 方式 | 操作 |
|---|---|
| **A（推荐）** | 数据线连接电脑，把整个 `Tool-Android` 文件夹复制到手机「内部存储 → Download」目录 |
| B | 用微信 / QQ 把文件夹打包发送到手机，再解压 |

### 第 3 步：打开 Termux，粘贴 3 行命令

打开 Termux 应用，依次输入（每行输完按回车）：

```bash
termux-setup-storage
cd /storage/emulated/0/Download/Tool-Android
bash install.sh
```

安装脚本会自动完成一切：更新软件源 → 装 Python → 装 Ollama →
拉取小模型 qwen3:0.6b → 写入配置文件。**全程只需联网一次**，之后全离线。

装好后，**以后每次使用**只需打开 Termux 输入两行：

```bash
cd /storage/emulated/0/Download/Tool-Android
bash run.sh 我下周三要交论文
```

---

## 常用用法

```bash
# 提取任务（自动启动本地 LLM）
bash run.sh 我下周三要交论文
bash run.sh 明天任务：1.看夏商周网课 2.刷真题

# 纯规则模式（不依赖 LLM，秒出，更省电）
bash run.sh 我下周三要交论文 --no-llm

# 指定参考日期 / JSON 输出
bash run.sh 两周后交作业 --ref 2026-08-02
bash run.sh 周五晚上八点开会 --json --pretty
```

## 换更大的模型（内存 4GB+ 手机）

```bash
bash install.sh qwen3:1.7b    # 约 1.4GB，更聪明
bash install.sh qwen3:4b      # 约 2.5GB，仅建议旗舰机
```

## 离线说明

- **首次安装需要联网**：下载 Termux 依赖、Ollama、以及模型（qwen3:0.6b ≈ 523MB）。
- **之后完全离线**：模型已存于 `~/.ollama/models`，开飞行模式也能用。
- 未安装 LLM / 模型 / 服务未启动时，工具自动降级为纯规则模式并提示，不报错。

## 性能建议

- **低内存手机**（<4GB）：只用规则模式 `--no-llm`，不启动 Ollama。
- **关后台限制**：设置 → 电池 → 允许 Termux 后台运行，防止长时间任务被杀。
- 模型和配置务必放 `~`（Termux 私有目录），放 `/sdcard` 会报权限错误。

## 常见问题

| 现象 | 解决 |
|---|---|
| 输入 `bash install.sh` 提示「未检测到 Termux」 | 说明你不在 Termux 里运行，请先按「零基础三步走」第 1 步安装 Termux |
| `bash: cd: ...: No such file` | 文件夹路径不对，用 `cd /storage/emulated/0/Download` 后 `ls` 查看实际名字 |
| `pkg install ollama` 找不到包 | 先 `pkg install tur-repo` 再重试，或换 `ollama-termux` |
| 模型下载失败 / 内存不足 | 用更小模型 `qwen3:0.6b`，或改用纯规则模式 |
| Termux 崩溃 | 从 F-Droid 重装（Play 版过旧），并允许后台运行 |

## 目录结构

```
Tool-Android/
  install.sh               # 一键安装脚本（含 Termux 环境检测与安装指引）
  run.sh                   # 快捷运行入口（自动拉起 Ollama）
  requirements.txt         # 依赖（jieba）
  task_reader/             # 核心包（自包含，可独立拷贝）
    config.json            # 安装脚本自动生成（host + model）
    cli.py engine.py ...   # 解析器实现
    dicts/                 # 外置词典
```
