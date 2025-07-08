@echo off
echo.
echo ========================================
echo   Starting Discord Stock Bot
echo ========================================
echo.

echo Checking Python...
python --version
if %errorlevel% neq 0 (
    echo ❌ Python not found! Please install Python first.
    pause
    exit /b 1
)

echo.
echo Checking dependencies...
pip show discord.py >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Dependencies not installed! Run setup.bat first.
    pause
    exit /b 1
)

echo.
echo Starting bot...
python bot.py

pause
