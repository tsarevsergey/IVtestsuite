@echo off
cd /d %~dp0..
echo Opening IV Test HTML UI...
start "" "%cd%\ui2\index.html"
