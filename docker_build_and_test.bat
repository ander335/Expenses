@echo off
echo Building Docker image...
docker build -t expenses-bot .

echo.
echo Testing Docker image locally with mounted auth_data...
docker run -v "%cd%/auth_data:/app/auth_data" --env-file .env expenses-bot

echo.
echo Press any key to exit...
pause > nul