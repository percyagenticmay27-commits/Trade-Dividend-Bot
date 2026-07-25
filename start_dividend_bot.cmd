@echo off
setlocal
cd /d %~dp0
if "%DIVIDEND_BOT_ENV%"=="" set DIVIDEND_BOT_ENV=paper
python run_daily_paper_cycle.py
endlocal
