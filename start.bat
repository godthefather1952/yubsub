@echo off
cd /d "%~dp0"
where python >nul 2>nul || (echo Python 3.10+ is required. Install from python.org & pause & exit /b 1)
where ffmpeg >nul 2>nul || (echo FFmpeg missing. Try: winget install ffmpeg & pause & exit /b 1)
where deno >nul 2>nul
if errorlevel 1 (
  where node >nul 2>nul
  if errorlevel 1 (
    echo A JavaScript runtime is required. Install Deno 2.3+ from deno.com or Node 22+.
    pause
    exit /b 1
  )
)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -U -r requirements.txt
echo Open http://localhost:5000 in your browser.
python app.py
pause
