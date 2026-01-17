@echo off
setlocal enabledelayedexpansion

REM Usage: cloud_deploy.bat [--skip-build | -s]
REM   --skip-build, -s : Skip Docker image build and push, deploy existing image
REM   (default)        : Build Docker image, push to registry, then deploy

REM Parse command line arguments
set SKIP_BUILD=false
if "%1"=="--skip-build" set SKIP_BUILD=true
if "%1"=="-s" set SKIP_BUILD=true

echo Deploying to Cloud Run Service...

REM Set your GCP project ID and region
set PROJECT_ID=gen-lang-client-0006062814
set REGION=europe-central2
set REPOSITORY=europe-central2-docker.pkg.dev/%PROJECT_ID%/expenses-bot
set AI_PROVIDER=gemini

echo.
REM echo Configuring authentication...
REM gcloud auth activate-service-account --key-file=c:\Users\user\Downloads\gen-lang-client-0006062814-3a6b19bf0387.json

echo.
REM echo Configuring Docker for Google Container Registry...
REM gcloud auth configure-docker %REGION%-docker.pkg.dev --quiet

if "%SKIP_BUILD%"=="false" (
    echo Checking Docker service status...
    docker info >nul 2>&1
    if !errorlevel! neq 0 (
        echo ERROR: Docker service is not running or not accessible.
        echo Please start Docker Desktop and ensure Docker service is running.
        exit /b 1
    )
    echo Docker service is running.

    echo.
    echo Building Docker image...
    docker build -t expenses-bot .

    echo.
    echo Tagging Docker image for GCP...
    docker tag expenses-bot %REPOSITORY%/expenses-bot

    echo.
    echo Pushing image to Google Artifact Registry...
    docker push %REPOSITORY%/expenses-bot
) else (
    echo Skipping Docker image build and push...
)

REM Deploy to Cloud Run Service
echo.
echo Deploying to Cloud Run Service...
call gcloud run deploy expenses-bot ^
    --image %REPOSITORY%/expenses-bot ^
    --project %PROJECT_ID% ^
    --region %REGION% ^
    --set-secrets=TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest ^
    --set-env-vars=USE_WEBHOOK=true,TELEGRAM_ADMIN_ID=98336105,AI_PROVIDER=%AI_PROVIDER% ^
    --platform managed ^
    --allow-unauthenticated ^
    --port 8080 ^
    --cpu 1 ^
    --memory 512Mi ^
    --min-instances 0 ^
    --max-instances 1

echo.
echo Ensuring all traffic points to the latest revision...
call gcloud run services update-traffic expenses-bot --project=%PROJECT_ID% --region=%REGION% --to-latest
if %errorlevel% neq 0 (
    echo WARNING: Failed to update traffic to the latest revision.
)

echo.
echo Cleaning up old revisions...
echo Keeping only the latest revision and deleting all others...
set /a count=0
for /f "tokens=* usebackq" %%r in (`gcloud run revisions list --service expenses-bot --project^=%PROJECT_ID% --region^=%REGION% --format^="value(metadata.name)" --sort-by^="~metadata.creationTimestamp"`) do (
    set /a count+=1
    if !count! gtr 1 (
        echo Deleting old revision %%r
        call gcloud run revisions delete %%r --project=%PROJECT_ID% --region=%REGION% --quiet
    ) else (
        echo Keeping latest revision %%r
    )
)

echo.
echo Deployment complete at %DATE% %TIME%!