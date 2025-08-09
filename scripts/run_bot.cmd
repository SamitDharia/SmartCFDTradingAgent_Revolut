@echo off
setlocal enabledelayedexpansion
cd /d %~dp0\..
if not defined VIRTUAL_ENV (
  if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
)
set "CURL_CA_BUNDLE="
set "YF_DISABLE_CURL=1"
python -m SmartCFDTradingAgent.pipeline %*
endlocal
