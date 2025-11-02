"""
db.py
Manages SQLite database for expenses using SQLAlchemy ORM with Google Cloud Storage integration.
"""

from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Float, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Mapped, mapped_column
from logger_config import logger

# Cloud Storage configuration - initialized lazily to avoid import-time issues
BUCKET_NAME = "expenses_bot_bucket"  # You'll need to set this to your actual bucket name
_cloud_storage = None

def get_cloud_storage():
    """Get cloud storage instance, initializing if needed."""
    global _cloud_storage
    if _cloud_storage is None:
        try:
            from cloud_storage import CloudStorage
            _cloud_storage = CloudStorage(BUCKET_NAME)
            # Download the database file from cloud storage if it exists
            _cloud_storage.download_db()
        except Exception as e:
            logger.warning(f"Cloud storage initialization failed: {e}")
            _cloud_storage = None
    return _cloud_storage

# For backward compatibility - create a module-level reference
cloud_storage = None

DB_PATH = "sqlite:///expenses.db"
Base = declarative_base()

@dataclass
class User(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # Authorization fields (no is_admin; single admin via TELEGRAM_ADMIN_ID)
    is_authorized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approval_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    receipts: Mapped[List["Receipt"]] = relationship("Receipt", back_populates="user")

@dataclass
class Receipt(Base):
    __tablename__ = "receipts"
    receipt_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.user_id'), nullable=False)
    merchant: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    text: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Full text content of the receipt
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Brief description from Gemini
    user: Mapped["User"] = relationship("User", back_populates="receipts")
    positions: Mapped[List["Position"]] = relationship("Position", back_populates="receipt", cascade="all, delete-orphan")

@dataclass
class Position(Base):
    __tablename__ = "positions"
    position_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receipt_id: Mapped[int] = mapped_column(Integer, ForeignKey('receipts.receipt_id'), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    receipt: Mapped["Receipt"] = relationship("Receipt", back_populates="positions")

from sqlalchemy.engine import Engine
from sqlalchemy import event, inspect

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key constraints for SQLite"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# Create engine with foreign key enforcement
engine = create_engine(DB_PATH)
Session = sessionmaker(bind=engine)

def migrate_database():
    """Handle database schema migrations."""
    logger.info("Checking for database migrations...")
    
    # Check if receipts table exists and has description column
    try:
        insp = inspect(engine)

        table_names = insp.get_table_names()

        # --- Receipts table migrations ---
        if 'receipts' in table_names:
            columns = [col['name'] for col in insp.get_columns('receipts')]

            if 'description' not in columns:
                logger.info("Adding 'description' column to receipts table...")
                # Use driver-level SQL execution for DDL in SQLAlchemy 2.0
                with engine.begin() as conn:
                    conn.exec_driver_sql("ALTER TABLE receipts ADD COLUMN description TEXT")
                logger.info("Successfully added 'description' column to receipts table")
        else:
            logger.info("Receipts table doesn't exist yet, will be created by create_all()")

        # --- Users table migrations ---
        if 'users' in table_names:
            user_columns = [col['name'] for col in insp.get_columns('users')]
            with engine.begin() as conn:
                if 'is_authorized' not in user_columns:
                    logger.info("Adding 'is_authorized' column to users table...")
                    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN is_authorized BOOLEAN NOT NULL DEFAULT 0")
                if 'approval_requested' not in user_columns:
                    logger.info("Adding 'approval_requested' column to users table...")
                    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN approval_requested BOOLEAN NOT NULL DEFAULT 0")
        else:
            logger.info("Users table doesn't exist yet, will be created by create_all()")

    except Exception as e:
        logger.error(f"Error during database migration: {e}")
        # Don't raise the exception, let the application continue
        # The create_all will handle basic table creation if needed

# Create tables if they don't exist (this must run first)
Base.metadata.create_all(engine)

# Run database migrations after table creation
migrate_database()

def get_or_create_user(user: User) -> User:
    session = Session()
    try:
        existing_user = session.query(User).filter_by(user_id=user.user_id).first()
        if not existing_user:
            session.add(user)
            session.commit()
            result = user
        else:
            result = existing_user
        return result
    finally:
        session.close()

def get_user(user_id: int) -> Optional[User]:
    session = Session()
    try:
        return session.query(User).filter_by(user_id=user_id).first()
    finally:
        session.close()

def create_user_if_missing(user_id: int, name: str, *, is_authorized: bool = False, approval_requested: bool = False) -> User:
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        if user:
            return user
        user = User(
            user_id=user_id,
            name=name,
            is_authorized=is_authorized,
            approval_requested=approval_requested,
        )
        session.add(user)
        session.commit()
        return user
    finally:
        session.close()

def set_user_authorized(user_id: int, authorized: bool) -> None:
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user:
            return
        user.is_authorized = authorized
        session.commit()
    finally:
        session.close()

def set_user_approval_requested(user_id: int, requested: bool = True) -> None:
    session = Session()
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user:
            return
        user.approval_requested = requested
        session.commit()
    finally:
        session.close()

def get_receipt(receipt_id: int) -> Optional[Receipt]:
    session = Session()
    receipt = session.query(Receipt).filter_by(receipt_id=receipt_id).first()
    if not receipt:
        session.close()
        return None
    session.close()
    return receipt

def get_user_receipts(user_id: int) -> List[Receipt]:
    session = Session()
    receipts = session.query(Receipt).filter_by(user_id=user_id).all()
    session.close()
    return receipts

def add_receipt(receipt: Receipt) -> int:
    session = Session()
    try:
        session.add(receipt)
        # This will cascade and save the positions as well
        session.commit()
        receipt_id = receipt.receipt_id
        logger.info(f"Receipt {receipt_id} added successfully")
            
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
    return receipt_id

def get_last_n_receipts(user_id: int, n: int) -> List[Receipt]:
    """Get last N receipts for a user, ordered by date desc."""
    session = Session()
    try:
        receipts = session.query(Receipt)\
            .filter_by(user_id=user_id)\
            .order_by(Receipt.receipt_id.desc())\
            .limit(n)\
            .all()
        return receipts
    finally:
        session.close()

def delete_receipt(receipt_id: int, user_id: int) -> bool:
    """Delete a receipt by ID. Returns True if successful, False if receipt not found or not owned by user."""
    session = Session()
    try:
        receipt = session.query(Receipt)\
            .filter_by(receipt_id=receipt_id, user_id=user_id)\
            .first()
        if not receipt:
            return False
        session.delete(receipt)
        session.commit()
        logger.info(f"Receipt {receipt_id} deleted successfully")
            
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def get_monthly_summary(user_id: int, n_months: int) -> List[dict]:
    """Get monthly summary for last N months."""
    from sqlalchemy import func, desc
    from datetime import datetime, timedelta
    
    session = Session()
    try:
        # Calculate date N months ago
        today = datetime.now()
        start_date = (today - timedelta(days=n_months * 30)).strftime('%d-%m-%Y')
        
        # Query receipts grouped by month
        results = session.query(
            # Combine month and year from DD-MM-YYYY format
            func.substr(Receipt.date, 4, 7).label('month'),  # Extract MM-YYYY from DD-MM-YYYY
            func.sum(Receipt.total_amount).label('total'),
            func.count(Receipt.receipt_id).label('count')
        ).filter(
            Receipt.user_id == user_id,
            Receipt.date.isnot(None)  # Exclude records with NULL dates
        ).group_by(
            func.substr(Receipt.date, 4, 7)  # Group by MM-YYYY
        ).order_by(
            desc('month')
        ).all()
        
        # Convert to list of dicts with formatted month
        return [
            {
                'month': r.month or 'Unknown',  # Will be in MM-YYYY format
                'total': float(r.total or 0),
                'count': r.count or 0
            }
            for r in results 
            # Filter for last N months - compare only month-year part
            if r.month >= start_date[3:] 
        ]
    finally:
        session.close()
