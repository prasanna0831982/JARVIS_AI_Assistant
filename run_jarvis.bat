@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo JARVIS environment not found. Please follow README.md setup first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" desktop.py
pause
