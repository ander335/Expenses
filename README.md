

- Before running the bot, make sure to set up Google Cloud Storage:
  1. Create a Google Cloud project and enable Cloud Storage API
  2. Create a storage bucket and note its name
  3. Set up authentication credentials (service account key) and set the GOOGLE_APPLICATION_CREDENTIALS environment variable
  4. Update the BUCKET_NAME variable in db.py with your bucket name