@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PY_SCRIPT=%SCRIPT_DIR%speedtest.py"

:: 1. Check local python in .local\bin
if exist "%USERPROFILE%\.local\bin\python.exe" (
    "%USERPROFILE%\.local\bin\python.exe" "%PY_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

if exist "%USERPROFILE%\.local\bin\python3.12.exe" (
    "%USERPROFILE%\.local\bin\python3.12.exe" "%PY_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

if exist "%USERPROFILE%\AppData\Roaming\uv\python\cpython-3.12.16-windows-x86_64-none\python.exe" (
    "%USERPROFILE%\AppData\Roaming\uv\python\cpython-3.12.16-windows-x86_64-none\python.exe" "%PY_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

:: 2. Check uv
where uv >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    uv run python "%PY_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

:: 3. Check py launcher
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 "%PY_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

:: 4. Check python in PATH
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python "%PY_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

echo [ERROR] Python 3 was not found. Please install Python or run:
echo   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
exit /b 1
