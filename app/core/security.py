"""
Security utilities: password hashing, JWT creation/verification, and dependencies.
=================================================================================

This module provides comprehensive security utilities for the InsightFinance API.
It handles password hashing, JWT token management, and user authentication.

Features:
- Secure password hashing with bcrypt
- JWT token creation and validation
- User authentication dependency injection
- Token expiration and refresh handling
- Security logging and monitoring
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Union

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.user import User

logger = get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        str: Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored hashed password
        
    Returns:
        bool: True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        subject: Token subject (usually user email)
        expires_minutes: Token expiration time in minutes
        
    Returns:
        str: Encoded JWT token
    """
    expire_delta = timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expire_delta
    
    to_encode = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),  # Issued at
        "type": "access"  # Token type
    }
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    logger.debug(f"JWT token created for subject: {subject}")
    return encoded_jwt


def create_refresh_token(subject: str, expires_days: int = 7) -> str:
    """
    Create a JWT refresh token with longer expiration.
    
    Args:
        subject: Token subject (usually user email)
        expires_days: Token expiration time in days
        
    Returns:
        str: Encoded JWT refresh token
    """
    expire_delta = timedelta(days=expires_days)
    expire = datetime.now(timezone.utc) + expire_delta
    
    to_encode = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"
    }
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    logger.debug(f"Refresh token created for subject: {subject}")
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token to verify
        token_type: Expected token type ("access" or "refresh")
        
    Returns:
        Optional[dict]: Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Verify token type
        if payload.get("type") != token_type:
            logger.warning(f"Invalid token type: expected {token_type}, got {payload.get('type')}")
            return None
            
        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
            logger.warning("Token has expired")
            return None
            
        return payload
        
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    """
    Get the current authenticated user from JWT token.
    
    This function is used as a FastAPI dependency to protect routes
    that require authentication.
    
    Args:
        token: JWT token from Authorization header
        db: Database session
        
    Returns:
        User: Current authenticated user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Verify token
        payload = verify_token(token, "access")
        if payload is None:
            raise credentials_exception
            
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
            
        # Get user from database
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if user is None:
            logger.warning(f"User not found for email: {email}")
            raise credentials_exception
            
        if not user.is_active:
            logger.warning(f"Inactive user attempted access: {email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        logger.debug(f"User authenticated: {user.email}")
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise credentials_exception


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Get the current active user (additional check for active status).
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        User: Current active user
        
    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


async def get_current_superuser(current_user: User = Depends(get_current_user)) -> User:
    """
    Get the current superuser (admin user).
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        User: Current superuser
        
    Raises:
        HTTPException: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def check_password_strength(password: str) -> dict:
    """
    Check password strength and return detailed feedback.
    
    Args:
        password: Password to check
        
    Returns:
        dict: Password strength analysis
    """
    score = 0
    feedback = []
    
    # Length check
    if len(password) >= 8:
        score += 1
    else:
        feedback.append("Password should be at least 8 characters long")
    
    # Character variety checks
    if any(c.isupper() for c in password):
        score += 1
    else:
        feedback.append("Password should contain uppercase letters")
        
    if any(c.islower() for c in password):
        score += 1
    else:
        feedback.append("Password should contain lowercase letters")
        
    if any(c.isdigit() for c in password):
        score += 1
    else:
        feedback.append("Password should contain numbers")
        
    if any(c in "!@#$%^&*(),.?\":{}|<>" for c in password):
        score += 1
    else:
        feedback.append("Password should contain special characters")
    
    # Determine strength level
    if score <= 2:
        strength = "weak"
    elif score <= 4:
        strength = "medium"
    else:
        strength = "strong"
    
    return {
        "score": score,
        "max_score": 5,
        "strength": strength,
        "feedback": feedback,
        "is_strong": score >= 4
    }


def generate_password_reset_token(email: str) -> str:
    """
    Generate a password reset token.
    
    Args:
        email: User email
        
    Returns:
        str: Password reset token
    """
    expire_delta = timedelta(hours=1)  # Reset token expires in 1 hour
    expire = datetime.now(timezone.utc) + expire_delta
    
    to_encode = {
        "sub": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "password_reset"
    }
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_password_reset_token(token: str) -> Optional[str]:
    """
    Verify a password reset token and return the email.
    
    Args:
        token: Password reset token
        
    Returns:
        Optional[str]: User email if token is valid, None otherwise
    """
    payload = verify_token(token, "password_reset")
    if payload:
        return payload.get("sub")
    return None


