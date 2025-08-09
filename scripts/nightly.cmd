@echo off
setlocal
cd /d C:\Projects\SmartCFDTradingAgent_Revolut
call venv\Scripts\activate

rem Walk-forward (equities per-ticker, daily)
python -m SmartCFDTradingAgent.walk_forward --watch SPY QQQ DIA IWM --interval 1d --years 3 --train-months 6 --test-months 1 --per-ticker

rem Walk-forward (crypto per-ticker, hourly)
python -m SmartCFDTradingAgent.walk_forward --watch BTC-USD ETH-USD --interval 1h --years 1 --train-months 3 --test-months 1 --per-ticker

rem Daily summary to Telegram
python -m SmartCFDTradingAgent.pipeline --daily-summary --tz Europe/Dublin

endlocal
