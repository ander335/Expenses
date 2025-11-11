"""
extract_japan_expenses_standalone.py
Downloads database from cloud storage and extracts all expenses containing 'Japan' in description.
Summarizes expenses by months and provides detailed breakdown.
This is a standalone version that doesn't depend on the existing db.py module.
"""

import os
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from google.cloud import storage
import logging

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cloud Storage configuration
BUCKET_NAME = "expenses_bot_bucket"

# Define database models
Base = declarative_base()

class Receipt(Base):
    __tablename__ = "receipts"
    receipt_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)
    merchant = Column(String, nullable=False)
    category = Column(String, nullable=False)
    total_amount = Column(Float, nullable=False)
    date = Column(String, nullable=True)
    text = Column(String, nullable=True)
    description = Column(String, nullable=True)

class CloudStorage:
    def __init__(self, bucket_name):
        """Initialize CloudStorage with bucket name."""
        self.bucket_name = bucket_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.local_db_path = 'expenses_temp.db'  # Use different filename to avoid conflicts

    def download_db(self):
        """Download the database file from cloud storage."""
        try:
            # Remove existing temp file if it exists
            if os.path.exists(self.local_db_path):
                os.remove(self.local_db_path)
                logger.info("Removed existing temporary database file")
            
            blob = self.bucket.blob('expenses.db')
            blob.download_to_filename(self.local_db_path)
            logger.info("Database downloaded successfully")
            return True
                
        except Exception as e:
            logger.error(f"Error downloading database: {str(e)}")
            return False

def download_database():
    """Download the latest database from cloud storage."""
    logger.info("Downloading database from cloud storage...")
    
    cloud_storage = CloudStorage(BUCKET_NAME)
    success = cloud_storage.download_db()
    
    if success:
        logger.info("Database downloaded successfully")
        return True
    else:
        logger.error("Failed to download database")
        return False

def setup_database_connection():
    """Setup database connection after download."""
    db_path = "sqlite:///expenses_temp.db"
    engine = create_engine(db_path)
    Session = sessionmaker(bind=engine)
    return Session

def extract_japan_expenses():
    """Extract all expenses containing 'Japan' in description and summarize by month."""
    
    # Download database
    if not download_database():
        logger.error("Cannot proceed without database")
        return
    
    # Check if database file exists
    if not os.path.exists('expenses_temp.db'):
        logger.error("Database file not found after download")
        return
    
    # Setup database connection
    Session = setup_database_connection()
    session = Session()
    
    try:
        # Query all receipts containing 'Japan' in description (case-insensitive)
        japan_receipts = session.query(Receipt).filter(
            Receipt.description.ilike('%Japan%')
        ).order_by(Receipt.date.desc()).all()
        
        if not japan_receipts:
            logger.info("No expenses found containing 'Japan' in description")
            print("No expenses found containing 'Japan' in description")
            return
        
        logger.info(f"Found {len(japan_receipts)} expenses containing 'Japan'")
        
        # Group expenses by month
        monthly_summary = defaultdict(lambda: {'total': 0.0, 'count': 0, 'receipts': []})
        total_amount = 0.0
        
        for receipt in japan_receipts:
            total_amount += receipt.total_amount
            
            # Extract month-year from date (format: DD-MM-YYYY)
            if receipt.date and len(receipt.date) >= 7:
                try:
                    # Extract MM-YYYY from DD-MM-YYYY
                    month_year = receipt.date[3:]  # Gets MM-YYYY part
                    
                    monthly_summary[month_year]['total'] += receipt.total_amount
                    monthly_summary[month_year]['count'] += 1
                    monthly_summary[month_year]['receipts'].append(receipt)
                    
                except (ValueError, IndexError) as e:
                    logger.warning(f"Invalid date format for receipt {receipt.receipt_id}: {receipt.date}")
                    # Use 'Unknown' for invalid dates
                    monthly_summary['Unknown']['total'] += receipt.total_amount
                    monthly_summary['Unknown']['count'] += 1
                    monthly_summary['Unknown']['receipts'].append(receipt)
            else:
                # Use 'Unknown' for missing dates
                monthly_summary['Unknown']['total'] += receipt.total_amount
                monthly_summary['Unknown']['count'] += 1
                monthly_summary['Unknown']['receipts'].append(receipt)
        
        # Print short summary
        print("JAPAN EXPENSES SUMMARY")
        print("=" * 30)
        print(f"Total: {total_amount:.2f} CZK ({len(japan_receipts)} receipts)")
        print()
        
        # Sort months (put 'Unknown' at the end)
        sorted_months = sorted([m for m in monthly_summary.keys() if m != 'Unknown'])
        if 'Unknown' in monthly_summary:
            sorted_months.append('Unknown')
        
        for month in sorted_months:
            data = monthly_summary[month]
            print(f"{month} - {data['total']:.2f} CZK")
        
    except Exception as e:
        logger.error(f"Error extracting Japan expenses: {str(e)}")
        print(f"Error: {str(e)}")
        
    finally:
        session.close()
        # Clean up temporary database file
        try:
            if os.path.exists('expenses_temp.db'):
                os.remove('expenses_temp.db')
                logger.info("Cleaned up temporary database file")
        except Exception as e:
            logger.warning(f"Could not clean up temporary file: {e}")

if __name__ == "__main__":
    extract_japan_expenses()