# 쇼핑 쇼츠 메이커 설치 (Windows)
# setup.bat을 더블클릭하면 이 스크립트가 실행된다. 여러 번 실행해도 안전하다 (이미 된 것은 건너뜀).
#  1) Python 3.11~3.12 확인    2) 가상환경(.venv) 생성
#  3) GPU 확인 → PyTorch(CUDA 또는 CPU) 설치    4) 필수·AI 패키지 설치
#  5) FFmpeg 확인 (없으면 winget으로 설치 제안)    6) 폰트 내려받기    7) ssm doctor
# 옵션: -Cpu (GPU가 있어도 CPU용 PyTorch), -ReinstallTorch (PyTorch 다시 설치)
# Windows PowerShell 5.1에서도 돌아가도록 PowerShell 7 전용 문법은 쓰지 않는다.
# 한글이 깨지지 않도록 이 파일은 UTF-8(BOM 포함)로 저장한다.
param([switch]$Cpu, [switch]$ReinstallTorch)

# 외부 프로그램(pip, python)이 경고를 stderr로 내도 멈추지 않도록 Continue로 두고, 종료 코드($LASTEXITCODE)로 판단한다
$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$TorchIndexes = @("https://download.pytorch.org/whl/cu128", "https://download.pytorch.org/whl/cu126")
$Host.UI.RawUI.WindowTitle = "쇼핑 쇼츠 메이커 설치"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"

function Info($msg) { Write-Host $msg -ForegroundColor Cyan }
function Ok($msg) { Write-Host "  [완료] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  [주의] $msg" -ForegroundColor Yellow }
function Fail($msg) {
    Write-Host ""
    Write-Host "[오류] $msg" -ForegroundColor Red
    Write-Host ""
    exit 1
}
function Pip {
    & $venvPython -m pip install --disable-pip-version-check @args
    if ($LASTEXITCODE -ne 0) { Fail "패키지 설치에 실패했습니다: pip install $args" }
}

Write-Host "============================================"
Write-Host "  쇼핑 쇼츠 메이커 설치 - Windows"
Write-Host "============================================"
Write-Host ""

# 1) Python ------------------------------------------------------------------
Info "[1/7] Python 확인"
$basePython = $null
$ver = ""
foreach ($c in @("py -3.12", "py -3.11", "python")) {
    $parts = $c.Split(" ")
    $exe = $parts[0]
    $cargs = @($parts | Select-Object -Skip 1)
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    $out = & $exe @cargs -c "import sys; print('%d.%d|%s' % (sys.version_info[0], sys.version_info[1], sys.executable))" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $out) { continue }
    $ver, $path = "$out".Trim().Split("|")
    if ($ver -eq "3.11" -or $ver -eq "3.12") { $basePython = $path; break }
}
if (-not $basePython) {
    Fail "Python 3.12(또는 3.11)이 필요합니다. https://www.python.org/downloads/ 에서 설치할 때 'Add python.exe to PATH'를 체크한 뒤 다시 실행하세요. (3.13 이상은 GPU용 PyTorch 호환 문제로 권장하지 않습니다)"
}
Ok "Python $ver ($basePython)"

# 2) 가상환경 -------------------------------------------------------------------
Info "[2/7] 가상환경(.venv)"
if (-not (Test-Path $venvPython)) {
    & $basePython -m venv (Join-Path $root ".venv")
    if ($LASTEXITCODE -ne 0) { Fail "가상환경을 만들지 못했습니다." }
    Ok "새로 만듦"
} else { Ok "이미 있음" }
& $venvPython -m pip install --disable-pip-version-check -q --upgrade pip | Out-Null

# Visual C++ 런타임: 오래되면(14.40 미만) PyTorch·onnxruntime이 DLL 오류(WinError 1114)로 불러와지지 않는다
$vcDll = Join-Path $env:SystemRoot "System32\msvcp140.dll"
$vcOld = $true
if (Test-Path $vcDll) {
    $vi = (Get-Item $vcDll).VersionInfo
    $vcOld = ($vi.FileMajorPart -lt 14) -or ($vi.FileMajorPart -eq 14 -and $vi.FileMinorPart -lt 40)
}
if ($vcOld -and (Get-Command winget -ErrorAction SilentlyContinue)) {
    $answer = Read-Host "  Visual C++ 런타임이 오래되었습니다 (PyTorch에 필요). winget으로 최신 버전을 설치할까요? (Y/n)"
    if ($answer -eq "" -or $answer -match "^[Yy]") {
        & winget install --id Microsoft.VCRedist.2015+.x64 -e --accept-source-agreements --accept-package-agreements
        Ok "Visual C++ 런타임 설치 (적용되지 않으면 PC를 다시 시작하세요)"
    } else { Warn "Visual C++ 런타임이 오래되면 OCR(PyTorch)이 동작하지 않습니다" }
} elseif ($vcOld) {
    Warn "Visual C++ 런타임이 오래되었습니다. https://aka.ms/vs/17/release/vc_redist.x64.exe 를 설치하세요."
}

# 3) GPU · PyTorch ------------------------------------------------------------------
Info "[3/7] GPU 확인 및 PyTorch 설치"
$hasGpu = $false
if (-not $Cpu -and (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    $gpuName = & nvidia-smi --query-gpu=name --format=csv,noheader 2>$null
    if ($LASTEXITCODE -eq 0 -and $gpuName) { $hasGpu = $true; Ok "NVIDIA GPU: $(("$gpuName").Split("`n")[0].Trim())" }
}
if (-not $hasGpu) { Warn "NVIDIA GPU를 쓰지 않습니다 → CPU 모드 (느리지만 동작합니다)" }

$torchState = & $venvPython -c "import torch; print('cuda' if torch.cuda.is_available() else 'cpu')" 2>$null
if ($LASTEXITCODE -ne 0) { $torchState = "none" }
$wanted = "cpu"
if ($hasGpu) { $wanted = "cuda" }
if ($torchState -eq $wanted -and -not $ReinstallTorch) {
    Ok "PyTorch 이미 설치됨 ($torchState)"
} else {
    if ($torchState -ne "none") { & $venvPython -m pip uninstall -y -q torch torchvision | Out-Null }
    if ($hasGpu) {
        $installed = $false
        foreach ($idx in $TorchIndexes) {
            Write-Host "  GPU용 PyTorch 설치 중 (2~3GB, 몇 분 걸립니다): $idx"
            & $venvPython -m pip install --disable-pip-version-check torch torchvision --index-url $idx
            if ($LASTEXITCODE -eq 0) { $installed = $true; break }
        }
        if (-not $installed) { Fail "GPU용 PyTorch 설치에 실패했습니다. NVIDIA 드라이버를 최신으로 업데이트하거나 setup.bat -Cpu 로 CPU 모드 설치를 하세요." }
    } else {
        Pip torch torchvision
    }
    Ok "PyTorch 설치"
}

# 4) 패키지 ---------------------------------------------------------------------
Info "[4/7] 필수·AI 패키지 설치"
Pip -q -r (Join-Path $root "requirements.txt") -r (Join-Path $root "requirements-ml.txt")
Pip -q --upgrade yt-dlp
Pip -q -e $root --no-deps
Ok "패키지 설치"

# 5) FFmpeg ------------------------------------------------------------------------
Info "[5/7] FFmpeg 확인"
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Ok "FFmpeg 있음"
} elseif (Get-Command winget -ErrorAction SilentlyContinue) {
    $answer = Read-Host "  FFmpeg가 없습니다. winget으로 설치할까요? (Y/n)"
    if ($answer -eq "" -or $answer -match "^[Yy]") {
        & winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
        if (Get-Command ffmpeg -ErrorAction SilentlyContinue) { Ok "FFmpeg 설치" }
        else { Warn "FFmpeg를 설치했지만 이 창에서는 아직 보이지 않습니다. 창을 닫고 setup.bat을 다시 실행하세요." }
    } else { Warn "FFmpeg 없이 진행합니다 (영상 렌더링이 안 됩니다)" }
} else {
    Warn "FFmpeg가 없습니다. https://www.gyan.dev/ffmpeg/builds/ 에서 받아 PATH에 추가하거나, config.local.yaml에 ffmpeg_path를 적으세요."
}

# 6) 폰트 ---------------------------------------------------------------------------
Info "[6/7] 폰트 내려받기"
& $venvPython -m ssm fonts
if ($LASTEXITCODE -ne 0) { Warn "폰트를 받지 못했습니다. 인터넷 연결 후 ssm.bat fonts 를 실행하세요." }

# 7) 점검 ---------------------------------------------------------------------------
Info "[7/7] 설치 점검 (ssm doctor)"
& $venvPython -m ssm doctor
$doctorCode = $LASTEXITCODE
Write-Host ""
if ($doctorCode -eq 0) {
    Write-Host "설치가 끝났습니다. 이 폴더에서 Claude Code를 열고 '쇼츠 만들어줘'라고 말하거나, ssm.bat 으로 직접 명령을 쓸 수 있습니다." -ForegroundColor Green
} else {
    Fail "점검에서 실패한 항목이 있습니다. 위 안내대로 고친 뒤 setup.bat을 다시 실행하세요."
}
