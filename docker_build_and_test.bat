@echo off
echo Building Docker image...
docker build -t expenses-bot .

echo.
echo Testing Docker image locally...
docker run --env-file .env expenses-bot

echo.
echo Press any key to exit...
pause > nul