"""
Test user management and authorization business logic.
"""

import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interfaces import UserData


class TestUserAuthorization:
    """Test user authorization and access control."""
    
    def test_admin_user_authorization(self, expenses_service):
        """Test that admin user is always authorized."""
        admin_user_id = 12345  # Matches the fixture admin ID
        admin_name = "Admin User"
        
        is_authorized, message = expenses_service.check_user_authorization(admin_user_id, admin_name)
        
        assert is_authorized is True
        assert message is None
        
        # Verify admin user was created in database
        admin_user = expenses_service.db_service.get_user(admin_user_id)
        assert admin_user is not None
        assert admin_user.is_authorized is True
        assert admin_user.approval_requested is False
    
    def test_authorized_user_access(self, expenses_service, sample_user_data):
        """Test authorized user can access the system."""
        user_id = sample_user_data['user_id']
        user_name = sample_user_data['name']
        
        # Create authorized user
        expenses_service.db_service.create_user_if_missing(
            user_id, user_name, is_authorized=True, approval_requested=False
        )
        
        is_authorized, message = expenses_service.check_user_authorization(user_id, user_name)
        
        assert is_authorized is True
        assert message is None
        
        # Verify session was authenticated
        assert expenses_service.security_service.is_authenticated(user_id)
    
    def test_new_user_requires_approval(self, expenses_service):
        """Test that new users require admin approval."""
        user_id = 99999
        user_name = "New User"
        
        is_authorized, message = expenses_service.check_user_authorization(user_id, user_name)
        
        assert is_authorized is False
        assert "access request has been sent" in message
        
        # Verify user was created with pending approval
        user = expenses_service.db_service.get_user(user_id)
        assert user is not None
        assert user.is_authorized is False
        assert user.approval_requested is True
    
    def test_unauthorized_user_pending_approval(self, expenses_service, sample_unauthorized_user_data):
        """Test unauthorized user with pending approval."""
        user_id = sample_unauthorized_user_data['user_id']
        user_name = sample_unauthorized_user_data['name']
        
        # Create unauthorized user
        expenses_service.db_service.create_user_if_missing(
            user_id, user_name, 
            is_authorized=False, approval_requested=True
        )
        
        is_authorized, message = expenses_service.check_user_authorization(user_id, user_name)
        
        assert is_authorized is False
        assert "pending admin approval" in message
    
    def test_unauthorized_user_no_pending_approval(self, expenses_service):
        """Test unauthorized user without pending approval gets approval requested."""
        user_id = 88888
        user_name = "Existing Unauthorized User"
        
        # Create unauthorized user without approval requested
        expenses_service.db_service.create_user_if_missing(
            user_id, user_name, 
            is_authorized=False, approval_requested=False
        )
        
        is_authorized, message = expenses_service.check_user_authorization(user_id, user_name)
        
        assert is_authorized is False
        assert "pending admin approval" in message
        
        # Verify approval was requested
        user = expenses_service.db_service.get_user(user_id)
        assert user.approval_requested is True
    
    def test_rate_limited_user(self, expenses_service, rate_limited_user):
        """Test that rate-limited users are rejected."""
        user_id = rate_limited_user
        user_name = "Rate Limited User"
        
        is_authorized, message = expenses_service.check_user_authorization(user_id, user_name)
        
        assert is_authorized is False
        assert "Too many requests" in message
        assert "wait" in message.lower()


class TestUserSessionManagement:
    """Test user session creation and validation."""
    
    def test_session_creation_for_new_user(self, expenses_service):
        """Test session creation for new users."""
        user_id = 77777
        user_name = "Session Test User"
        
        # Check initial state - no session exists
        assert not expenses_service.security_service.validate_session(user_id)
        
        # Authorization check should create session
        expenses_service.check_user_authorization(user_id, user_name)
        
        # Session should now exist
        assert expenses_service.security_service.validate_session(user_id)
    
    def test_session_authentication_for_authorized_user(self, expenses_service, sample_user_data):
        """Test session authentication for authorized users."""
        user_id = sample_user_data['user_id']
        user_name = sample_user_data['name']
        
        # Create authorized user
        expenses_service.db_service.create_user_if_missing(
            user_id, user_name, is_authorized=True
        )
        
        # Initially not authenticated
        assert not expenses_service.security_service.is_authenticated(user_id)
        
        # Authorization check should authenticate session
        is_authorized, _ = expenses_service.check_user_authorization(user_id, user_name)
        
        assert is_authorized
        assert expenses_service.security_service.is_authenticated(user_id)
    
    def test_session_not_authenticated_for_unauthorized_user(self, expenses_service):
        """Test that unauthorized users don't get authenticated sessions."""
        user_id = 66666
        user_name = "Unauthorized Session User"
        
        is_authorized, _ = expenses_service.check_user_authorization(user_id, user_name)
        
        assert not is_authorized
        # Session exists but not authenticated
        assert expenses_service.security_service.validate_session(user_id)
        assert not expenses_service.security_service.is_authenticated(user_id)


class TestUserDatabaseOperations:
    """Test user-related database operations."""
    
    def test_create_user_if_missing_new_user(self, mock_db_service):
        """Test creating a new user."""
        user_id = 55555
        user_name = "Brand New User"
        
        user = mock_db_service.create_user_if_missing(
            user_id, user_name, is_authorized=True, approval_requested=False
        )
        
        assert user.user_id == user_id
        assert user.name == user_name
        assert user.is_authorized is True
        assert user.approval_requested is False
        
        # Verify user was stored
        stored_user = mock_db_service.get_user(user_id)
        assert stored_user is not None
        assert stored_user.user_id == user_id
    
    def test_create_user_if_missing_existing_user(self, mock_db_service):
        """Test that existing user is returned unchanged."""
        user_id = 44444
        user_name = "Existing User"
        
        # Create user first time
        first_user = mock_db_service.create_user_if_missing(
            user_id, user_name, is_authorized=False, approval_requested=True
        )
        
        # Try to create again with different settings
        second_user = mock_db_service.create_user_if_missing(
            user_id, "Different Name", is_authorized=True, approval_requested=False
        )
        
        # Should return the same user with original settings
        assert second_user.user_id == user_id
        assert second_user.name == user_name  # Original name
        assert second_user.is_authorized is False  # Original setting
        assert second_user.approval_requested is True  # Original setting
    
    def test_set_user_authorized(self, mock_db_service):
        """Test setting user authorization status."""
        user_id = 33333
        user_name = "Authorization Test User"
        
        # Create unauthorized user
        mock_db_service.create_user_if_missing(
            user_id, user_name, is_authorized=False
        )
        
        # Authorize user
        mock_db_service.set_user_authorized(user_id, True)
        
        # Verify authorization was set
        user = mock_db_service.get_user(user_id)
        assert user.is_authorized is True
        
        # Unauthorize user
        mock_db_service.set_user_authorized(user_id, False)
        
        # Verify authorization was removed
        user = mock_db_service.get_user(user_id)
        assert user.is_authorized is False
    
    def test_set_user_approval_requested(self, mock_db_service):
        """Test setting user approval request status."""
        user_id = 22222
        user_name = "Approval Test User"
        
        # Create user without approval requested
        mock_db_service.create_user_if_missing(
            user_id, user_name, approval_requested=False
        )
        
        # Request approval
        mock_db_service.set_user_approval_requested(user_id, True)
        
        # Verify approval was requested
        user = mock_db_service.get_user(user_id)
        assert user.approval_requested is True
        
        # Clear approval request
        mock_db_service.set_user_approval_requested(user_id, False)
        
        # Verify approval request was cleared
        user = mock_db_service.get_user(user_id)
        assert user.approval_requested is False
    
    def test_get_nonexistent_user(self, mock_db_service):
        """Test getting a user that doesn't exist."""
        user = mock_db_service.get_user(999999)
        assert user is None


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    def test_rate_limit_allows_initial_requests(self, mock_security_service):
        """Test that initial requests are allowed."""
        user_id = 11111
        
        # Configure low limits for testing
        mock_security_service.set_rate_limit_config(max_requests=3, window_seconds=60)
        
        # First few requests should be allowed
        assert mock_security_service.is_rate_limit_allowed(user_id) is True
        assert mock_security_service.is_rate_limit_allowed(user_id) is True
        assert mock_security_service.is_rate_limit_allowed(user_id) is True
    
    def test_rate_limit_blocks_excess_requests(self, mock_security_service):
        """Test that excess requests are blocked."""
        user_id = 11112
        
        # Configure very low limit for testing
        mock_security_service.set_rate_limit_config(max_requests=2, window_seconds=60)
        
        # Use up the limit
        assert mock_security_service.is_rate_limit_allowed(user_id) is True
        assert mock_security_service.is_rate_limit_allowed(user_id) is True
        
        # Next request should be blocked
        assert mock_security_service.is_rate_limit_allowed(user_id) is False
    
    def test_rate_limit_remaining_time(self, mock_security_service):
        """Test getting remaining time for rate limit reset."""
        user_id = 11113
        
        # Configure rate limit
        mock_security_service.set_rate_limit_config(max_requests=1, window_seconds=30)
        
        # Use up the limit
        mock_security_service.is_rate_limit_allowed(user_id)
        
        # Should have remaining time
        remaining = mock_security_service.get_rate_limit_remaining_time(user_id)
        assert remaining > 0
        assert remaining <= 30
    
    def test_rate_limit_per_user_isolation(self, mock_security_service):
        """Test that rate limits are per-user."""
        user1_id = 11114
        user2_id = 11115
        
        # Configure low limit
        mock_security_service.set_rate_limit_config(max_requests=1, window_seconds=60)
        
        # User 1 uses up their limit
        assert mock_security_service.is_rate_limit_allowed(user1_id) is True
        assert mock_security_service.is_rate_limit_allowed(user1_id) is False
        
        # User 2 should still be allowed
        assert mock_security_service.is_rate_limit_allowed(user2_id) is True


@pytest.mark.integration
class TestUserManagementIntegration:
    """Integration tests for complete user management workflows."""
    
    def test_new_user_registration_workflow(self, expenses_service):
        """Test complete new user registration and approval workflow."""
        user_id = 10001
        user_name = "Integration Test User"
        
        # Step 1: New user tries to access system
        is_authorized, message = expenses_service.check_user_authorization(user_id, user_name)
        assert not is_authorized
        assert "access request has been sent" in message
        
        # Step 2: User is created with pending approval
        user = expenses_service.db_service.get_user(user_id)
        assert user is not None
        assert not user.is_authorized
        assert user.approval_requested
        
        # Step 3: Admin approves user
        expenses_service.db_service.set_user_authorized(user_id, True)
        expenses_service.db_service.set_user_approval_requested(user_id, False)
        
        # Step 4: User can now access system
        is_authorized, message = expenses_service.check_user_authorization(user_id, user_name)
        assert is_authorized
        assert message is None
        
        # Step 5: Session is authenticated
        assert expenses_service.security_service.is_authenticated(user_id)
    
    def test_user_authorization_with_rate_limiting(self, expenses_service):
        """Test user authorization combined with rate limiting."""
        user_id = 10002
        user_name = "Rate Limit Test User"
        
        # Configure tight rate limits
        expenses_service.security_service.set_rate_limit_config(max_requests=2, window_seconds=10)
        
        # Create authorized user
        expenses_service.db_service.create_user_if_missing(
            user_id, user_name, is_authorized=True
        )
        
        # First two authorization checks should work
        is_authorized, _ = expenses_service.check_user_authorization(user_id, user_name)
        assert is_authorized
        
        is_authorized, _ = expenses_service.check_user_authorization(user_id, user_name)
        assert is_authorized
        
        # Third should be rate limited
        is_authorized, message = expenses_service.check_user_authorization(user_id, user_name)
        assert not is_authorized
        assert "Too many requests" in message