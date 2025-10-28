@echo off
setlocal

REM Set your GCP project ID and region
set PROJECT_ID=gen-lang-client-0006062814
set REGION=europe-central2
set REPOSITORY=europe-central2-docker.pkg.dev/%PROJECT_ID%/expenses-bot

echo Building Docker image...
docker build -t expenses-bot .

echo.
REM echo Configuring authentication...
REM call gcloud auth activate-service-account --key-file=auth_data/gen-lang-client-0006062814-5e5e4e1479fc.json

echo.
REM echo Configuring Docker for Google Container Registry...
REM call gcloud auth configure-docker %REGION%-docker.pkg.dev --quiet

echo.
echo Tagging Docker image for GCP...
docker tag expenses-bot %REPOSITORY%/expenses-bot

echo.
echo Pushing image to Google Artifact Registry...
docker push %REPOSITORY%/expenses-bot

echo.
echo Deploying to Cloud Run Job...
call gcloud run jobs update expenses-bot ^
    --image %REPOSITORY%/expenses-bot ^
    --project %PROJECT_ID% ^
    --region %REGION% ^
    --set-secrets=TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest ^
    --max-retries=0 ^
    --parallelism=1 ^
    --task-timeout=3600

echo.
echo Executing the Cloud Run Job...
call gcloud run jobs execute expenses-bot ^
    --project %PROJECT_ID% ^
    --region %REGION%

echo.
echo Deployment complete!
echo Press any key to exit...
pause > nul