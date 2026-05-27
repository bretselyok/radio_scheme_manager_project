@echo off
REM Сборка exe выполняется на Windows, потому что PyInstaller собирает исполняемый файл под текущую ОС.
python -m pip install --upgrade pip
python -m pip install pyinstaller==6.10.0
pyinstaller --noconfirm --onefile --windowed --name RadioSchemeManager main.py
pause
