@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title NatureMask Studio

rem --- find NatureMask if it is already running, otherwise the first free port 8765..8775 -----
set PORT=
for /L %%P in (8765,1,8775) do (
  if not defined PORT (
    curl -s -m 3 http://127.0.0.1:%%P/api/health 2>NUL | findstr /C:"NatureMask" >NUL
    if not errorlevel 1 (
      echo NatureMask Studio is already running on port %%P - opening it in the browser.
      start "" http://127.0.0.1:%%P
      exit /b 0
    )
    netstat -ano | findstr /R /C:"127.0.0.1:%%P .*LISTENING" /C:"0.0.0.0:%%P .*LISTENING" >NUL
    if errorlevel 1 (
      set PORT=%%P
    ) else (
      echo Port %%P is used by another program - trying the next one.
    )
  )
)
if not defined PORT (
  echo No free port between 8765 and 8775. Close some programs and try again.
  pause
  exit /b 1
)

rem --- one-time setup -------------------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
  where python >NUL 2>NUL
  if errorlevel 1 (
    echo Python 3.10 or newer is required: https://www.python.org/downloads/
    pause
    exit /b 1
  )
  echo [1/3] Creating the Python environment ^(one time^)...
  python -m venv .venv || goto :err
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :err
)

if not exist "frontend\dist\index.html" (
  echo [2/3] Building the interface ^(one time, needs Node.js LTS^)...
  where npm >NUL 2>NUL
  if errorlevel 1 (
    echo Node.js LTS is required once to build the interface: https://nodejs.org/
    pause
    exit /b 1
  )
  pushd frontend
  call npm install --no-audit --no-fund || (popd & goto :err)
  call npm run build || (popd & goto :err)
  popd
)

rem --- run ----------------------------------------------------------------------------
echo [3/3] Starting NatureMask Studio at http://127.0.0.1:%PORT%  (close this window to stop)
start "" cmd /c "timeout /t 4 /nobreak >NUL & start http://127.0.0.1:%PORT%"
if not exist "data\logs" mkdir "data\logs"
echo %DATE% %TIME% starting on port %PORT% > "data\logs\start.log"
".venv\Scripts\python.exe" -c "import sys, fastapi, uvicorn, numpy, scipy, soundfile; print('python', sys.version.split()[0], 'ok')" >> "data\logs\start.log" 2>&1
if errorlevel 1 (
  type "data\logs\start.log"
  echo.
  echo The Python environment is incomplete. Delete the .venv folder and run start.bat again.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port %PORT%
echo.
echo NatureMask Studio has stopped (exit code %ERRORLEVEL%). If this was unexpected, the messages above explain why.
pause
goto :eof

:err
echo.
echo Setup failed - see the messages above.
pause
exit /b 1
