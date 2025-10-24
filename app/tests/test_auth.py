"""
Authentication system tests.
===========================

This module contains comprehensive tests for the authentication system
including user registration, login, JWT token validation, and security features.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, verify_token
from app.models.user import User


client = TestClient(app)


@pytest.fixture
def test_user_data():
    """Test user data for registration."""
    return {
        "email": "test@example.com",
        "password": "TestPass123!"
    }


@pytest.fixture
def weak_password_data():
    """Weak password data for testing validation."""
    return {
        "email": "test@example.com",
        "password": "123"
    }


def test_password_hashing():
    """Test password hashing and verification."""
    password = "TestPassword123!"
    hashed = hash_password(password)
    
    # Hash should be different from original
    assert hashed != password
    
    # Verification should work
    assert verify_password(password, hashed) is True
    
    # Wrong password should fail
    assert verify_password("wrong_password", hashed) is False


def test_jwt_token_creation():
    """Test JWT token creation and verification."""
    email = "test@example.com"
    token = create_access_token(email)
    
    # Token should be created
    assert token is not None
    assert isinstance(token, str)
    
    # Token should be verifiable
    payload = verify_token(token, "access")
    assert payload is not None
    assert payload["sub"] == email
    assert payload["type"] == "access"


def test_jwt_token_verification():
    """Test JWT token verification with invalid tokens."""
    # Invalid token should return None
    invalid_token = "invalid.token.here"
    payload = verify_token(invalid_token, "access")
    assert payload is None
    
    # Wrong token type should return None
    email = "test@example.com"
    token = create_access_token(email)
    payload = verify_token(token, "refresh")  # Wrong type
    assert payload is None


def test_register_success(test_user_data):
    """Test successful user registration."""
    response = client.post("/auth/register", json=test_user_data)
    
    assert response.status_code == 201
    data = response.json()
    
    # Check response structure
    assert "user" in data
    assert "token" in data
    assert "message" in data
    
    # Check user data
    assert data["user"]["email"] == test_user_data["email"]
    assert data["user"]["is_active"] is True
    assert "id" in data["user"]
    assert "created_at" in data["user"]
    
    # Check token data
    assert data["token"]["access_token"] is not None
    assert data["token"]["token_type"] == "bearer"
    assert data["token"]["expires_in"] == 1800  # 30 minutes


def test_register_duplicate_email(test_user_data):
    """Test registration with duplicate email."""
    # First registration should succeed
    response1 = client.post("/auth/register", json=test_user_data)
    assert response1.status_code == 201
    
    # Second registration with same email should fail
    response2 = client.post("/auth/register", json=test_user_data)
    assert response2.status_code == 400
    assert "already registered" in response2.json()["detail"]


def test_register_weak_password(weak_password_data):
    """Test registration with weak password."""
    response = client.post("/auth/register", json=weak_password_data)
    
    assert response.status_code == 422  # Validation error
    assert "password" in str(response.json())


def test_login_success(test_user_data):
    """Test successful user login."""
    # First register a user
    client.post("/auth/register", json=test_user_data)
    
    # Then login
    response = client.post("/auth/login", json=test_user_data)
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800


def test_login_invalid_credentials(test_user_data):
    """Test login with invalid credentials."""
    # Register a user
    client.post("/auth/register", json=test_user_data)
    
    # Try to login with wrong password
    wrong_data = {
        "email": test_user_data["email"],
        "password": "WrongPassword123!"
    }
    
    response = client.post("/auth/login", json=wrong_data)
    
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_nonexistent_user():
    """Test login with non-existent user."""
    login_data = {
        "email": "nonexistent@example.com",
        "password": "SomePassword123!"
    }
    
    response = client.post("/auth/login", json=login_data)
    
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_oauth2_login(test_user_data):
    """Test OAuth2 compatible login endpoint."""
    # Register a user
    client.post("/auth/register", json=test_user_data)
    
    # Login using OAuth2 form
    form_data = {
        "username": test_user_data["email"],
        "password": test_user_data["password"]
    }
    
    response = client.post("/auth/token", data=form_data)
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


def test_get_current_user_profile(test_user_data):
    """Test getting current user profile."""
    # Register and login
    register_response = client.post("/auth/register", json=test_user_data)
    token = register_response.json()["token"]["access_token"]
    
    # Get profile
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/auth/me", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["email"] == test_user_data["email"]
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


def test_get_profile_without_token():
    """Test getting profile without authentication token."""
    response = client.get("/auth/me")
    
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]


def test_get_profile_with_invalid_token():
    """Test getting profile with invalid token."""
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.get("/auth/me", headers=headers)
    
    assert response.status_code == 401
    assert "Could not validate credentials" in response.json()["detail"]


def test_logout(test_user_data):
    """Test logout endpoint."""
    # Register and login
    register_response = client.post("/auth/register", json=test_user_data)
    token = register_response.json()["token"]["access_token"]
    
    # Logout
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/auth/logout", headers=headers)
    
    assert response.status_code == 200
    assert "Logged out successfully" in response.json()["message"]


def test_refresh_token(test_user_data):
    """Test token refresh."""
    # Register and login
    register_response = client.post("/auth/register", json=test_user_data)
    token = register_response.json()["token"]["access_token"]
    
    # Refresh token
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/auth/refresh", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800
    
    # New token should be different
    assert data["access_token"] != token


def test_protected_endpoint_access(test_user_data):
    """Test access to protected endpoints."""
    # Register and login
    register_response = client.post("/auth/register", json=test_user_data)
    token = register_response.json()["token"]["access_token"]
    
    # Try to access protected endpoint
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/prices/AAPL", headers=headers)
    
    # Should not get 401 (authentication error)
    assert response.status_code != 401


def test_protected_endpoint_without_auth():
    """Test access to protected endpoints without authentication."""
    response = client.get("/prices/AAPL")
    
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]


def test_password_validation():
    """Test password validation rules."""
    from app.core.security import check_password_strength
    
    # Test weak password
    weak_result = check_password_strength("123")
    assert weak_result["strength"] == "weak"
    assert weak_result["is_strong"] is False
    assert len(weak_result["feedback"]) > 0
    
    # Test strong password
    strong_result = check_password_strength("StrongPass123!")
    assert strong_result["strength"] == "strong"
    assert strong_result["is_strong"] is True
    assert len(strong_result["feedback"]) == 0

