@echo off
setlocal
pushd %~dp0\..
if not exist venv\Scripts\python.exe (
  echo Virtualenv missing. Please run python -m venv venv && exit /b 1
)
"venv\Scripts\python.exe" -m SmartCFDTradingAgent.pipeline --show-decisions 10 --to-telegram %*
popd
