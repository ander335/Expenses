"""
extract_japan_expenses_standalone.py
Downloads database from cloud storage and extracts all expenses containing 'Japan' in description.
Summarizes expenses by months and provides detailed breakdown.
This is a standalone version that doesn't depend on the existing db.py module.
"""

import sys
import os
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from google.cloud import storage
import logging

# Set UTF-8 encoding for output
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

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

def parse_date(date_str):
    """Parse date string in DD-MM-YYYY format to datetime object."""
    if not date_str or len(date_str) < 10:
        return None
    try:
        return datetime.strptime(date_str, '%d-%m-%Y')
    except ValueError:
        return None

def parse_date_for_sort(date_str):
    """Parse date string DD-MM-YYYY for sorting."""
    if not date_str or len(date_str) < 10:
        return (9999, 12, 31)  # Put invalid dates at the end
    try:
        parts = date_str.split('-')
        day = int(parts[0])
        month = int(parts[1])
        year = int(parts[2])
        return (year, month, day)
    except (ValueError, IndexError):
        return (9999, 12, 31)

def extract_japan_and_date_range_expenses():
    """Extract Japan expenses and all expenses from Nov 14 to Dec 3, 2025."""
    
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
        # Date range: November 14, 2025 to December 3, 2025 (inclusive)
        start_date = datetime(2025, 11, 14)
        end_date = datetime(2025, 12, 3)
        
        # Query all receipts containing 'Japan' in description
        japan_receipts = session.query(Receipt).filter(
            Receipt.description.ilike('%Japan%')
        ).all()
        
        # Query all receipts in the date range
        all_receipts = session.query(Receipt).all()
        date_range_receipts = []
        
        for receipt in all_receipts:
            parsed_date = parse_date(receipt.date)
            if parsed_date and start_date <= parsed_date <= end_date:
                date_range_receipts.append(receipt)
        
        # Combine both sets (remove duplicates by receipt_id)
        combined_receipts = {}
        for receipt in japan_receipts:
            combined_receipts[receipt.receipt_id] = receipt
        for receipt in date_range_receipts:
            combined_receipts[receipt.receipt_id] = receipt
        
        combined_receipts_list = list(combined_receipts.values())
        
        # Sort by date to identify the last 2 transactions
        combined_receipts_list.sort(key=lambda x: parse_date_for_sort(x.date))
        
        # Remove the last 2 transactions (not related to vacation)
        if len(combined_receipts_list) >= 2:
            combined_receipts_list = combined_receipts_list[:-2]
            logger.info("Removed last 2 transactions")
        
        # Reclassify HAINANAIR receipt from vacation to transport
        for receipt in combined_receipts_list:
            if receipt.merchant and 'HAINANAIR' in receipt.merchant.upper():
                original_category = receipt.category
                receipt.category = 'transport'
                logger.info(f"Reclassified receipt {receipt.receipt_id} (HAINANAIR) from {original_category} to transport")
        
        # Sort by date and classify first two transactions as flights
        combined_receipts_list.sort(key=lambda x: parse_date_for_sort(x.date))
        for idx, receipt in enumerate(combined_receipts_list[:2]):
            original_category = receipt.category
            receipt.category = 'flights'
            logger.info(f"Reclassified receipt {receipt.receipt_id} to flights (originally {original_category})")
        
        if not combined_receipts_list:
            logger.info("No expenses found")
            print("No expenses found")
            return
        
        logger.info(f"Found {len(japan_receipts)} Japan expenses and {len(date_range_receipts)} expenses in date range (total unique: {len(combined_receipts_list)})")
        
        # Group expenses by month
        monthly_summary = defaultdict(lambda: {'total': 0.0, 'count': 0, 'receipts': []})
        total_amount = 0.0
        
        for receipt in combined_receipts_list:
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
        
        # Prepare data for table
        table_data = []
        category_summary = defaultdict(lambda: {'total': 0.0, 'count': 0})
        
        for receipt in combined_receipts_list:
            date_str = receipt.date or 'No date'
            merchant = (receipt.merchant or 'Unknown')[:20].ljust(20)
            category = receipt.category or 'Unknown'
            amount = receipt.total_amount
            description = (receipt.description or 'No description')[:60]
            
            table_data.append({
                'date': date_str,
                'amount': amount,
                'category': category,
                'merchant': merchant,
                'description': description
            })
            
            category_summary[category]['total'] += amount
            category_summary[category]['count'] += 1
        
        # Sort table data by date (ascending - earlier dates first)
        table_data.sort(key=lambda x: parse_date_for_sort(x['date']))
        
        # Print main expenses table
        print()
        print("=" * 130)
        print("ALL EXPENSES TABLE")
        print("=" * 130)
        print()
        
        # Print table header
        header = f"{'Date':<12} | {'Amount (CZK)':<14} | {'Category':<15} | {'Merchant':<20} | {'Description':<60}"
        print(header)
        print("-" * 130)
        
        # Print table rows
        for row in table_data:
            line = f"{row['date']:<12} | {row['amount']:>12.2f} CZK | {row['category']:<15} | {row['merchant']:<20} | {row['description']:<60}"
            print(line)
        
        print()
        print("=" * 130)
        print("CATEGORY SUMMARY")
        print("=" * 130)
        print()
        
        # Print category summary table
        cat_header = f"{'Category':<20} | {'Count':<8} | {'Total (CZK)':<15} | {'Percentage':<12}"
        print(cat_header)
        print("-" * 70)
        
        # Sort categories by total amount (descending)
        sorted_categories = sorted(category_summary.items(), key=lambda x: x[1]['total'], reverse=True)
        
        for category, data in sorted_categories:
            percentage = (data['total'] / total_amount * 100) if total_amount > 0 else 0
            cat_line = f"{category:<20} | {data['count']:>6} | {data['total']:>13.2f} CZK | {percentage:>10.2f}%"
            print(cat_line)
        
        print("-" * 70)
        print(f"{'TOTAL':<20} | {len(combined_receipts_list):>6} | {total_amount:>13.2f} CZK | {100.0:>10.2f}%")
        
        # Print adjusted category summary table
        print()
        print("=" * 130)
        print("ADJUSTED CATEGORY SUMMARY (Hotels + Food Combined)")
        print("=" * 130)
        print()
        
        # Create adjusted summary
        adjusted_summary = {}
        
        for category, data in category_summary.items():
            if category == 'vacation':
                # Rename vacation to hotels
                adjusted_summary['hotels'] = data.copy()
            elif category == 'alcohol':
                # Combine alcohol with food
                if 'food' not in adjusted_summary:
                    adjusted_summary['food'] = {'total': 0.0, 'count': 0}
                adjusted_summary['food']['total'] += data['total']
                adjusted_summary['food']['count'] += data['count']
            elif category == 'food':
                # Add food if not already added
                if 'food' not in adjusted_summary:
                    adjusted_summary['food'] = data.copy()
            else:
                adjusted_summary[category] = data.copy()
        
        # Combine alcohol with food if both exist
        if 'alcohol' in category_summary and 'food' in adjusted_summary:
            adjusted_summary['food']['total'] += category_summary['alcohol']['total']
            adjusted_summary['food']['count'] += category_summary['alcohol']['count']
        
        # Print adjusted category summary table
        adj_header = f"{'Category':<20} | {'Count':<8} | {'Total (CZK)':<15} | {'Percentage':<12}"
        print(adj_header)
        print("-" * 70)
        
        # Sort adjusted categories by total amount (descending)
        sorted_adj_categories = sorted(adjusted_summary.items(), key=lambda x: x[1]['total'], reverse=True)
        
        for category, data in sorted_adj_categories:
            percentage = (data['total'] / total_amount * 100) if total_amount > 0 else 0
            adj_line = f"{category:<20} | {data['count']:>6} | {data['total']:>13.2f} CZK | {percentage:>10.2f}%"
            print(adj_line)
        
        print("-" * 70)
        print(f"{'TOTAL':<20} | {len(combined_receipts_list):>6} | {total_amount:>13.2f} CZK | {100.0:>10.2f}%")
        
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
    extract_japan_and_date_range_expenses()