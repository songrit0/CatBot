@echo off
echo.
echo ========================================
echo   Discord Stock Bot Setup Script
echo ========================================
echo.

echo [1/4] Installing Python packages...
pip install -r requirements.txt

echo.
echo [2/4] Checking credentials.json...
if exist credentials.json (
    echo ✅ credentials.json found!
) else (
    echo ❌ credentials.json not found!
    echo Please download your Google Service Account credentials as 'credentials.json'
    echo and place it in this directory.
    pause
    exit /b 1
)

echo.
echo [3/4] Checking environment variables...
if exist .env (
    echo ✅ .env file found!
) else (
    echo ❌ .env file not found!
    echo Please create .env file with your configuration.
    pause
    exit /b 1
)

echo.
echo [4/4] Setup complete!
echo.
echo To run the bot:
echo   python bot.py
echo.
pause
