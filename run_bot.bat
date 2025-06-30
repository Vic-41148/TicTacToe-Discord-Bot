@echo off
cd /d "%~dp0"
for /f "usebackq tokens=* delims=" %%i in (`type .env`) do set %%i
python bot.py
