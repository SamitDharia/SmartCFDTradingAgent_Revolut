@echo off
setlocal
pushd %~dp0\..
if not exist venv\Scripts\python.exe (
  echo Virtualenv missing. Please run python -m venv venv && exit /b 1
)
set SKIP_SSL_VERIFY=1
set TELEGRAM_SKIP_VERIFY=1
set TELEGRAM_BOT_TOKEN=%TELEGRAM_BOT_TOKEN%
set TELEGRAM_CHAT_ID=%TELEGRAM_CHAT_ID%
set ALPACA_API_KEY=%ALPACA_API_KEY%
set ALPACA_API_SECRET=%ALPACA_API_SECRET%
set APCA_API_BASE_URL=%APCA_API_BASE_URL%
"venv\Scripts\python.exe" -m SmartCFDTradingAgent.pipeline --config configs/equities.yml --profile equities_daily --broker alpaca %*
popd
