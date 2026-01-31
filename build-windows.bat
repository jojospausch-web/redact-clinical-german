@echo off
REM Build script for Windows PyInstaller executable

echo Building standalone executable for Windows...

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>NUL
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Create the executable
pyinstaller --onefile ^
    --name redact-clinical ^
    --add-data "templates;templates" ^
    src/main.py

echo.
echo Build completed!
echo Executable location: dist\redact-clinical.exe
echo.
echo To test:
echo   dist\redact-clinical.exe input.pdf --output anonymized.pdf
pause
