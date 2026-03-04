@echo off
echo ========================================
echo Starting BS Finance Client Management
echo ========================================
echo.

REM Check if virtual environment exists, if not create it
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Create uploads folder if it doesn't exist
if not exist "uploads" mkdir uploads

REM Run the Flask app
echo.
echo Starting Flask server...
echo Server will be available at: http://127.0.0.1:5000
echo Press Ctrl+C to stop the server
echo.
python app.py

REM Deactivate virtual environment when app closes
deactivate
