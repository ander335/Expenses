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
        """Download the database file from cloud storage with corruption recovery."""
        try:
            # Check if local file exists
            if os.path.exists(self.local_db_path):
                logger.info("Local database file exists and will be overwritten")
            
            blob = self.bucket.blob('expenses.db')
            
            # Download to a temporary file first to verify integrity
            temp_path = f"{self.local_db_path}.temp"
            blob.download_to_filename(temp_path)
            logger.info("Database downloaded to temporary location")
            
            # Try to verify the database file integrity
            if self._verify_database_integrity(temp_path):
                # Move temp file to final location
                if os.path.exists(self.local_db_path):
                    os.remove(self.local_db_path)
                os.rename(temp_path, self.local_db_path)
                logger.info("Successfully downloaded and verified database from cloud storage")
                # Store the current modification time
                self.last_modified_time = os.path.getmtime(self.local_db_path)
                return True
            else:
                logger.error("Downloaded database failed integrity check")
                os.remove(temp_path)
                # Try to recover from backup
                return self._recover_from_backup()
                
        except Exception as e:
            if 'Not Found' in str(e):
                logger.warning("Database file not found in cloud storage. Will create new one locally.")
            else:
                logger.error(f"Error downloading database: {str(e)}")
                # Try to recover from backup
                return self._recover_from_backup()
            return False

    def _verify_database_integrity(self, db_path):
        """Verify SQLite database integrity."""
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()
            conn.close()
            
            is_ok = result and result[0] == 'ok'
            logger.info(f"Database integrity check: {'PASSED' if is_ok else 'FAILED'}")
            return is_ok
        except Exception as e:
            logger.error(f"Database integrity check failed: {e}")
            return False

    def _recover_from_backup(self):
        """Attempt to recover from the most recent backup."""
        try:
            logger.info("Attempting to recover from backup...")
            
            # Find the most recent backup
            backup_blobs = list(self.bucket.list_blobs(prefix='expenses.db.backup.'))
            if not backup_blobs:
                logger.warning("No backup files found")
                return False
            
            # Sort by name (which includes timestamp) to get the latest
            backup_blobs.sort(key=lambda x: x.name, reverse=True)
            latest_backup = backup_blobs[0]
            
            logger.info(f"Attempting recovery from backup: {latest_backup.name}")
            
            # Download backup to temporary location
            temp_path = f"{self.local_db_path}.recovery"
            latest_backup.download_to_filename(temp_path)
            
            # Verify backup integrity
            if self._verify_database_integrity(temp_path):
                # Use the backup
                if os.path.exists(self.local_db_path):
                    os.remove(self.local_db_path)
                os.rename(temp_path, self.local_db_path)
                self.last_modified_time = os.path.getmtime(self.local_db_path)
                logger.info("Successfully recovered from backup")
                return True
            else:
                logger.error("Backup file is also corrupted")
                os.remove(temp_path)
                return False
                
        except Exception as e:
            logger.error(f"Error during backup recovery: {e}")
            return False

    def check_and_upload_db(self):
        """Check if database was modified and needs to be uploaded with atomic upload."""
        if not os.path.exists(self.local_db_path):
            logger.warning("Local database file not found")
            return False

        current_modified_time = os.path.getmtime(self.local_db_path)
        
        # Check if file was modified since last check
        if self.last_modified_time is None or current_modified_time > self.last_modified_time:
            try:
                # Use atomic upload with temporary filename
                temp_blob_name = f'expenses.db.temp.{int(datetime.now().timestamp())}'
                backup_blob_name = f'expenses.db.backup.{int(datetime.now().timestamp())}'
                
                logger.info(f"Starting atomic database upload to {temp_blob_name}")
                
                # Step 1: Upload to temporary file
                temp_blob = self.bucket.blob(temp_blob_name)
                temp_blob.upload_from_filename(self.local_db_path)
                logger.info("Database uploaded to temporary location")
                
                # Step 2: Create backup of current file (if it exists)
                try:
                    current_blob = self.bucket.blob('expenses.db')
                    if current_blob.exists():
                        backup_blob = self.bucket.blob(backup_blob_name)
                        backup_blob.rewrite(current_blob)
                        logger.info(f"Created backup: {backup_blob_name}")
                except Exception as backup_error:
                    logger.warning(f"Could not create backup: {backup_error}")
                
                # Step 3: Atomic rename from temp to final name
                final_blob = self.bucket.blob('expenses.db')
                final_blob.rewrite(temp_blob)
                logger.info("Database atomically moved to final location")
                
                # Step 4: Clean up temporary file
                temp_blob.delete()
                logger.info("Temporary file cleaned up")
                
                # Step 5: Clean up old backups (keep only last 1)
                self._cleanup_old_backups()
                
                self.last_modified_time = current_modified_time
                self.last_upload_time = datetime.now()
                logger.info("Successfully uploaded database to cloud storage")
                return True
                
            except Exception as e:
                logger.error(f"Error uploading database: {str(e)}")
                # Clean up any temporary files on error
                try:
                    temp_blob = self.bucket.blob(temp_blob_name)
                    if temp_blob.exists():
                        temp_blob.delete()
                        logger.info("Cleaned up temporary file after error")
                except:
                    pass
                return False

        logger.debug("Database unchanged since last upload")
        return False

    def _cleanup_old_backups(self):
        """Keep only the last 1 backup file."""
        try:
            # List all backup files
            backup_blobs = list(self.bucket.list_blobs(prefix='expenses.db.backup.'))
            
            # Sort by creation time (newest first)
            backup_blobs.sort(key=lambda x: x.name, reverse=True)
            
            # Delete all but the 1 most recent
            for blob in backup_blobs[1:]:
                blob.delete()
                logger.info(f"Deleted old backup: {blob.name}")
                
        except Exception as e:
            logger.warning(f"Error cleaning up old backups: {e}")