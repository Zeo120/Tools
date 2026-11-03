@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PY_SCRIPT=%SCRIPT_DIR%server.py"

if exist "%USERPROFILE%\.local\bin\python.exe" (
    "%USERPROFILE%\.local\bin\python.exe" "%PY_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

if exist "%USERPROFILE%\.local\bin\python3.12.exe" (
    "%USERPROFILE%\.local\bin\python3.12.exe" "%PY_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

where uv >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    uv run python "%PY_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 "%PY_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python "%PY_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

echo [ERROR] Python 3 was not found.
exit /b 1
