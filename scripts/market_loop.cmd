@echo off
setlocal
cd /d C:\Projects\SmartCFDTradingAgent_Revolut

REM Activate venv
call venv\Scripts\activate

REM Run equities during market window (Sharpe top-4, cap 2 suggestions)
REM You can tweak symbols/ADX/interval as you like.
scripts\run_bot.cmd --watch SPY QQQ DIA IWM --size 4 --interval 1d --adx 15 --max-trades 2 --grace 120 --risk 0.01 --equity 1000

endlocal
