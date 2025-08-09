@echo off
setlocal
cd /d C:\Projects\SmartCFDTradingAgent_Revolut
for /f "delims=" %%F in ('dir /b /o:-d SmartCFDTradingAgent\logs\*.log') do ( set LATEST=%%F & goto X )
:X
if not defined LATEST (
  echo No log files found.
) else (
  notepad SmartCFDTradingAgent\logs\%LATEST%
)
endlocal
