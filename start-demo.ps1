# 一键启动 FastAPI + Vue（Demo）
# 用法：双击 start-demo.cmd，或在当前目录执行 npm run demo
$ErrorActionPreference = 'Stop'

$appDir = $PSScriptRoot
$serverDir = Join-Path $appDir 'server'
$dataDir = Join-Path $appDir 'data'
$dbFile = Join-Path $dataDir 'market.db'
$seedPy = Join-Path $serverDir 'seed.py'
$requirements = Join-Path $serverDir 'requirements.txt'
$apiUrl = 'http://127.0.0.1:8000'
$webUrl = 'http://127.0.0.1:5173'

$apiProc = $null
$startedApi = $false

function Test-Api {
    try {
        Invoke-RestMethod -Uri "$apiUrl/api/health" -TimeoutSec 2 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Test-ApiCurrent {
    try {
        $health = Invoke-RestMethod -Uri "$apiUrl/api/health" -TimeoutSec 3
        return ($health.features -contains 'collect_run' -and
            $health.features -contains 'quotes_page' -and
            $health.features -contains 'pricing_rules' -and
            $health.features -contains 'sync_quota' -and
            $health.features -contains 'save_and_sync' -and
            $health.features -contains 'token_manage' -and
            $health.features -contains 'quote_capture_split')
    }
    catch {
        return $false
    }
}

Write-Host '=== 商品行情计价系统 Demo ==='

# Python
& python --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error '找不到 python，请先安装 Python 3.10+'
    exit 2
}

# Python 依赖
& python -c "import fastapi, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host '安装 Python 依赖...'
    Push-Location $serverDir
    try {
        & python -m pip install -r $requirements
    }
    finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error 'Python 依赖安装失败'
        exit 2
    }
}

# Node 依赖
if (-not (Test-Path (Join-Path $appDir 'node_modules'))) {
    Write-Host '安装前端依赖...'
    Push-Location $appDir
    try {
        & npm install
    }
    finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error 'npm install 失败'
        exit 2
    }
}

# 数据库
if (-not (Test-Path $dbFile)) {
    Write-Host '初始化 SQLite 数据库...'
    Push-Location $serverDir
    try {
        & python $seedPy --reset
    }
    finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error '数据库初始化失败'
        exit 2
    }
}

# API
if (Test-Api) {
    if (Test-ApiCurrent) {
        Write-Host 'API 已在运行且为当前版本，复用现有服务。'
    }
    else {
        $listen = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
        $apiPid = if ($listen) { $listen.OwningProcess } else { $null }
        $apiProcess = $null
        if ($apiPid) {
            $apiProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$apiPid" -ErrorAction SilentlyContinue
        }
        if ($apiProcess -and $apiProcess.CommandLine -like '*uvicorn*app:app*') {
            Write-Host "检测到旧版 API（PID $apiPid），正在重启以加载新接口..."
            Stop-Process -Id $apiPid -Force
            Start-Sleep -Seconds 1
        }
        else {
            Write-Error '8000 端口已被其他程序占用，请先释放端口后重试。'
            exit 1
        }
    }
}

if (-not (Test-Api)) {
    New-Item -ItemType Directory -Force $dataDir | Out-Null
    $apiLog = Join-Path $dataDir 'api.log'
    $apiErr = Join-Path $dataDir 'api.err.log'
    Write-Host '启动 FastAPI...'
    $apiProc = Start-Process -FilePath 'python' `
        -ArgumentList @('-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', '8000') `
        -WorkingDirectory $serverDir -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $apiLog -RedirectStandardError $apiErr
    $startedApi = $true

    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        if ($apiProc.HasExited) { break }
        if (Test-Api) {
            $ready = $true
            break
        }
    }
    if (-not $ready) {
        if ($apiProc -and -not $apiProc.HasExited) {
            Stop-Process -Id $apiProc.Id -Force
        }
        Write-Error "API 启动失败，请查看 $apiErr"
        exit 1
    }
    Write-Host "API 已启动：$apiUrl/docs"
}

Write-Host "启动 Vue 前端：$webUrl"
Write-Host '按 Ctrl+C 停止前端，API 会随后自动停止。'
Write-Host ''

try {
    Push-Location $appDir
    try {
        & npm run dev
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($startedApi -and $apiProc -and -not $apiProc.HasExited) {
        Stop-Process -Id $apiProc.Id -Force
        Write-Host 'FastAPI 已停止。'
    }
}
