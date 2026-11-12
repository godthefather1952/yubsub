@echo off
cd /d "%~dp0"
where python >nul 2>nul || (echo Python is not installed. Get it from python.org & pause & exit /b 1)
where ffmpeg >nul 2>nul || (echo ffmpeg missing. Run: winget install ffmpeg  then reopen this window & pause & exit /b 1)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
pip install -q -U -r requirements.txt
start "" http://localhost:5000
python app.py
pause
