"""
db.py
Manages SQLite database for expenses using SQLAlchemy ORM.
"""

from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DB_PATH = "sqlite:///expenses.db"
Base = declarative_base()

class Expense(Base):
    __tablename__ = "expenses"
    expense_id = Column(Integer, primary_key=True, autoincrement=True)
    shop_name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    amount = Column(Float, nullable=False)

engine = create_engine(DB_PATH)
Session = sessionmaker(bind=engine)

# Create tables
Base.metadata.create_all(engine)

def add_expense(shop_name, category, amount):
    session = Session()
    expense = Expense(shop_name=shop_name, category=category, amount=amount)
    session.add(expense)
    session.commit()
    expense_id = expense.expense_id  # Access before session close
    session.close()
    return expense_id
