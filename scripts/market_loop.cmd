@echo off
setlocal enabledelayedexpansion
cd /d %~dp0\..

set LOGFILE=market_loop.log

REM Optionally activate virtual environment
if not defined VIRTUAL_ENV (
  if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
)

REM Ensure Python is available
where python >nul 2>&1
if errorlevel 1 (
  echo Python could not be located. Please install Python or ensure it is on your PATH.
  exit /b 1
)

REM Run equities during market window (Sharpe top-4, cap 2 suggestions)
REM You can tweak symbols/ADX/interval as you like.
set ARGS=--watch SPY QQQ DIA IWM --size 4 --interval 1d --adx 15 --max-trades 2 --grace 120 --risk 0.01 --equity 1000
scripts\run_bot.cmd %ARGS% %* >> %LOGFILE% 2>&1

endlocal
