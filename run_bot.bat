@echo off
TITLE FRIXO Proxy Discord Bot
COLOR 0B
echo [*] Checking and installing required dependencies...
pip install -r requirements.txt
cls
echo [*] Launching FRIXO Proxy Discord Bot...
python discord_bot.py
pause
