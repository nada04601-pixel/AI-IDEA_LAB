# AI Shorts Studio 실행 (Windows)
# start-windows.bat을 더블클릭하면 이 스크립트가 실행된다.
# - Python, Node.js, FFmpeg 확인
# - 처음에는 백엔드 가상환경을 만들고, 매번 빠진 패키지만 설치
# - 백엔드(8000)와 화면(3000)을 새 창 두 개로 실행하고, 준비되면 브라우저를 연다
# Windows PowerShell 5.1에서도 돌아가도록 PowerShell 7 전용 문법은 쓰지 않는다.
# 한글이 깨지지 않도록 이 파일은 UTF-8(BOM 포함)로 저장한다.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"
$Host.UI.RawUI.WindowTitle = "AI Shorts Studio"

function Info($msg) { Write-Host $msg -ForegroundColor Cyan }
function Warn($msg) { Write-Host $msg -ForegroundColor Yellow }
function Fail($msg) {
    # 종료 코드 1로 끝내면 start-windows.bat이 창을 멈춰(pause) 메시지를 읽을 수 있게 한다
    Write-Host ""
    Write-Host "[오류] $msg" -ForegroundColor Red
    Write-Host ""
    exit 1
}

Write-Host "============================================"
Write-Host "  AI Shorts Studio 실행 - Windows"
Write-Host "============================================"
Write-Host ""

# ---- 1. 필요한 프로그램 확인 ----
# py 런처를 먼저 쓴다. python.exe가 Microsoft Store 바로가기(WindowsApps)면 실제 설치가 아니므로 건너뛴다.
$pyExe = $null
$pyArgs = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pyExe = "py"
    $pyArgs = @("-3")
} else {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd -and $pythonCmd.Source -notlike "*WindowsApps*") { $pyExe = $pythonCmd.Source }
}
if (-not $pyExe) {
    Fail "Python을 찾을 수 없습니다. PowerShell에서 'winget install Python.Python.3.12'를 실행하고, 창을 모두 닫은 뒤 다시 실행하세요."
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    Fail "Node.js를 찾을 수 없습니다. PowerShell에서 'winget install OpenJS.NodeJS.LTS'를 실행하고, 창을 모두 닫은 뒤 다시 실행하세요."
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Warn "[주의] FFmpeg가 없습니다. 영상 생성과 MP4 렌더링만 안 되고 나머지는 동작합니다."
    Warn "       설치: PowerShell에서 'winget install Gyan.FFmpeg' 실행 후 이 창을 다시 여세요."
}

# ---- 2. 백엔드 패키지 ----
if (-not (Test-Path $venvPython)) {
    Info "[설치] 백엔드 가상환경을 만드는 중입니다 (처음 한 번)..."
    & $pyExe @pyArgs -m venv (Join-Path $backend ".venv")
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) { Fail "가상환경을 만들지 못했습니다. 위 메시지를 확인하세요." }
}
Info "[확인] 백엔드 패키지..."
& $venvPython -m pip install -q --disable-pip-version-check -r (Join-Path $backend "requirements-dev.txt")
if ($LASTEXITCODE -ne 0) { Fail "백엔드 패키지를 설치하지 못했습니다. 인터넷 연결과 위 메시지를 확인하세요." }

# ---- 3. 화면(프런트엔드) 패키지 ----
Info "[확인] 화면 패키지... (처음에는 몇 분 걸립니다)"
Push-Location $frontend
try {
    & npm.cmd install --no-audit --no-fund --loglevel=error
    $npmExit = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($npmExit -ne 0) { Fail "화면 패키지를 설치하지 못했습니다. 인터넷 연결과 위 메시지를 확인하세요." }

# ---- 4. 영상 자막 글꼴 (한글이 네모로 보이지 않게 맑은 고딕) ----
if (-not $env:AISS_SUBTITLE_FONT) { $env:AISS_SUBTITLE_FONT = "Malgun Gothic" }

# ---- 5. 서버 두 개를 새 창으로 실행 (이 스크립트의 환경 변수를 물려받는다) ----
Info "[실행] 백엔드와 화면 서버를 새 창 두 개로 엽니다."
Start-Process -FilePath "cmd.exe" -WorkingDirectory $backend -ArgumentList '/k title AI Shorts Studio - backend 8000 & .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000'
Start-Process -FilePath "cmd.exe" -WorkingDirectory $frontend -ArgumentList '/k title AI Shorts Studio - web 3000 & npm.cmd run dev'

# ---- 6. 준비되면 브라우저 열기 ----
function Test-Url($url) {
    try {
        Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 | Out-Null
        return $true
    } catch {
        return $false
    }
}

Info "[대기] 서버가 준비될 때까지 기다리는 중입니다..."
$ready = $false
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 2
    if ((Test-Url "http://localhost:8000/api/health") -and (Test-Url "http://localhost:3000")) {
        $ready = $true
        break
    }
}

if (-not $ready) {
    Fail "3분이 지나도 서버가 응답하지 않습니다. 새로 열린 두 창(backend, web)의 오류 메시지를 확인하세요."
}

Start-Process "http://localhost:3000"
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  준비 완료: 브라우저에서 http://localhost:3000" -ForegroundColor Green
Write-Host ""
Write-Host "  끝낼 때는 새로 열린 두 창(backend, web)을 닫으세요."
Write-Host "  이 창은 닫아도 됩니다."
Write-Host "============================================" -ForegroundColor Green
Start-Sleep -Seconds 15
