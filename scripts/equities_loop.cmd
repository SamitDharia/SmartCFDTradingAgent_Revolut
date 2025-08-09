@echo off
cd /d %~dp0\..
call venv\Scripts\activate
set "CURL_CA_BUNDLE="
set "YF_DISABLE_CURL=1"
python -m SmartCFDTradingAgent.pipeline --config configs\equities.yml --profile equities_daily %*
