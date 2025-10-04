"""
db.py
Manages SQLite database for expenses using SQLAlchemy ORM.
"""

from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Mapped, mapped_column

DB_PATH = "sqlite:///expenses.db"
Base = declarative_base()

@dataclass
class User(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
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
from sqlalchemy import event

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key constraints for SQLite"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# Create engine with foreign key enforcement
engine = create_engine(DB_PATH)
Session = sessionmaker(bind=engine)

# Create tables if they don't exist
Base.metadata.create_all(engine)

def get_or_create_user(user: User) -> User:
    session = Session()
    existing_user = session.query(User).filter_by(user_id=user.user_id).first()
    if not existing_user:
        session.add(user)
        session.commit()
        result = user
    else:
        result = existing_user
    session.close()
    return result

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
