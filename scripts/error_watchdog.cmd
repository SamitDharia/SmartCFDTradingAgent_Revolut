@echo off
setlocal
pushd %~dp0\..
if not exist venv\Scripts\python.exe (
  echo Virtualenv missing. Please run python -m venv venv && exit /b 1
)
set SKIP_SSL_VERIFY=1
set TELEGRAM_SKIP_VERIFY=1
"venv\Scripts\python.exe" scripts\error_watchdog.py %*
popd
