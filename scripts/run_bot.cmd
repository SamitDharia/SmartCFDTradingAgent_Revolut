@echo off
setlocal enabledelayedexpansion
cd /d %~dp0\..

REM Optionally activate virtual environment
if not defined VIRTUAL_ENV (
  if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
  )
)

REM Ensure Python is available
where python >nul 2>&1
if errorlevel 1 (
  echo Python could not be located. Please install Python or ensure it is on your PATH.
  exit /b 1
)

set "CURL_CA_BUNDLE="
set "YF_DISABLE_CURL=1"
python -m SmartCFDTradingAgent.pipeline %*
endlocal
