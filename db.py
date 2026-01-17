"""
db.py
Manages SQLite database for expenses using SQLAlchemy ORM with Google Cloud Storage integration.
"""

from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Float, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Mapped, mapped_column
from cloud_storage import CloudStorage
from logger_config import logger

# Cloud Storage configuration
BUCKET_NAME = "expenses_bot_bucket"  # You'll need to set this to your actual bucket name
cloud_storage = CloudStorage(BUCKET_NAME)

# Download the database file from cloud storage if it exists
cloud_storage.download_db()

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
    is_income: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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

@dataclass
class Group(Base):
    __tablename__ = "groups"
    group_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    members: Mapped[List["GroupMember"]] = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")

@dataclass
class GroupMember(Base):
    __tablename__ = "group_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey('groups.group_id'), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.user_id'), nullable=False)
    group: Mapped["Group"] = relationship("Group", back_populates="members")
    user: Mapped["User"] = relationship("User")

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
            
            if 'is_income' not in columns:
                logger.info("Adding 'is_income' column to receipts table...")
                with engine.begin() as conn:
                    conn.exec_driver_sql("ALTER TABLE receipts ADD COLUMN is_income BOOLEAN NOT NULL DEFAULT 0")
                logger.info("Successfully added 'is_income' column to receipts table")
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
    """Get last N receipts for a user and their group members, ordered by date desc."""
    session = Session()
    try:
        # Get all user IDs in the same group (including the user themselves)
        group_user_ids = get_group_user_ids(user_id)
        
        receipts = session.query(Receipt)\
            .filter(Receipt.user_id.in_(group_user_ids))\
            .order_by(Receipt.receipt_id.desc())\
            .limit(n)\
            .all()
        return receipts
    finally:
        session.close()

def delete_receipt(receipt_id: int, user_id: int, is_admin: bool = False) -> dict:
    """
    Delete a receipt by ID. 
    Returns dict with 'success': bool and 'message': str indicating the result.
    
    Args:
        receipt_id: The ID of the receipt to delete
        user_id: The ID of the user requesting deletion
        is_admin: True if the user is an admin (can delete any receipt)
    """
    session = Session()
    try:
        # If admin, search for any receipt with the ID
        if is_admin:
            receipt = session.query(Receipt)\
                .filter_by(receipt_id=receipt_id)\
                .first()
            if not receipt:
                return {'success': False, 'message': f'Receipt {receipt_id} not found.'}
            
            # Log admin action for security audit
            if receipt.user_id != user_id:
                receipt_owner = session.query(User).filter_by(user_id=receipt.user_id).first()
                owner_name = receipt_owner.name if receipt_owner else f"User {receipt.user_id}"
                logger.warning(f"ADMIN ACTION: User {user_id} (admin) deleted receipt {receipt_id} belonging to {owner_name} (user_id: {receipt.user_id})")
            else:
                logger.info(f"Admin {user_id} deleted their own receipt {receipt_id}")
        else:
            # Regular user - only allow deletion of own receipts
            receipt = session.query(Receipt)\
                .filter_by(receipt_id=receipt_id, user_id=user_id)\
                .first()
            if not receipt:
                # Check if receipt exists but belongs to someone else
                other_receipt = session.query(Receipt)\
                    .filter_by(receipt_id=receipt_id)\
                    .first()
                if other_receipt:
                    logger.warning(f"SECURITY: User {user_id} attempted to delete receipt {receipt_id} belonging to user {other_receipt.user_id}")
                    return {'success': False, 'message': f'Receipt {receipt_id} not found or you do not have permission to delete it.'}
                else:
                    return {'success': False, 'message': f'Receipt {receipt_id} not found.'}
        
        session.delete(receipt)
        session.commit()
        logger.info(f"Receipt {receipt_id} deleted successfully by user {user_id}")
        return {'success': True, 'message': f'Receipt {receipt_id} deleted successfully!'}
            
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def get_receipts_by_date(user_id: int, date_str: str) -> List[Receipt]:
    """Get receipts for a specific date for user and their group members. Date format should be DD-MM-YYYY."""
    session = Session()
    try:
        # Get all user IDs in the same group (including the user themselves)
        group_user_ids = get_group_user_ids(user_id)
        
        receipts = session.query(Receipt)\
            .filter(Receipt.user_id.in_(group_user_ids), Receipt.date == date_str)\
            .order_by(Receipt.receipt_id.desc())\
            .all()
        return receipts
    finally:
        session.close()

def get_monthly_summary(user_id: int, n_months: int, fetch_income: Optional[bool] = None) -> List[dict]:
    """Get monthly summary for last N months including group members.
    """
    from sqlalchemy import func, desc
    from datetime import datetime, timedelta
    
    session = Session()
    try:
        # Get all user IDs in the same group (including the user themselves)
        group_user_ids = get_group_user_ids(user_id)
        
        # Create a set of valid month-year strings for current month and N-1 months back
        today = datetime.now()
        current_year = today.year
        current_month = today.month
        
        valid_months = set()
        year = current_year
        month = current_month
        
        for i in range(n_months):
            valid_months.add(f"{month:02d}-{year}")
            # Go back one month
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        
        logger.info(f"Valid months for summary: {sorted(valid_months)}")
        
        # Query receipts grouped by month for all group members
        query = session.query(
            # Extract year and month from DD-MM-YYYY format
            func.substr(Receipt.date, 7, 4).label('year'),  # Extract YYYY
            func.substr(Receipt.date, 4, 2).label('month_num'),  # Extract MM
            func.substr(Receipt.date, 4, 7).label('month'),  # Extract MM-YYYY for display
            func.sum(Receipt.total_amount).label('total'),
            func.count(Receipt.receipt_id).label('count')
        ).filter(
            Receipt.user_id.in_(group_user_ids),
            Receipt.date.isnot(None)  # Exclude records with NULL dates
        )
        
        # Filter by transaction type if specified
        if fetch_income is not None:
            query = query.filter(Receipt.is_income == fetch_income)
            transaction_type = 'income' if fetch_income else 'expenses'
            logger.info(f"Filtering for: {transaction_type}")
        
        results = query.group_by(
            func.substr(Receipt.date, 4, 7)  # Group by MM-YYYY
        ).order_by(
            desc(func.substr(Receipt.date, 7, 4)),  # Sort by year descending
            desc(func.substr(Receipt.date, 4, 2))   # Then by month descending
        ).all()
        
        # Convert to list of dicts with formatted month
        return [
            {
                'month': r.month or 'Unknown',  # Will be in MM-YYYY format
                'total': float(r.total or 0),
                'count': r.count or 0
            }
            for r in results 
            # Filter for last N months - check if month is in valid set
            if r.month in valid_months 
        ]
    finally:
        session.close()

# Group management functions

def create_group(description: str) -> int:
    """Create a new group and return its ID."""
    session = Session()
    try:
        group = Group(description=description)
        session.add(group)
        session.commit()
        group_id = group.group_id
        logger.info(f"Group {group_id} created with description: {description}")
        return group_id
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def add_user_to_group(user_id: int, group_id: int) -> bool:
    """Add a user to a group. Returns True if successful, False if already in group."""
    session = Session()
    try:
        # Check if user is already in the group
        existing = session.query(GroupMember).filter_by(
            user_id=user_id, group_id=group_id
        ).first()
        if existing:
            return False
        
        # Add user to group
        member = GroupMember(user_id=user_id, group_id=group_id)
        session.add(member)
        session.commit()
        logger.info(f"User {user_id} added to group {group_id}")
        return True
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def remove_user_from_group(user_id: int, group_id: int) -> bool:
    """Remove a user from a group. Returns True if successful, False if not in group."""
    session = Session()
    try:
        member = session.query(GroupMember).filter_by(
            user_id=user_id, group_id=group_id
        ).first()
        if not member:
            return False
        
        session.delete(member)
        session.commit()
        logger.info(f"User {user_id} removed from group {group_id}")
        return True
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_user_group(user_id: int) -> Optional[Group]:
    """Get the group that a user belongs to. Assumes user can only be in one group."""
    session = Session()
    try:
        member = session.query(GroupMember).filter_by(user_id=user_id).first()
        if not member:
            return None
        
        group = session.query(Group).filter_by(group_id=member.group_id).first()
        return group
    finally:
        session.close()

def get_group_members(group_id: int) -> List[User]:
    """Get all users in a group."""
    session = Session()
    try:
        members = session.query(User).join(GroupMember).filter(
            GroupMember.group_id == group_id
        ).all()
        return members
    finally:
        session.close()

def get_all_groups() -> List[Group]:
    """Get all groups."""
    session = Session()
    try:
        groups = session.query(Group).all()
        return groups
    finally:
        session.close()

def delete_group(group_id: int) -> bool:
    """Delete a group and all its memberships. Returns True if successful."""
    session = Session()
    try:
        group = session.query(Group).filter_by(group_id=group_id).first()
        if not group:
            return False
        
        session.delete(group)  # This will cascade delete group members
        session.commit()
        logger.info(f"Group {group_id} deleted")
        return True
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_group_user_ids(user_id: int) -> List[int]:
    """Get all user IDs in the same group as the given user, including the user themselves."""
    session = Session()
    try:
        # Get the group the user belongs to
        user_group = session.query(GroupMember).filter_by(user_id=user_id).first()
        if not user_group:
            # User is not in any group, return only themselves
            return [user_id]
        
        # Get all users in the same group
        group_user_ids = session.query(GroupMember.user_id).filter_by(
            group_id=user_group.group_id
        ).all()
        
        return [uid[0] for uid in group_user_ids]
    finally:
        session.close()

def ensure_default_group():
    """Ensure the default 'Servants of Shafran' group exists with specified users."""
    try:
        # Check if "Servants of Shafran" group already exists
        session = Session()
        try:
            existing_group = session.query(Group).filter_by(description="Servants of Shafran").first()
            if existing_group:
                logger.info(f"Default group 'Servants of Shafran' already exists with ID: {existing_group.group_id}")
                group_id = existing_group.group_id
            else:
                # Create the group
                group_id = create_group("Servants of Shafran")
                logger.info(f"Created default group 'Servants of Shafran' with ID: {group_id}")
        finally:
            session.close()
        
        # Ensure both users are in the group
        target_users = [98336105, 235783980]
        
        for user_id in target_users:
            try:
                # Check if user is already in the group
                session = Session()
                try:
                    existing_member = session.query(GroupMember).filter_by(
                        user_id=user_id, group_id=group_id
                    ).first()
                    
                    if not existing_member:
                        # Add user to group
                        success = add_user_to_group(user_id, group_id)
                        if success:
                            logger.info(f"Added user {user_id} to 'Servants of Shafran' group")
                        else:
                            logger.warning(f"Failed to add user {user_id} to 'Servants of Shafran' group")
                    else:
                        logger.info(f"User {user_id} already in 'Servants of Shafran' group")
                finally:
                    session.close()
                    
            except Exception as e:
                logger.error(f"Error adding user {user_id} to default group: {e}")
        
        logger.info("Default group setup completed")
        
    except Exception as e:
        logger.error(f"Error setting up default group: {e}")

# Ensure default group exists after all functions are defined
ensure_default_group()
