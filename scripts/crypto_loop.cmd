@echo off
setlocal
pushd %~dp0\..
if not exist venv\Scripts\python.exe (
  echo Virtualenv missing. Please run python -m venv venv && exit /b 1
)
set SKIP_SSL_VERIFY=1
set TELEGRAM_SKIP_VERIFY=1
set PYTHONHTTPSVERIFY=0
set CURL_CA_BUNDLE=
set REQUESTS_CA_BUNDLE=
set USE_ALPACA_CRYPTO=1
"venv\Scripts\python.exe" -m SmartCFDTradingAgent.pipeline --config configs\crypto.yml --profile crypto_1h --broker alpaca --use-params --ml-blend auto --ml-threshold 0.65 --budget-mode auto --retrain-on-dry-run --retrain-interval-hours 4 %*
popd
REM Keep window open when run manually (set NO_PAUSE=1 to skip)
if not defined NO_PAUSE pause
