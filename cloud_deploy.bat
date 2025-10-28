@echo off
setlocal

REM Set your GCP project ID and region
set PROJECT_ID=gen-lang-client-0006062814
set REGION=europe-central2

echo Building Docker image...
docker build -t expenses-bot .

echo.
echo Configuring Docker for Google Container Registry...
gcloud auth configure-docker

echo.
echo Tagging Docker image for GCP...
docker tag expenses-bot gcr.io/%PROJECT_ID%/expenses-bot

echo.
echo Pushing image to Google Container Registry...
docker push gcr.io/%PROJECT_ID%/expenses-bot

echo.
echo Deploying to Cloud Run...
gcloud run deploy expenses-bot ^
    --image gcr.io/%PROJECT_ID%/expenses-bot ^
    --platform managed ^
    --region %REGION% ^
    --allow-unauthenticated

echo.
echo Deployment complete!
echo Press any key to exit...
pause > nul