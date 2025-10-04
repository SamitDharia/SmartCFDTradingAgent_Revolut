@echo off
setlocal
pushd %~dp0\..
if not exist venv\Scripts\python.exe (
  echo Virtualenv missing. Please run python -m venv venv && exit /b 1
)
set SKIP_SSL_VERIFY=1
set TELEGRAM_SKIP_VERIFY=1
rem Prefer Alpaca crypto data for intraday backfill when credentials are available
if defined ALPACA_API_KEY set USE_ALPACA_CRYPTO=1
if defined APCA_API_KEY_ID set USE_ALPACA_CRYPTO=1
"venv\Scripts\python.exe" scripts\human_digest.py --to-telegram --email %*
popd
