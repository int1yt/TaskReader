# TaskReader APK — 手机零基础一键测试版

把任务提取助手打包成安卓 App。用户**只需要安装一个 APK、点图标**，
就能在仿微信聊天界面里测试，**不需要 Termux / 命令行 / 任何电脑知识**。

## 工作原理

```
APK（安卓 App）
 ├─ Python 核心（Chaquopy 打包）：task_reader + bot + wechat 全部打进 APK
 ├─ 本地界面：WebView 加载聊天页，JS 通过 Bridge 直接调 Python
 └─ 纯规则模式开箱即用：jieba 已内置，离线秒出，无需下载任何东西
    （AI 增强需手机装有 Ollama 小模型，未装时自动降级为纯规则）
```

## 一键构建（在电脑上执行一次）

### Windows

```powershell
# 双击 build_apk.ps1，或：
powershell -ExecutionPolicy Bypass -File build_apk.ps1
```

脚本会自动完成（已装的组件自动跳过，可重复执行）：
1. 下载 JDK 17（Temurin）
2. 下载 Android SDK 命令行工具
3. 安装 SDK 组件（platform-34 / build-tools）
4. 下载 Gradle 8.7
5. 编译生成 APK

> 首次构建需联网下载，约 **10~30 分钟**；之后增量构建只需 1~2 分钟。

构建完成后 APK 在：
```
app\build\outputs\apk\debug\app-debug.apk
```

## 安装到手机

1. 把 `app-debug.apk` 通过微信/QQ/数据线发到手机
2. 手机点击 APK → 允许「安装未知来源应用」→ 安装
3. 打开「任务提取助手」，在聊天框输入句子即可测试

## 两种测试模式

- **纯规则**（开箱即用）：jieba 解析，离线秒出，顶栏显示「纯规则模式」
- **AI 增强**：手机需先装 Ollama（Play 商店 / F-Droid）并拉取小模型，
  命令：`ollama pull qwen3:0.6b`。未装时自动降级，不影响使用

## 目录结构

```
apk/
  build_apk.ps1              # 一键构建脚本（自动装 JDK/SDK/Gradle）
  build.gradle / settings    # Gradle 工程
  app/
    build.gradle             # Chaquopy 配置（Python 3.11 + jieba）
    src/main/
      AndroidManifest.xml
      java/.../MainActivity  # WebView 聊天界面 + JS↔Python 桥
      assets/index.html      # 仿微信聊天页（直接调 Python，无 HTTP）
      python/                # Python 核心（task_reader/bot/wechat 打包进来）
```

## 常见问题

| 问题 | 解决 |
|---|---|
| 构建报「JAVA_HOME 无效」 | 脚本自带 JDK17，检查是否被杀毒软件拦截了下载 |
| APK 安装失败 | 手机开启「允许未知来源」；或 APK 未下载完整重发一次 |
| 顶栏显示「AI 离线」 | 属正常，纯规则模式仍可用；想要 AI 就装 Ollama 并拉模型 |
| 想改应用名/图标 | 改 `AndroidManifest.xml` 的 label 和 `res/drawable` 图标 |
