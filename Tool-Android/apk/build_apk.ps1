# ============================================================
#  TaskReader APK 一键构建脚本 (Windows PowerShell)
#
#  零基础使用：
#    1. 双击运行本脚本（或右键 → 使用 PowerShell 运行）
#    2. 等待自动下载 JDK / Android SDK / Gradle 并编译（首次约 10~30 分钟）
#    3. 完成后 APK 在  apk\app\build\outputs\apk\debug\TaskReader-debug.apk
#    4. 把 APK 发到手机安装即可（需允许"安装未知来源应用"）
#
#  脚本会自动检测，已存在的组件直接跳过，可重复执行。
# ============================================================
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$tools = Join-Path $env:LOCALAPPDATA "TaskReaderBuild"
$jdkDir = Join-Path $tools "jdk21"
$sdkDir = Join-Path $tools "android-sdk"
$gradleVer = "8.9"
$gradleDir = Join-Path $tools "gradle-$gradleVer"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Has($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

# 带重试的下载（网络不稳时自动重试 5 次，每次间隔 5 秒）
function Download($url, $out) {
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        for ($i = 1; $i -le 5; $i++) {
            # 用 cmd 执行，把进度条/错误全部静默，避免 PowerShell 把 stderr 当终止错误
            cmd /c "curl.exe -sL --fail --retry 3 --retry-delay 3 -o `"$out`" `"$url`" 2>nul"
            if ($LASTEXITCODE -eq 0 -and (Test-Path $out) -and (Get-Item $out).Length -gt 0) { return }
            Write-Host "下载失败，第 $i/5 次重试 ..."
            Start-Sleep -Seconds 5
        }
        throw "下载失败: $url"
    }
    # 无 curl 时退回 Invoke-WebRequest（同样带重试）
    for ($i = 1; $i -le 5; $i++) {
        try {
            Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
            if ((Get-Item $out).Length -gt 0) { return }
        } catch {
            Write-Host "下载失败，第 $i/5 次重试 ..."
            Start-Sleep -Seconds 5
        }
    }
    throw "下载失败: $url"
}

New-Item -ItemType Directory -Path $tools -Force | Out-Null

# ---------- 1. JDK 21 ----------
Step "1/5 检查 JDK 21"
$javaHome = $null
if (Test-Path (Join-Path $jdkDir "bin\java.exe")) {
    $javaHome = $jdkDir
    Write-Host "JDK 21 已存在: $javaHome"
} elseif (Has "java") {
    # 检测系统 Java 主版本（java -version 输出在 stderr，用 cmd 捕获避免 EAP=Stop 误终止）
    $ver = & cmd /c "java -version 2>&1"
    Write-Host "检测到系统 Java：$ver"
    $ver = $ver -join " "
    if ($ver -match '"(\d+)') {
        $major = [int]$Matches[1]
        if ($major -eq 21) {
            $javaHome = (Split-Path (Split-Path (Get-Command java).Source))
            Write-Host "系统 Java 是 21，直接使用: $javaHome"
        } else {
            Write-Host "系统 Java 不是 21（是 $major），改用自带 JDK21"
        }
    }
}
if (-not $javaHome -or -not (Test-Path (Join-Path $javaHome "bin\java.exe"))) {
    Write-Host "下载 JDK 21 (Temurin) ..."
    # 官方 adoptium 会 307 跳转到 github release（国内常被墙），先走国内镜像
    $urls = @(
        "https://mirrors.tuna.tsinghua.edu.cn/Adoptium/21/jdk/x64/windows/OpenJDK21U-jdk_x64_windows_hotspot_21.0.12_8.zip",
        "https://mirrors.huaweicloud.com/adoptium/21/jdk/x64/windows/OpenJDK21U-jdk_x64_windows_hotspot_21.0.12_8.zip",
        "https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse"
    )
    $zip = Join-Path $tools "jdk21.zip"
    $ok = $false
    foreach ($url in $urls) {
        Write-Host "尝试 $url ..."
        try { Download $url $zip } catch { Write-Host "该源失败，换下一个..." }
        if ((Test-Path $zip) -and (Get-Item $zip).Length -gt 0) { $ok = $true; break }
    }
    if (-not $ok) { throw "JDK 下载失败" }
    Expand-Archive -Path $zip -DestinationPath $tools -Force
    $extracted = Get-ChildItem $tools -Directory | Where-Object { $_.Name -like "jdk-21*" } | Select-Object -First 1
    Move-Item $extracted.FullName $jdkDir -Force
    Remove-Item $zip -Force
    $javaHome = $jdkDir
    Write-Host "JDK 21 已安装"
}
$env:JAVA_HOME = $javaHome
$env:Path = "$javaHome\bin;$env:Path"

# ---------- 2. Android SDK ----------
Step "2/5 检查 Android SDK"
$sdkManager = Join-Path $sdkDir "cmdline-tools\latest\bin\sdkmanager.bat"
if (-not (Test-Path $sdkManager)) {
    Write-Host "下载 Android 命令行工具 ..."
    $url = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
    $zip = Join-Path $tools "cmdline-tools.zip"
    Download $url $zip
    Expand-Archive -Path $zip -DestinationPath (Join-Path $tools "cmdline-tools-tmp") -Force
    New-Item -ItemType Directory -Path (Join-Path $sdkDir "cmdline-tools\latest") -Force | Out-Null
    Copy-Item (Join-Path $tools "cmdline-tools-tmp\cmdline-tools\*") (Join-Path $sdkDir "cmdline-tools\latest\") -Recurse -Force
    Remove-Item (Join-Path $tools "cmdline-tools-tmp") -Recurse -Force
    Remove-Item $zip -Force
    Write-Host "命令行工具已安装"
}
$env:ANDROID_HOME = $sdkDir
$env:ANDROID_SDK_ROOT = $sdkDir
$env:Path = "$sdkDir\platform-tools;$sdkDir\cmdline-tools\latest\bin;$env:Path"

# ---------- 3. SDK 组件 ----------
Step "3/5 安装 SDK 组件 (platform 34 / build-tools)"
$lic = Join-Path $sdkDir "licenses"
New-Item -ItemType Directory -Path $lic -Force | Out-Null
Set-Content -Path (Join-Path $lic "android-sdk-license") -Value "`n24333f8a63b6825ea9c5514f83c2829b004d1fee" -Encoding ASCII
& $sdkManager --sdk_root=$sdkDir "platforms;android-34" "build-tools;34.0.0" "platform-tools" | Out-Null

# ---------- 4. Gradle ----------
Step "4/5 检查 Gradle $gradleVer"
if (-not (Test-Path (Join-Path $gradleDir "bin\gradle.bat"))) {
    Write-Host "下载 Gradle $gradleVer ..."
    # 官方源在国内常被墙，先试国内镜像，再退官方源
    $urls = @(
        "https://mirrors.cloud.tencent.com/gradle/gradle-$gradleVer-bin.zip",
        "https://mirrors.huaweicloud.com/gradle/gradle-$gradleVer-bin.zip",
        "https://services.gradle.org/distributions/gradle-$gradleVer-bin.zip"
    )
    $zip = Join-Path $tools "gradle.zip"
    $ok = $false
    foreach ($url in $urls) {
        Write-Host "尝试 $url ..."
        Download $url $zip
        if (Test-Path $zip) { $ok = $true; break }
    }
    if (-not $ok) { throw "Gradle 下载失败" }
    Expand-Archive -Path $zip -DestinationPath $tools -Force
    Remove-Item $zip -Force
    Write-Host "Gradle 已安装"
}

# ---------- 5. 构建 APK ----------
Step "5/5 编译 APK（首次较慢，请耐心等待）"
$env:GRADLE_USER_HOME = Join-Path $tools "gradle-home"
$gradle = Join-Path $gradleDir "bin\gradle.bat"
Push-Location $root
try {
    & $gradle assembleDebug --no-daemon
    if ($LASTEXITCODE -ne 0) { throw "Gradle 构建失败" }
} finally {
    Pop-Location
}

$apk = Join-Path $root "app\build\outputs\apk\debug\app-debug.apk"
if (Test-Path $apk) {
    Write-Host ""
    Write-Host "==============================================================" -ForegroundColor Green
    Write-Host "  构建成功！APK 位置:" -ForegroundColor Green
    Write-Host "  $apk" -ForegroundColor Green
    Write-Host ""
    Write-Host "  用法：把 APK 发到手机 → 点击安装 → 允许未知来源 → 打开" -ForegroundColor Green
    Write-Host "==============================================================" -ForegroundColor Green
} else {
    Write-Host "构建未生成 APK，请查看上方错误日志。" -ForegroundColor Red
}
