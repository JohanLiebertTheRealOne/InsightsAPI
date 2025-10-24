#!/usr/bin/env python3
"""
Authentication Demo Script for InsightFinance API
=================================================

This script demonstrates the authentication system by:
1. Registering a new user
2. Logging in with credentials
3. Accessing protected endpoints
4. Testing token refresh

Usage:
    python auth_demo.py

Requirements:
    - API server running (uvicorn app.main:app --reload)
    - Database and Redis initialized
"""

import requests
import json
import sys
from typing import Dict, Any


API_BASE_URL = "http://localhost:8000"


def make_request(method: str, endpoint: str, data: Dict[Any, Any] = None, token: str = None) -> Dict[Any, Any]:
    """Make HTTP request to API."""
    url = f"{API_BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return {}


def test_health():
    """Test API health."""
    print("🔍 Testing API health...")
    result = make_request("GET", "/health")
    if result:
        print(f"✅ API is healthy: {result['status']}")
        return True
    else:
        print("❌ API health check failed")
        return False


def register_user(email: str, password: str) -> Dict[Any, Any]:
    """Register a new user."""
    print(f"📝 Registering user: {email}")
    
    data = {
        "email": email,
        "password": password
    }
    
    result = make_request("POST", "/auth/register", data)
    if result:
        print(f"✅ User registered successfully")
        print(f"   User ID: {result['user']['id']}")
        print(f"   Email: {result['user']['email']}")
        print(f"   Active: {result['user']['is_active']}")
        return result
    else:
        print("❌ User registration failed")
        return {}


def login_user(email: str, password: str) -> Dict[Any, Any]:
    """Login user and get token."""
    print(f"🔐 Logging in user: {email}")
    
    data = {
        "email": email,
        "password": password
    }
    
    result = make_request("POST", "/auth/login", data)
    if result:
        print(f"✅ Login successful")
        print(f"   Token type: {result['token_type']}")
        print(f"   Expires in: {result['expires_in']} seconds")
        return result
    else:
        print("❌ Login failed")
        return {}


def get_user_profile(token: str) -> Dict[Any, Any]:
    """Get current user profile."""
    print("👤 Getting user profile...")
    
    result = make_request("GET", "/auth/me", token=token)
    if result:
        print(f"✅ Profile retrieved")
        print(f"   ID: {result['id']}")
        print(f"   Email: {result['email']}")
        print(f"   Active: {result['is_active']}")
        print(f"   Created: {result['created_at']}")
        return result
    else:
        print("❌ Profile retrieval failed")
        return {}


def refresh_token(token: str) -> Dict[Any, Any]:
    """Refresh JWT token."""
    print("🔄 Refreshing token...")
    
    result = make_request("POST", "/auth/refresh", token=token)
    if result:
        print(f"✅ Token refreshed")
        print(f"   New token type: {result['token_type']}")
        print(f"   Expires in: {result['expires_in']} seconds")
        return result
    else:
        print("❌ Token refresh failed")
        return {}


def test_protected_endpoint(token: str):
    """Test access to protected endpoint."""
    print("🔒 Testing protected endpoint access...")
    
    # Try to access prices endpoint
    result = make_request("GET", "/prices/AAPL", token=token)
    if result:
        print(f"✅ Protected endpoint accessible")
        print(f"   Symbol: {result.get('symbol', 'N/A')}")
        print(f"   Price: {result.get('current_price', 'N/A')}")
    else:
        print("❌ Protected endpoint access failed")


def logout_user(token: str):
    """Logout user."""
    print("👋 Logging out user...")
    
    result = make_request("POST", "/auth/logout", token=token)
    if result:
        print(f"✅ Logout successful: {result['message']}")
    else:
        print("❌ Logout failed")


def main():
    """Main demo function."""
    print("🚀 InsightFinance API Authentication Demo")
    print("=" * 50)
    
    # Test API health
    if not test_health():
        print("❌ API is not running. Please start the server first:")
        print("   uvicorn app.main:app --reload")
        sys.exit(1)
    
    print()
    
    # Demo user credentials
    email = "demo@insightfinance.com"
    password = "DemoPass123!"
    
    # Step 1: Register user
    register_result = register_user(email, password)
    if not register_result:
        print("❌ Demo failed at registration step")
        sys.exit(1)
    
    token = register_result["token"]["access_token"]
    print()
    
    # Step 2: Get user profile
    get_user_profile(token)
    print()
    
    # Step 3: Test protected endpoint
    test_protected_endpoint(token)
    print()
    
    # Step 4: Refresh token
    refresh_result = refresh_token(token)
    if refresh_result:
        token = refresh_result["access_token"]  # Use new token
    print()
    
    # Step 5: Test with new token
    test_protected_endpoint(token)
    print()
    
    # Step 6: Logout
    logout_user(token)
    print()
    
    # Step 7: Test login with existing user
    login_result = login_user(email, password)
    if login_result:
        new_token = login_result["access_token"]
        test_protected_endpoint(new_token)
    
    print()
    print("🎉 Authentication demo completed successfully!")
    print()
    print("Next steps:")
    print("- Try the Swagger UI: http://localhost:8000/docs")
    print("- Test different endpoints with your token")
    print("- Check the logs for security events")


if __name__ == "__main__":
    main()

