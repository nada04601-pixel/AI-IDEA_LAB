# 틀린그림 찾기 쇼츠 만들기 (Windows)
# make-windows.bat을 더블클릭하면 이 스크립트가 실행된다.
# - Python, FFmpeg 확인 → 처음 한 번 가상환경과 패키지 설치 → 쇼츠 MP4 생성 → 결과 폴더 열기
# - make-windows.bat 뒤에 옵션을 붙이면 그대로 전달된다. 예) make-windows.bat --seed 7 --time 10
# Windows PowerShell 5.1에서도 돌아가도록 PowerShell 7 전용 문법은 쓰지 않는다.
# 한글이 깨지지 않도록 이 파일은 UTF-8(BOM 포함)로 저장한다.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$out = Join-Path $root "out"
$Host.UI.RawUI.WindowTitle = "틀린그림 찾기 쇼츠"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

function Info($msg) { Write-Host $msg -ForegroundColor Cyan }
function Fail($msg) {
    Write-Host ""
    Write-Host "[오류] $msg" -ForegroundColor Red
    Write-Host ""
    exit 1
}

# ---- 1. 필요한 프로그램 확인 ----
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
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Fail "FFmpeg를 찾을 수 없습니다. PowerShell에서 'winget install Gyan.FFmpeg'를 실행하고, 창을 모두 닫은 뒤 다시 실행하세요."
}

# ---- 2. 패키지 ----
if (-not (Test-Path $venvPython)) {
    Info "[설치] 가상환경을 만드는 중입니다 (처음 한 번)..."
    & $pyExe @pyArgs -m venv (Join-Path $root ".venv")
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) { Fail "가상환경을 만들지 못했습니다. 위 메시지를 확인하세요." }
}
Info "[확인] 패키지..."
& $venvPython -m pip install -q --disable-pip-version-check -r (Join-Path $root "requirements.txt")
if ($LASTEXITCODE -ne 0) { Fail "패키지 설치에 실패했습니다. 인터넷 연결을 확인하세요." }

# ---- 3. 쇼츠 만들기 ----
Info "[생성] 쇼츠를 만드는 중입니다 (30초~1분 정도 걸립니다)..."
Push-Location $root
try {
    & $venvPython -m spotdiff --out $out @args
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { Fail "쇼츠를 만들지 못했습니다. 위 메시지를 확인하세요." }

Info "[완료] 결과 폴더를 엽니다: $out"
Start-Process explorer.exe $out
