"""
Authentication routes: register and login to obtain JWT.
=======================================================

This module provides user registration and authentication endpoints.
It handles user creation, password validation, and JWT token generation.

Features:
- User registration with email validation
- Secure password hashing with bcrypt
- JWT token generation and validation
- Proper error handling and status codes
- Input validation with Pydantic models
"""

from typing import Optional
import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.core.logging import get_logger
from app.models.user import User

logger = get_logger(__name__)
router = APIRouter()


class RegisterRequest(BaseModel):
    """User registration request model."""
    email: EmailStr
    password: str
    
    @validator('password')
    def validate_password(cls, v):
        """
        Validate password strength.
        
        Requirements:
        - At least 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character
        """
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        
        return v


class LoginRequest(BaseModel):
    """User login request model."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    """User profile response model."""
    id: int
    email: str
    is_active: bool
    created_at: str


class RegisterResponse(BaseModel):
    """Registration response model."""
    user: UserResponse
    token: TokenResponse
    message: str


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> RegisterResponse:
    """
    Register a new user account.
    
    This endpoint creates a new user account with the provided email and password.
    The password is securely hashed using bcrypt before storage.
    
    Args:
        payload: Registration request with email and password
        db: Database session
        
    Returns:
        RegisterResponse: User details and JWT token
        
    Raises:
        HTTPException: If email already exists or validation fails
    """
    try:
        logger.info(f"Registration attempt for email: {payload.email}")
        
        # Check if email already exists
        existing = await db.execute(select(User).where(User.email == payload.email))
        if existing.scalar_one_or_none():
            logger.warning(f"Registration failed: email {payload.email} already exists")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Email already registered"
            )
        
        # Create new user
        hashed_password = hash_password(payload.password)
        user = User(
            email=payload.email,
            hashed_password=hashed_password,
            is_active=True
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Generate JWT token
        token = create_access_token(subject=user.email)
        
        logger.info(f"User registered successfully: {user.email}")
        
        return RegisterResponse(
            user=UserResponse(
                id=user.id,
                email=user.email,
                is_active=user.is_active,
                created_at=user.created_at.isoformat()
            ),
            token=TokenResponse(
                access_token=token,
                token_type="bearer",
                expires_in=30 * 60  # 30 minutes
            ),
            message="User registered successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again."
        )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """
    Authenticate user and return JWT token.
    
    This endpoint validates user credentials and returns a JWT token
    for authenticated requests to protected endpoints.
    
    Args:
        payload: Login request with email and password
        db: Database session
        
    Returns:
        TokenResponse: JWT token and metadata
        
    Raises:
        HTTPException: If credentials are invalid
    """
    try:
        logger.info(f"Login attempt for email: {payload.email}")
        
        # Find user by email
        result = await db.execute(select(User).where(User.email == payload.email))
        user = result.scalar_one_or_none()
        
        # Validate credentials
        if user is None or not verify_password(payload.password, user.hashed_password):
            logger.warning(f"Login failed: invalid credentials for {payload.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is active
        if not user.is_active:
            logger.warning(f"Login failed: inactive user {payload.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Generate JWT token
        token = create_access_token(subject=user.email)
        
        logger.info(f"User logged in successfully: {user.email}")
        
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=30 * 60  # 30 minutes
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again."
        )


@router.post("/token", response_model=TokenResponse)
async def login_form(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """
    OAuth2 compatible login endpoint for Swagger UI.
    
    This endpoint provides OAuth2 compatibility for the Swagger UI
    authentication form. It uses the same logic as the /login endpoint.
    
    Args:
        form_data: OAuth2 form data (username=email, password)
        db: Database session
        
    Returns:
        TokenResponse: JWT token and metadata
    """
    payload = LoginRequest(email=form_data.username, password=form_data.password)
    return await login(payload, db)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)) -> UserResponse:
    """
    Get current user profile.
    
    This endpoint returns the profile information of the currently
    authenticated user based on their JWT token.
    
    Args:
        current_user: Current authenticated user from JWT token
        
    Returns:
        UserResponse: User profile information
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat()
    )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout endpoint (client-side token removal).
    
    Since JWT tokens are stateless, this endpoint serves as a
    notification that the client should remove the token.
    In a production system, you might implement token blacklisting.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        dict: Logout confirmation message
    """
    logger.info(f"User logged out: {current_user.email}")
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(current_user: User = Depends(get_current_user)) -> TokenResponse:
    """
    Refresh JWT token.
    
    This endpoint generates a new JWT token for the currently
    authenticated user, effectively extending their session.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        TokenResponse: New JWT token and metadata
    """
    token = create_access_token(subject=current_user.email)
    
    logger.info(f"Token refreshed for user: {current_user.email}")
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=30 * 60  # 30 minutes
    )


