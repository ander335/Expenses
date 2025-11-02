"""
Test expense tracking and management business logic.
"""

import pytest
from datetime import datetime, timedelta
from db import Receipt, Position


class TestExpenseRetrieval:
    """Test retrieving user expenses."""
    
    def test_get_user_expenses_empty(self, expenses_service):
        """Test getting expenses for user with no receipts."""
        user_id = 12345
        
        receipts = expenses_service.get_user_expenses(user_id, 10)
        
        assert receipts == []
    
    def test_get_user_expenses_with_data(self, expenses_service, populated_database, sample_user_data):
        """Test getting expenses for user with receipts."""
        user_id = sample_user_data['user_id']
        
        receipts = expenses_service.get_user_expenses(user_id, 10)
        
        assert len(receipts) == 5  # populated_database creates 5 receipts
        
        # Verify receipts are ordered by date (most recent first)
        for receipt in receipts:
            assert receipt.user_id == user_id
        
        # Check that the most recent receipt comes first
        assert receipts[0].merchant == "Store 5"  # Last one created
        assert receipts[-1].merchant == "Store 1"  # First one created
    
    def test_get_user_expenses_limit(self, expenses_service, populated_database, sample_user_data):
        """Test limiting number of expenses returned."""
        user_id = sample_user_data['user_id']
        
        receipts = expenses_service.get_user_expenses(user_id, 3)
        
        assert len(receipts) == 3
        assert receipts[0].merchant == "Store 5"  # Most recent
        assert receipts[2].merchant == "Store 3"  # Third most recent
    
    def test_get_user_expenses_different_users(self, expenses_service, sample_user_data):
        """Test that users only see their own expenses."""
        user1_id = sample_user_data['user_id']
        user2_id = 99999
        
        # Create receipts for user 1
        receipt1 = Receipt(
            user_id=user1_id,
            merchant="User1 Store",
            category="food",
            total_amount=10.0,
            positions=[]
        )
        expenses_service.db_service.add_receipt(receipt1)
        
        # Create receipts for user 2
        receipt2 = Receipt(
            user_id=user2_id,
            merchant="User2 Store", 
            category="transport",
            total_amount=20.0,
            positions=[]
        )
        expenses_service.db_service.add_receipt(receipt2)
        
        # Each user should only see their own receipts
        user1_receipts = expenses_service.get_user_expenses(user1_id, 10)
        user2_receipts = expenses_service.get_user_expenses(user2_id, 10)
        
        assert len(user1_receipts) == 1
        assert len(user2_receipts) == 1
        assert user1_receipts[0].merchant == "User1 Store"
        assert user2_receipts[0].merchant == "User2 Store"


class TestExpenseDeletion:
    """Test deleting user expenses."""
    
    def test_delete_user_expense_success(self, expenses_service, sample_user_data, sample_receipt_object):
        """Test successful expense deletion."""
        user_id = sample_user_data['user_id']
        
        # Add a receipt
        receipt_id = expenses_service.db_service.add_receipt(sample_receipt_object)
        
        # Verify it exists
        assert expenses_service.db_service.get_receipt(receipt_id) is not None
        
        # Delete it
        result = expenses_service.delete_user_expense(user_id, receipt_id)
        
        assert result is True
        assert expenses_service.db_service.get_receipt(receipt_id) is None
    
    def test_delete_user_expense_nonexistent(self, expenses_service, sample_user_data):
        """Test deleting non-existent expense."""
        user_id = sample_user_data['user_id']
        nonexistent_receipt_id = 99999
        
        result = expenses_service.delete_user_expense(user_id, nonexistent_receipt_id)
        
        assert result is False
    
    def test_delete_user_expense_wrong_user(self, expenses_service, sample_receipt_object):
        """Test that users can't delete other users' expenses."""
        user1_id = 11111
        user2_id = 22222
        
        # User 1 creates a receipt
        sample_receipt_object.user_id = user1_id
        receipt_id = expenses_service.db_service.add_receipt(sample_receipt_object)
        
        # User 2 tries to delete it
        result = expenses_service.delete_user_expense(user2_id, receipt_id)
        
        assert result is False
        # Receipt should still exist
        assert expenses_service.db_service.get_receipt(receipt_id) is not None
    
    def test_delete_user_expense_with_positions(self, expenses_service, sample_user_data, sample_receipt_object):
        """Test deleting expense that has positions."""
        user_id = sample_user_data['user_id']
        
        # Add receipt with positions
        receipt_id = expenses_service.db_service.add_receipt(sample_receipt_object)
        
        # Verify positions exist
        saved_receipt = expenses_service.db_service.get_receipt(receipt_id)
        assert len(saved_receipt.positions) > 0
        
        # Delete receipt
        result = expenses_service.delete_user_expense(user_id, receipt_id)
        
        assert result is True
        # Both receipt and positions should be gone
        assert expenses_service.db_service.get_receipt(receipt_id) is None


class TestExpenseSummary:
    """Test expense summary and reporting."""
    
    def test_get_expense_summary_empty(self, expenses_service):
        """Test getting summary for user with no expenses."""
        user_id = 12345
        
        summary = expenses_service.get_expense_summary(user_id, 3)
        
        assert summary == []
    
    def test_get_expense_summary_single_month(self, expenses_service, sample_user_data):
        """Test getting summary with expenses in single month."""
        user_id = sample_user_data['user_id']
        
        # Create receipts for same month
        for i in range(3):
            receipt = Receipt(
                user_id=user_id,
                merchant=f"Store {i+1}",
                category="food",
                total_amount=10.0 + i,
                date="15-01-2024",  # Same month
                positions=[]
            )
            expenses_service.db_service.add_receipt(receipt)
        
        summary = expenses_service.get_expense_summary(user_id, 3)
        
        assert len(summary) == 1
        assert summary[0].month == "01-2024"
        assert summary[0].count == 3
        assert summary[0].total == 33.0  # 10 + 11 + 12
    
    def test_get_expense_summary_multiple_months(self, expenses_service, sample_user_data):
        """Test getting summary with expenses across multiple months."""
        user_id = sample_user_data['user_id']
        
        # Create receipts for different months
        receipts_data = [
            ("15-01-2024", 20.0),  # January
            ("20-01-2024", 15.0),  # January (same month)
            ("10-02-2024", 30.0),  # February
            ("05-03-2024", 25.0),  # March
        ]
        
        for date, amount in receipts_data:
            receipt = Receipt(
                user_id=user_id,
                merchant="Test Store",
                category="food",
                total_amount=amount,
                date=date,
                positions=[]
            )
            expenses_service.db_service.add_receipt(receipt)
        
        summary = expenses_service.get_expense_summary(user_id, 6)
        
        assert len(summary) == 3  # 3 different months
        
        # Summary should be ordered by month (most recent first)
        months = [s.month for s in summary]
        assert "03-2024" in months  # March
        assert "02-2024" in months  # February
        assert "01-2024" in months  # January
        
        # Check totals
        jan_summary = next(s for s in summary if s.month == "01-2024")
        feb_summary = next(s for s in summary if s.month == "02-2024")
        mar_summary = next(s for s in summary if s.month == "03-2024")
        
        assert jan_summary.total == 35.0  # 20 + 15
        assert jan_summary.count == 2
        assert feb_summary.total == 30.0
        assert feb_summary.count == 1
        assert mar_summary.total == 25.0
        assert mar_summary.count == 1
    
    def test_get_expense_summary_limit_months(self, expenses_service, sample_user_data):
        """Test limiting summary to specific number of months."""
        user_id = sample_user_data['user_id']
        
        # Create receipts for 5 different months
        months = ["01-2024", "02-2024", "03-2024", "04-2024", "05-2024"]
        for i, month in enumerate(months):
            receipt = Receipt(
                user_id=user_id,
                merchant="Test Store",
                category="food",
                total_amount=10.0,
                date=f"15-{month}",
                positions=[]
            )
            expenses_service.db_service.add_receipt(receipt)
        
        # Request only 3 months
        summary = expenses_service.get_expense_summary(user_id, 3)
        
        assert len(summary) <= 3  # Should not exceed requested limit
        
        # Should get the most recent months
        returned_months = [s.month for s in summary]
        assert "05-2024" in returned_months  # Most recent
        assert "04-2024" in returned_months
        assert "03-2024" in returned_months
    
    def test_get_expense_summary_invalid_dates_ignored(self, expenses_service, sample_user_data):
        """Test that receipts with invalid dates are ignored in summary."""
        user_id = sample_user_data['user_id']
        
        # Create receipts with valid and invalid dates
        receipts_data = [
            ("15-01-2024", 20.0, True),   # Valid
            ("invalid-date", 15.0, False),  # Invalid
            (None, 10.0, False),          # None
            ("20-01-2024", 25.0, True),   # Valid
        ]
        
        for date, amount, is_valid in receipts_data:
            receipt = Receipt(
                user_id=user_id,
                merchant="Test Store",
                category="food",
                total_amount=amount,
                date=date,
                positions=[]
            )
            expenses_service.db_service.add_receipt(receipt)
        
        summary = expenses_service.get_expense_summary(user_id, 3)
        
        # Should only include valid dates
        assert len(summary) == 1  # Only January 2024
        assert summary[0].month == "01-2024"
        assert summary[0].total == 45.0  # 20 + 25 (only valid dates)
        assert summary[0].count == 2
    
    def test_get_expense_summary_different_users(self, expenses_service):
        """Test that summary is user-specific."""
        user1_id = 11111
        user2_id = 22222
        
        # Create receipts for both users
        receipt1 = Receipt(
            user_id=user1_id,
            merchant="User1 Store",
            category="food",
            total_amount=100.0,
            date="15-01-2024",
            positions=[]
        )
        
        receipt2 = Receipt(
            user_id=user2_id,
            merchant="User2 Store",
            category="transport",
            total_amount=200.0,
            date="15-01-2024",
            positions=[]
        )
        
        expenses_service.db_service.add_receipt(receipt1)
        expenses_service.db_service.add_receipt(receipt2)
        
        # Each user should only see their own summary
        user1_summary = expenses_service.get_expense_summary(user1_id, 3)
        user2_summary = expenses_service.get_expense_summary(user2_id, 3)
        
        assert len(user1_summary) == 1
        assert len(user2_summary) == 1
        assert user1_summary[0].total == 100.0
        assert user2_summary[0].total == 200.0


class TestReceiptValidation:
    """Test receipt validation logic."""
    
    @pytest.mark.parametrize("amount,should_be_valid", [
        (1.00, True),
        (0.01, True),
        (999999.99, True),
        (0.00, True),
    ])
    def test_receipt_amount_validation(self, expenses_service, sample_user_data, amount, should_be_valid):
        """Test receipt amount validation with various values."""
        user_id = sample_user_data['user_id']
        
        receipt = Receipt(
            user_id=user_id,
            merchant="Test Store",
            category="food",
            total_amount=amount,
            positions=[]
        )
        
        # This should not raise an exception for valid amounts
        if should_be_valid:
            receipt_id = expenses_service.db_service.add_receipt(receipt)
            assert receipt_id > 0
            
            saved_receipt = expenses_service.db_service.get_receipt(receipt_id)
            assert saved_receipt.total_amount == amount
    
    @pytest.mark.parametrize("category", [
        'food', 'transport', 'clothes', 'healthcare', 'beauty', 
        'household', 'car', 'cat', 'other'
    ])
    def test_receipt_category_validation(self, expenses_service, sample_user_data, category):
        """Test receipt with all valid categories."""
        user_id = sample_user_data['user_id']
        
        receipt = Receipt(
            user_id=user_id,
            merchant="Test Store",
            category=category,
            total_amount=10.0,
            positions=[]
        )
        
        receipt_id = expenses_service.db_service.add_receipt(receipt)
        saved_receipt = expenses_service.db_service.get_receipt(receipt_id)
        
        assert saved_receipt.category == category


@pytest.mark.integration
class TestExpenseTrackingIntegration:
    """Integration tests for complete expense tracking workflows."""
    
    def test_complete_expense_lifecycle(self, expenses_service, sample_user_data):
        """Test complete lifecycle: create, read, update summary, delete."""
        user_id = sample_user_data['user_id']
        
        # Step 1: Create expense
        receipt = Receipt(
            user_id=user_id,
            merchant="Lifecycle Test Store",
            category="food",
            total_amount=50.0,
            date="15-01-2024",
            positions=[
                Position(
                    description="Test Item",
                    quantity="1",
                    category="food",
                    price=50.0
                )
            ]
        )
        
        receipt_id = expenses_service.db_service.add_receipt(receipt)
        assert receipt_id > 0
        
        # Step 2: Read expense
        user_expenses = expenses_service.get_user_expenses(user_id, 10)
        assert len(user_expenses) == 1
        assert user_expenses[0].merchant == "Lifecycle Test Store"
        
        # Step 3: Check summary
        summary = expenses_service.get_expense_summary(user_id, 3)
        assert len(summary) == 1
        assert summary[0].total == 50.0
        assert summary[0].count == 1
        
        # Step 4: Delete expense
        delete_result = expenses_service.delete_user_expense(user_id, receipt_id)
        assert delete_result is True
        
        # Step 5: Verify deletion
        user_expenses = expenses_service.get_user_expenses(user_id, 10)
        assert len(user_expenses) == 0
        
        summary = expenses_service.get_expense_summary(user_id, 3)
        assert len(summary) == 0
    
    def test_multi_user_expense_isolation(self, expenses_service):
        """Test that multiple users' expenses don't interfere with each other."""
        user1_id = 10001
        user2_id = 10002
        
        # Create expenses for both users
        receipt1 = Receipt(
            user_id=user1_id,
            merchant="User1 Store",
            category="food",
            total_amount=25.0,
            date="15-01-2024",
            positions=[]
        )
        
        receipt2 = Receipt(
            user_id=user2_id,
            merchant="User2 Store",
            category="transport",
            total_amount=75.0,
            date="15-01-2024",
            positions=[]
        )
        
        receipt1_id = expenses_service.db_service.add_receipt(receipt1)
        receipt2_id = expenses_service.db_service.add_receipt(receipt2)
        
        # Verify isolation in expense lists
        user1_expenses = expenses_service.get_user_expenses(user1_id, 10)
        user2_expenses = expenses_service.get_user_expenses(user2_id, 10)
        
        assert len(user1_expenses) == 1
        assert len(user2_expenses) == 1
        assert user1_expenses[0].receipt_id == receipt1_id
        assert user2_expenses[0].receipt_id == receipt2_id
        
        # Verify isolation in summaries
        user1_summary = expenses_service.get_expense_summary(user1_id, 3)
        user2_summary = expenses_service.get_expense_summary(user2_id, 3)
        
        assert user1_summary[0].total == 25.0
        assert user2_summary[0].total == 75.0
        
        # Verify deletion isolation
        delete_result = expenses_service.delete_user_expense(user1_id, receipt1_id)
        assert delete_result is True
        
        # User2's expenses should be unaffected
        user2_expenses_after = expenses_service.get_user_expenses(user2_id, 10)
        assert len(user2_expenses_after) == 1
        assert user2_expenses_after[0].receipt_id == receipt2_id