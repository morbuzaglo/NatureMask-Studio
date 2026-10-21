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

rem Keep Python's bytecode cache out of OneDrive: __pycache__ synced from another computer arrives as
rem cloud-only placeholders that can hang the import forever.
set "PYTHONPYCACHEPREFIX=%LOCALAPPDATA%\NatureMask-Studio\pycache"

rem --- one-time setup -------------------------------------------------------------
rem A .venv synced from another computer (OneDrive) points to a Python that does not exist here:
rem test that it actually runs and is new enough, otherwise rebuild it.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; sys.exit(sys.version_info < (3, 11))" >NUL 2>NUL
  if errorlevel 1 (
    echo The Python environment in .venv was made on another computer or is broken - rebuilding it.
    rmdir /s /q ".venv"
  )
)
if not exist ".venv\Scripts\python.exe" (
  set PYEXE=
  for %%V in (3.13 3.12 3.11) do (
    if not defined PYEXE (
      py -%%V -c "import sys" >NUL 2>NUL
      if not errorlevel 1 set "PYEXE=py -%%V"
    )
  )
  if not defined PYEXE (
    python -c "import sys; sys.exit(sys.version_info < (3, 11))" >NUL 2>NUL
    if not errorlevel 1 set "PYEXE=python"
  )
  if not defined PYEXE (
    echo Python 3.11 or newer is required ^(3.12 recommended^): https://www.python.org/downloads/
    echo   or run:  winget install Python.Python.3.12
    pause
    exit /b 1
  )
  echo [1/3] Creating the Python environment with !PYEXE! ^(one time^)...
  !PYEXE! -m venv .venv || goto :err
)
".venv\Scripts\python.exe" -c "import fastapi, uvicorn, numpy, scipy, soundfile, h5py, pandas" >NUL 2>NUL
if errorlevel 1 (
  echo [1/3] Installing Python packages ^(one time, a few minutes^)...
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
