@echo off
cd /d %~dp0..
echo Starting IV Test UI...
.\venv310\Scripts\python.exe -m streamlit run ui/app.py --server.port 8501
pause
