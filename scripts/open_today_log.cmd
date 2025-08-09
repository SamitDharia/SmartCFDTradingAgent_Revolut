@echo off
setlocal
cd /d C:\Projects\SmartCFDTradingAgent_Revolut
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set D=%%i
notepad SmartCFDTradingAgent\logs\%D%.log
endlocal
