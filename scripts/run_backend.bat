@echo off
cd /d %~dp0..
echo Starting IV Test Backend...
.\.venv\Scripts\python.exe -m uvicorn ivtest.main:app --host 0.0.0.0 --port 5000 --reload
pause
