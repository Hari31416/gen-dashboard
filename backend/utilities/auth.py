import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from services.database.user_database import (
    ROLE_USER,
    create_user_in_db,
    get_user_from_db,
    is_user_expired,
    user_exists,
)

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Get a user by username from MongoDB"""
    return get_user_from_db(username)


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user with username and password"""
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    if user.get("disabled", False):
        return None
    # Check if account has expired
    if is_user_expired(user):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def create_user(
    username: str,
    password: str,
    email: Optional[str] = None,
    full_name: Optional[str] = None,
    role: str = ROLE_USER,
    account_validity_days: Optional[int] = None,
    max_token_limit_millions: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Create a new user in MongoDB
    Returns the created user dict or raises ValueError if user exists

    Args:
        username: Unique username
        password: Plain text password (will be hashed)
        email: User email (optional)
        full_name: User's full name (optional)
        role: User role (admin or user)
        account_validity_days: Number of days until account expires
        max_token_limit_millions: Maximum token limit in millions (-1 for unlimited)
    """
    # Validate username
    if not username or len(username) < 3:
        raise ValueError("Username must be at least 3 characters long")

    # make sure that no spaces in username
    if " " in username:
        raise ValueError("Username cannot contain spaces")

    # Validate password
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters long")

    # Hash password
    hashed_password = get_password_hash(password)

    # Create user in MongoDB (will raise ValueError if user exists)
    return create_user_in_db(
        username=username,
        hashed_password=hashed_password,
        email=email,
        full_name=full_name,
        disabled=False,
        role=role,
        account_validity_days=account_validity_days,
        max_token_limit_millions=max_token_limit_millions,
    )
