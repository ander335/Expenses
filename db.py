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
