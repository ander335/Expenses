@echo off

REM Read environment variables from .env file
for /f "tokens=*" %%a in (.env) do (
    set %%a
)

REM Check for Google Cloud credentials
if not defined GOOGLE_APPLICATION_CREDENTIALS (
    echo ERROR: GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.
    echo Please set it to point to your Google Cloud service account key file.
    echo Example: set GOOGLE_APPLICATION_CREDENTIALS=path\to\service-account-key.json
    pause
    exit /b 1
)

REM Run the Python script using virtual environment Python
g:\projects\Expenses\.venv\Scripts\python.exe expenses.py

pause