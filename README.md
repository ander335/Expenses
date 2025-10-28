
# Expenses Bot
ProjectId = gen-lang-client-0006062814

## Local Setup
- Before running the bot, make sure to set up Google Cloud Storage:
  1. Create a Google Cloud project and enable Cloud Storage API
  2. Create a storage bucket and note its name
  3. Set up authentication credentials (service account key) and set the GOOGLE_APPLICATION_CREDENTIALS environment variable
  4. Update the BUCKET_NAME variable in db.py with your bucket name

## Deploying to Google Cloud Platform (GCP)

### Prerequisites
- Install Google Cloud SDK
- Install Docker Desktop
- Have a Google Cloud Project created
- Enable the following APIs in your GCP project:
  - Cloud Run API
  - Container Registry API
  - Cloud Build API

### Deployment Steps

1. **Prepare the Environment Variables**
   Create a `.env` file with your configuration, check .env.example
   ```

2. **Build and Test Docker Image Locally**
   
   You can build and test the Docker image in two ways:

   **Option 1:** Run the provided batch file:
   ```powershell
   .\docker_build_and_test.bat
   ```

   **Option 2:** Run commands manually:
   ```powershell
   # Build the Docker image
   docker build -t expenses-bot .

   # Test the image locally
   docker run --env-file .env expenses-bot
   ```

3. **Deploy to Google Cloud Run**
   
   You can deploy to Google Cloud Run in two ways:

   **Option 1:** Run the provided deployment script:
   ```powershell
   .\cloud_deploy.bat
   ```
   The script will automatically:
   - Build the Docker image
   - Configure Docker for GCR
   - Tag and push the image
   - Deploy to Cloud Run

   **Option 2:** Run commands manually:
   ```powershell
   # Configure Docker to use Google Container Registry
   gcloud auth configure-docker

   # Tag the image for Google Container Registry
   docker tag expenses-bot gcr.io/[PROJECT-ID]/expenses-bot

   # Push the image to Google Container Registry
   docker push gcr.io/[PROJECT-ID]/expenses-bot

   # Deploy to Cloud Run
   gcloud run deploy expenses-bot `
     --image gcr.io/[PROJECT-ID]/expenses-bot `
     --platform managed `
     --region [REGION] `
     --allow-unauthenticated
   ```

4. **Configure Environment Variables in Cloud Run**
   - Go to the Cloud Run console
   - Select your deployed service
   - Click "Edit & Deploy New Revision"
   - Add your environment variables:
     - `TELEGRAM_BOT_TOKEN`
     - Add any other configuration variables needed

5. **Set up Service Account and Permissions**
   - Create a service account for your bot
   - Grant necessary permissions (Storage Object Viewer, etc.)
   - Download the JSON key and store it securely
   - Add the service account key as a secret in Cloud Run

6. **Monitoring and Logs**
   - Monitor your bot using Cloud Run dashboard
   - View logs in Cloud Logging
   - Set up alerts if needed

### Security Notes
1. Never commit sensitive information like API keys or tokens to your repository
2. Use Cloud Run's built-in secret management for sensitive data
3. Follow the principle of least privilege when setting up service account permissions

### Cost Optimization
- Cloud Run charges only for the actual compute time used
- Set appropriate memory and CPU limits
- Monitor usage and adjust resources as needed

### Important Notes
- Replace `[PROJECT-ID]` and `[REGION]` in the commands with your actual GCP project ID and preferred region
- The bot will need to be modified to read environment variables instead of local files for configuration
- Ensure your service account has the necessary permissions to access Cloud Storage and other GCP services