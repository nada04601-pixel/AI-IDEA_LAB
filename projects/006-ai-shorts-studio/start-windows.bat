@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title AI Shorts Studio

echo ============================================
echo   AI Shorts Studio 실행 - Windows
echo ============================================
echo.

rem ---- 1. 필요한 프로그램 확인 ----
set "PY="
where py >nul 2>nul && set "PY=py -3"
if defined PY goto :have_python
where python >nul 2>nul && set "PY=python"
if defined PY goto :have_python
echo [오류] Python을 찾을 수 없습니다.
echo        PowerShell에서 winget install Python.Python.3.12 를 실행한 뒤
echo        이 창을 닫고 다시 실행하세요.
goto :fail
:have_python

where npm >nul 2>nul
if errorlevel 1 goto :no_node
goto :have_node
:no_node
echo [오류] Node.js를 찾을 수 없습니다.
echo        PowerShell에서 winget install OpenJS.NodeJS.LTS 를 실행한 뒤
echo        이 창을 닫고 다시 실행하세요.
goto :fail
:have_node

where ffmpeg >nul 2>nul
if errorlevel 1 echo [주의] FFmpeg가 없습니다. 영상 생성과 MP4 렌더링만 안 되고 나머지는 동작합니다.
if errorlevel 1 echo        설치: PowerShell에서 winget install Gyan.FFmpeg

rem ---- 2. 백엔드 패키지 - 처음에는 가상환경을 만들고, 매번 빠진 패키지만 설치 ----
if exist "backend\.venv\Scripts\python.exe" goto :venv_ready
echo [설치] 백엔드 가상환경을 만드는 중입니다. 처음 한 번만 합니다...
%PY% -m venv backend\.venv
if errorlevel 1 goto :fail
:venv_ready
echo [확인] 백엔드 패키지...
"backend\.venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r backend\requirements-dev.txt
if errorlevel 1 goto :fail

rem ---- 3. 프런트엔드 패키지 ----
echo [확인] 화면 패키지... 처음에는 몇 분 걸립니다.
pushd frontend
call npm install --no-audit --no-fund --loglevel=error
set "NPM_ERR=%errorlevel%"
popd
if not "%NPM_ERR%"=="0" goto :fail

rem ---- 4. 영상 자막 글꼴 - 한글이 네모로 보이지 않게 맑은 고딕 사용 ----
if not defined AISS_SUBTITLE_FONT set "AISS_SUBTITLE_FONT=Malgun Gothic"

rem ---- 5. 서버 두 개를 각각 새 창에서 실행 ----
echo [실행] 백엔드와 화면 서버를 새 창 두 개로 엽니다.
start "AI Shorts Studio - 백엔드 8000" /d "%~dp0backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
start "AI Shorts Studio - 화면 3000" /d "%~dp0frontend" cmd /k "npm run dev"

rem ---- 6. 준비되면 브라우저 열기 ----
echo [대기] 서버가 준비될 때까지 기다리는 중입니다...
set /a TRIES=0
:wait
timeout /t 2 /nobreak >nul
curl -s -o nul http://localhost:8000/api/health
if errorlevel 1 goto :not_yet
curl -s -o nul http://localhost:3000
if errorlevel 1 goto :not_yet
goto :ready
:not_yet
set /a TRIES+=1
if %TRIES% lss 90 goto :wait
echo [주의] 3분이 지나도 서버가 응답하지 않습니다. 새로 열린 두 창의 오류 메시지를 확인하세요.
goto :done

:ready
start "" http://localhost:3000
echo.
echo ============================================
echo   준비 완료: 브라우저에서 http://localhost:3000
echo.
echo   끝낼 때는 새로 열린 두 창을 닫으세요.
echo   이 창은 닫아도 됩니다.
echo ============================================
goto :done

:fail
echo.
echo 문제가 생겨 멈췄습니다. 위 메시지를 확인하세요.
pause
exit /b 1

:done
pause
exit /b 0
