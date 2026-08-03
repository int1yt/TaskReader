# Tool-Android — TaskReader 手机版

在 Android 手机上本地提取中文任务（动作、对象、时间、地点）。
基于 **Termux + Ollama + qwen3 小模型**，数据不出手机，断网可离线运行。

**最终形态是微信机器人**：给微信好友发一句话，机器人回复提取出的任务。
当前微信接入模块为**预留接口**（`wechat/`），先用**网页测试端**在手机上验证
核心流程。

架构：`bot/`（消息处理核心，与传输无关）← `wechat/`（微信接入，待实现）＋
`webui.py`（网页测试端，模拟微信聊天）。

> **零基础用户**：按照下文「零基础三步走」操作即可，全程无需任何电脑知识，
> 安装脚本会自动检测环境并引导你。装完后用「网页测试端」最省事。

---

## 网页测试端（模拟微信聊天）

安装完成后，在 Termux 里输入一行：

```bash
bash serve.sh
```

然后按提示打开手机浏览器访问 `http://127.0.0.1:8000`，即可看到**仿微信聊天界面**：

- 给机器人发一句中文，它像微信一样回复（绿色气泡是你的消息，白色气泡是机器人回复）
- 回复里展示每个任务的时间、地点、备注、置信度，并附带结构化卡片
- 界面有示例句子，点一下即可试玩
- 顶栏显示「AI 在线 / 纯规则模式」，代表本地小模型是否可用

> 💡 小技巧：在浏览器菜单里选「**添加到主屏幕**」，之后就能像普通 App 一样
> 点图标打开，无需再进 Termux。

## 交互聊天测试端（命令行，不用 HTTP / 浏览器）

不想用网页也可以，直接在 Termux 里一问一答，效果和微信聊天一样：

```bash
bash chat.sh              # AI 增强
bash chat.sh --no-llm     # 纯规则模式（更快，不依赖模型）
```

进去后输入一句话回车，机器人就回复提取出的任务；输入 `quit` 退出。
两种测试端共用同一个 `BotCore`，验证的是同一套核心逻辑。

---

## 微信接入（预留接口，待实现）

当前 `wechat/` 目录已定义好接入骨架，尚未实现真实登录/收发：

```
wechat/
  models.py    # WeChatMessage / WeChatContext 消息模型
  adapter.py   # WeChatAdapter：登录、收发、消息回调（TODO 待实现）
```

接入真实微信时只需三步：
1. 选定微信 SDK（如 itchat / wechaty / wxauto / 企业微信回调）
2. 在 `WeChatAdapter.login()` 实现登录
3. 把收到的消息转成 `WeChatMessage` → `self.core.handle_text(...)` → `send()` 发回

**全部业务逻辑在 `bot/core.py`，微信端不碰解析细节。** 命令行可先无微信验证流程：

```bash
python -m wechat.adapter --dry-run "我下周三要交论文"
```

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

装好后，**以后每次使用**打开 Termux 输入两行即可启动图形界面：

```bash
cd /storage/emulated/0/Download/Tool-Android
bash serve.sh
```

然后手机浏览器打开 `http://127.0.0.1:8000` 即可点按使用（也可「添加到主屏幕」变成 App）。

---

## 常用用法

```bash
# 图形界面（推荐，不用敲命令）
bash serve.sh

# 命令行提取任务（自动启动本地 LLM）
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
  serve.sh                 # 网页测试端启动（模拟微信聊天，推荐先测这个）
  run.sh                   # 命令行快捷运行（自动拉起 Ollama）
  webui.py                 # 测试客户端 Web 服务（纯标准库，零额外依赖）
  webui/
    index.html             # 仿微信聊天界面（浏览器打开）
  bot/                     # 机器人核心（与传输无关，微信/网页共用）
    core.py                # BotCore：处理文本消息 → 返回回复（文本+结构化任务）
    reply.py               # Reply：机器人输出统一格式
  wechat/                  # 微信接入模块（预留接口，待实现）
    adapter.py             # WeChatAdapter：登录/收发/回调（TODO）
    models.py              # WeChatMessage / WeChatContext 消息模型
  requirements.txt         # 依赖（jieba）
  task_reader/             # 解析核心（自包含，可独立拷贝）
    config.json            # 安装脚本自动生成（host + model）
    cli.py engine.py ...   # 解析器实现
    dicts/                 # 外置词典
```
