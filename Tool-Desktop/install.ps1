# ============================================================
#  Tool-Desktop 一键安装脚本 (Windows PowerShell)
#  用法:  powershell -ExecutionPolicy Bypass -File install.ps1
#  可选:  powershell -ExecutionPolicy Bypass -File install.ps1 -Model qwen3:4b
#  已安装的步骤会自动跳过，可重复执行。
# ============================================================
param(
    [string]$Model = "qwen3:8b"
)
$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

function Get-CommandPath($name) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# ---------- 1. Python ----------
Write-Step "1/5 检查 Python"
$py = Get-CommandPath "python"
if (-not $py) {
    Write-Host "未检测到 Python，正在通过 winget 安装 Python 3.12 ..."
    winget install --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
    $py = Get-CommandPath "python"
    if (-not $py) { Write-Error "Python 安装失败，请手动安装后重试。"; exit 1 }
}
Write-Host "Python: $py"

# ---------- 2. 虚拟环境 + 依赖 ----------
Write-Step "2/5 创建虚拟环境并安装依赖 (jieba)"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}
$venvPy = ".venv\Scripts\python.exe"
& $venvPy -m pip install --upgrade pip -q
& $venvPy -m pip install -r requirements.txt -q
Write-Host "依赖安装完成。"

# ---------- 3. Ollama ----------
Write-Step "3/5 检查 Ollama"
$ollama = Get-CommandPath "ollama"
if (-not $ollama) {
    Write-Host "未检测到 Ollama，正在通过 winget 安装 ..."
    winget install --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
    $ollama = Get-CommandPath "ollama"
    if (-not $ollama) { Write-Error "Ollama 安装失败，请手动安装后重试。"; exit 1 }
}
Write-Host "Ollama: $ollama"

# ---------- 4. 启动服务 + 拉取模型 ----------
Write-Step "4/5 启动 Ollama 服务并拉取模型 ($Model)"
$ollamaExe = $ollama
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2
} catch {
    Write-Host "启动 Ollama 服务 ..."
    Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 4
}

& $ollamaExe pull $Model
Write-Host "模型 $Model 已就绪。"

# ---------- 5. 写配置 ----------
Write-Step "5/5 写入配置文件 task_reader/config.json"
$config = @{
    host  = "http://127.0.0.1:11434"
    model = $Model
} | ConvertTo-Json
Set-Content -Path "task_reader\config.json" -Value $config -Encoding UTF8

Write-Host ""
Write-Host "安装完成！使用方法:"
Write-Host "  交互:    .\.venv\Scripts\python -m task_reader.cli ""我下周三要交论文"""
Write-Host "  快捷:    .\run.bat ""我下周三要交论文"""
Write-Host "  纯规则:  .\.venv\Scripts\python -m task_reader.cli ""我下周三要交论文"" --no-llm"
