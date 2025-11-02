"""
process_db.py
Downloads the database from cloud storage and queries receipts from 2023.
Uses existing functionality from db.py to avoid code duplication.
"""

import os
import sys
from typing import List
from sqlalchemy.orm.exc import NoResultFound
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import from db.py - this automatically downloads the database and sets up connections
from db import Session, Receipt, cloud_storage
from logger_config import logger

def query_receipts_from_2023() -> List[Receipt]:
    """
    Query all receipts from 2023 using the existing database session from db.py.
    
    Returns:
        List[Receipt]: List of receipts from 2023
    """
    logger.info("Querying receipts from 2023...")
    
    session = Session()
    try:
        # Query receipts where date ends with '-2023' (DD-MM-2023 format)
        receipts_2023 = session.query(Receipt).filter(
            Receipt.date.like('%-2023')
        ).order_by(Receipt.date).all()
        
        logger.info(f"Found {len(receipts_2023)} receipts from 2023")
        return receipts_2023
        
    except Exception as e:
        logger.error(f"Error querying receipts from 2023: {str(e)}")
        return []
    finally:
        session.close()

def update_receipts_2023_to_2025() -> bool:
    """
    Update all receipts from 2023 to 2025, keeping the day and month the same.
    
    Returns:
        bool: True if update was successful, False otherwise
    """
    logger.info("Updating receipt dates from 2023 to 2025...")
    
    session = Session()
    try:
        # Query all receipts from 2023
        receipts_2023 = session.query(Receipt).filter(
            Receipt.date.like('%-2023')
        ).all()
        
        updated_count = 0
        for receipt in receipts_2023:
            if receipt.date:
                try:
                    # Split date (DD-MM-2023) and replace year
                    date_parts = receipt.date.split('-')
                    if len(date_parts) == 3 and date_parts[2] == '2023':
                        # Keep day and month, change year to 2025
                        new_date = f"{date_parts[0]}-{date_parts[1]}-2025"
                        old_date = receipt.date
                        receipt.date = new_date
                        updated_count += 1
                        logger.info(f"Updated receipt {receipt.receipt_id}: {old_date} -> {new_date}")
                except (IndexError, ValueError) as e:
                    logger.warning(f"Could not update receipt {receipt.receipt_id} with date {receipt.date}: {e}")
        
        # Commit all changes
        session.commit()
        logger.info(f"Successfully updated {updated_count} receipts from 2023 to 2025")
        return True
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating receipts from 2023 to 2025: {str(e)}")
        return False
    finally:
        session.close()

def upload_database_to_cloud() -> bool:
    """
    Upload the updated database to cloud storage.
    
    Returns:
        bool: True if upload was successful, False otherwise
    """
    logger.info("Uploading updated database to cloud storage...")
    
    try:
        # Use the existing cloud_storage instance from db.py
        success = cloud_storage.check_and_upload_db()
        
        if success:
            logger.info("Successfully uploaded database to cloud storage")
        else:
            logger.warning("Database upload returned False - no changes detected or upload failed")
        
        return success
        
    except Exception as e:
        logger.error(f"Error uploading database to cloud storage: {str(e)}")
        return False

def main():
    """
    Main function to process the database, update dates from 2023 to 2025, and upload to cloud.
    Database is automatically downloaded and connected via db.py imports.
    """
    logger.info("Starting process_db.py - Processing receipts from 2023")
    
    try:
        # Database is automatically downloaded when importing from db.py
        logger.info("Database connection established via db.py")
        
        # Step 1: Query receipts from 2023
        receipts_2023 = query_receipts_from_2023()
        logger.info(f"Total number of receipts from 2023: {len(receipts_2023)}")
        
        if len(receipts_2023) > 0:
            # Step 2: Update receipts from 2023 to 2025
            update_success = update_receipts_2023_to_2025()
            
            if update_success:
                # Step 3: Upload updated database to cloud
                upload_success = upload_database_to_cloud()
                
                if upload_success:
                    logger.info("Successfully completed: updated dates and uploaded to cloud")
                else:
                    logger.warning("Update completed but upload to cloud failed")
            else:
                logger.error("Failed to update receipt dates")
                return 1
        else:
            logger.info("No receipts from 2023 found to update")
        
        return 0
        
    except Exception as e:
        logger.error(f"Unexpected error in main: {str(e)}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)