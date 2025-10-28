@echo off

REM Read environment variables from .env file
for /f "tokens=*" %%a in (.env) do (
    set %%a
)

REM Run the Python script using virtual environment Python
g:\projects\Expenses\.venv\Scripts\python.exe expenses.py

pause