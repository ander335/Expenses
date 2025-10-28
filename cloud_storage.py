from google.cloud import storage
import os
from datetime import datetime, timedelta
from logger_config import logger

class CloudStorage:
    def __init__(self, bucket_name):
        """Initialize CloudStorage with bucket name."""
        self.bucket_name = bucket_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.last_upload_time = None
        self.local_db_path = 'expenses.db'
        self.last_modified_time = None

    def download_db(self):
        """Download the database file from cloud storage."""
        try:
            # Check if local file exists
            if os.path.exists(self.local_db_path):
                logger.info("Local database file exists and will be overwritten")
            
            blob = self.bucket.blob('expenses.db')
            blob.download_to_filename(self.local_db_path)
            logger.info("Successfully downloaded database from cloud storage")
            # Store the current modification time
            self.last_modified_time = os.path.getmtime(self.local_db_path)
        except Exception as e:
            if 'Not Found' in str(e):
                logger.warning("Database file not found in cloud storage. Will create new one locally.")
            else:
                logger.error(f"Error downloading database: {str(e)}")
            return False
        return True

    def check_and_upload_db(self):
        """Check if database was modified and needs to be uploaded."""
        if not os.path.exists(self.local_db_path):
            logger.warning("Local database file not found")
            return False

        current_modified_time = os.path.getmtime(self.local_db_path)
        
        # Check if file was modified since last check
        if self.last_modified_time is None or current_modified_time > self.last_modified_time:
            try:
                blob = self.bucket.blob('expenses.db')
                blob.upload_from_filename(self.local_db_path)
                self.last_modified_time = current_modified_time
                self.last_upload_time = datetime.now()
                logger.info("Successfully uploaded database to cloud storage")
                return True
            except Exception as e:
                logger.error(f"Error uploading database: {str(e)}")
                return False

        return False

    def should_upload(self):
        """Check if it's time for daily upload."""
        if self.last_upload_time is None:
            return True
        
        now = datetime.now()
        return (now - self.last_upload_time) >= timedelta(days=1)