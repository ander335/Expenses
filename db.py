"""
db.py
Manages SQLite database for expenses using SQLAlchemy ORM.
"""

from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

DB_PATH = "sqlite:///expenses.db"
Base = declarative_base()

# Data models for domain logic
@dataclass
class PositionData:
    description: str
    quantity: float
    category: str
    price: float
    receipt_id: Optional[int] = None
    position_id: Optional[int] = None

@dataclass
class ReceiptData:
    merchant: str
    category: str
    total_amount: float
    text: Optional[str]
    date: Optional[str]
    positions: List[PositionData]
    user_id: int
    receipt_id: Optional[int] = None

@dataclass
class UserData:
    user_id: int
    name: str

class User(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    name = Column(String, nullable=False)
    receipts = relationship("Receipt", back_populates="user")

class Receipt(Base):
    __tablename__ = "receipts"
    receipt_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)
    merchant = Column(String, nullable=False)
    category = Column(String, nullable=False)
    total_amount = Column(Float, nullable=False)
    date = Column(String, nullable=True)
    text = Column(String, nullable=True)  # Full text content of the receipt
    user = relationship("User", back_populates="receipts")
    positions = relationship("Position", back_populates="receipt")

class Position(Base):
    __tablename__ = "positions"
    position_id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(Integer, ForeignKey('receipts.receipt_id'), nullable=False)
    description = Column(String, nullable=False)
    quantity = Column(String, nullable=False)
    category = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    receipt = relationship("Receipt", back_populates="positions")

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

def get_or_create_user(user_data: UserData) -> UserData:
    session = Session()
    user = session.query(User).filter_by(user_id=user_data.user_id).first()
    if not user:
        user = User(user_id=user_data.user_id, name=user_data.name)
        session.add(user)
        session.commit()
    result = UserData(user_id=user.user_id, name=user.name)
    session.close()
    return result

def get_receipt(receipt_id: int) -> Optional[ReceiptData]:
    session = Session()
    receipt = session.query(Receipt).filter_by(receipt_id=receipt_id).first()
    if not receipt:
        session.close()
        return None
    
    positions_data = [
        PositionData(
            description=p.description,
            quantity=float(p.quantity),
            category=p.category,
            price=p.price,
            receipt_id=p.receipt_id,
            position_id=p.position_id
        ) for p in receipt.positions
    ]
    
    result = ReceiptData(
        merchant=receipt.merchant,
        category=receipt.category,
        total_amount=receipt.total_amount,
        text=receipt.text,
        date=receipt.date,
        positions=positions_data,
        user_id=receipt.user_id,
        receipt_id=receipt.receipt_id
    )
    session.close()
    return result

def get_user_receipts(user_id: int) -> List[ReceiptData]:
    session = Session()
    receipts = session.query(Receipt).filter_by(user_id=user_id).all()
    result = []
    
    for receipt in receipts:
        positions_data = [
            PositionData(
                description=p.description,
                quantity=float(p.quantity),
                category=p.category,
                price=p.price,
                receipt_id=p.receipt_id,
                position_id=p.position_id
            ) for p in receipt.positions
        ]
        
        result.append(ReceiptData(
            merchant=receipt.merchant,
            category=receipt.category,
            total_amount=receipt.total_amount,
            text=receipt.text,
            date=receipt.date,
            positions=positions_data,
            user_id=receipt.user_id,
            receipt_id=receipt.receipt_id
        ))
    
    session.close()
    return result

def add_receipt(receipt_data: ReceiptData) -> int:
    session = Session()
    receipt = Receipt(
        user_id=receipt_data.user_id,
        merchant=receipt_data.merchant,
        category=receipt_data.category,
        text=receipt_data.text,
        total_amount=receipt_data.total_amount,
        date=receipt_data.date
    )
    session.add(receipt)
    session.commit()

    # Add positions
    if receipt_data.positions:
        for pos in receipt_data.positions:
            position = Position(
                receipt_id=receipt.receipt_id,
                description=pos.description,
                quantity=str(pos.quantity),  # Convert to string as per DB schema
                category=pos.category,
                price=pos.price
            )
            session.add(position)
        session.commit()

    receipt_id = receipt.receipt_id  # Access before session close
    session.close()
    return receipt_id
