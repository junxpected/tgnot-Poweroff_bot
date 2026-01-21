@echo off
cd /d %~dp0
set BOT_TOKEN=PASTE_YOUR_BOT_TOKEN_HERE
start /b python -m app.bot
