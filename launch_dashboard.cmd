@echo off
setlocal
pushd %~dp0
if not exist venv\Scripts\python.exe (
  echo Virtualenv missing. Please run python -m venv venv && exit /b 1
)
start "SmartCFD Dashboard" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && streamlit run apps\dashboard.py"
popd
