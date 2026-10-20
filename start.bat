@echo off
setlocal
cd /d "%~dp0"
title NatureMask Studio

where python >/dev/null 2>nul
if errorlevel 1 (
  echo Python 3.10 or newer is required: https://www.python.org/downloads/
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating the Python environment ^(one time^)...
  python -m venv .venv || goto :err
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :err
)

if not exist "frontend\dist\index.html" (
  echo [2/3] Building the interface ^(one time, needs Node.js LTS^)...
  where npm >/dev/null 2>nul
  if errorlevel 1 (
    echo Node.js LTS is required once to build the interface: https://nodejs.org/
    pause
    exit /b 1
  )
  pushd frontend
  call npm install --no-audit --no-fund || (popd ^& goto :err)
  call npm run build || (popd ^& goto :err)
  popd
)

echo [3/3] Starting NatureMask Studio at http://127.0.0.1:8765  ^(close this window to stop^)
start "" cmd /c "timeout /t 3 /nobreak >/dev/null & start http://127.0.0.1:8765"
".venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8765
goto :eof

:err
echo.
echo Setup failed - see the messages above.
pause
exit /b 1
