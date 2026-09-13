@echo off
TITLE FRIXO Proxy Scraper & Checker
COLOR 0B
echo [*] Checking and installing required dependencies...
pip install -r requirements.txt
cls
echo [*] Launching FRIXO Proxy Tool...
python proxy.py
pause