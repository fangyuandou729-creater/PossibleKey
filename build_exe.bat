@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m PyInstaller --clean --noconsole --onefile --uac-admin --name PossibleKey --hidden-import keyboard._winkeyboard --hidden-import mouse._winmouse PossibleKey.py
) else (
  python -m PyInstaller --clean --noconsole --onefile --uac-admin --name PossibleKey --hidden-import keyboard._winkeyboard --hidden-import mouse._winmouse PossibleKey.py
)
pause
