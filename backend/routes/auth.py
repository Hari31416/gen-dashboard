from datetime import timedelta, datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from utilities.auth import (
    authenticate_user,
    create_access_token,
    decode_token,
    get_user,
    create_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from services.database.user_database import (
    is_admin,
    list_all_users,
    extend_user_expiry,
    set_user_expiry,
    set_user_role,
    set_user_token_limit,
    delete_user_from_db,
    is_user_expired,
    ROLE_ADMIN,
    ROLE_USER,
)
from utilities import create_simple_logger

logger = create_simple_logger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    role: Optional[str] = None
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    account_validity_days: Optional[int] = None
    max_token_limit_millions: Optional[float] = None


class UserInDB(User):
    hashed_password: str


class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = ROLE_USER
    account_validity_days: Optional[int] = None
    max_token_limit_millions: Optional[float] = None


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None


class ExtendExpiryRequest(BaseModel):
    username: str
    additional_days: int


class SetExpiryRequest(BaseModel):
    username: str
    expires_at: str  # ISO format datetime string


class SetRoleRequest(BaseModel):
    username: str
    role: str


class SetTokenLimitRequest(BaseModel):
    username: str
    max_token_limit_millions: float


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Dependency to get the current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    user_dict = get_user(username)
    if user_dict is None:
        raise credentials_exception

    return User(**user_dict)


async def get_current_user_ws(token: str) -> User:
    """
    Dependency to get the current authenticated user from JWT token for WebSockets.
    WebSockets cannot use the Authorization header easily, so we pass token in query param.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    user_dict = get_user(username)
    if user_dict is None:
        raise credentials_exception

    if is_user_expired(user_dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account has expired",
        )

    return User(**user_dict)


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency to get current active (non-disabled) user"""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Dependency to ensure the current user is an admin"""
    user_dict = get_user(current_user.username)
    if not user_dict or not is_admin(user_dict):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible token login endpoint
    Uses form data with username and password
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        # Check if the account exists but is expired
        user_dict = get_user(form_data.username)
        if user_dict and is_user_expired(user_dict):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account has expired. Please contact administrator to renew.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )

    logger.info(f"User {user['username']} logged in successfully")

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    return current_user


@router.get("/me/usage")
async def get_my_usage(current_user: User = Depends(get_current_active_user)):
    """
    Get current user's usage statistics including token limit info.
    Returns tokens used, token limit, and percentage used.
    """
    try:
        from services.usage_service import get_user_usage_with_limit

        usage_stats = get_user_usage_with_limit(current_user.username)
        logger.info(f"User {current_user.username} fetched their usage stats")
        return usage_stats
    except Exception as e:
        logger.error(
            f"Error fetching usage stats for {current_user.username}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching usage statistics",
        )


@router.post("/verify")
async def verify_token(current_user: User = Depends(get_current_active_user)):
    """Verify if a token is valid"""
    return {"valid": True, "username": current_user.username}


# ============================================================================
# ADMIN-ONLY ENDPOINTS
# ============================================================================


@router.post(
    "/admin/create-user", response_model=User, status_code=status.HTTP_201_CREATED
)
async def admin_create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_admin_user),
):
    """
    Create a new user (admin only)
    Admins can create users with any role and set custom expiry
    """
    try:
        new_user = create_user(
            username=user_data.username,
            password=user_data.password,
            email=user_data.email,
            full_name=user_data.full_name,
            role=user_data.role or ROLE_USER,
            account_validity_days=user_data.account_validity_days,
            max_token_limit_millions=user_data.max_token_limit_millions,
        )
        logger.info(
            f"Admin {current_user.username} created user: {new_user['username']} with role {user_data.role}"
        )
        return new_user
    except ValueError as e:
        logger.warning(f"Admin user creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error during admin user creation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during user creation",
        )


@router.get("/admin/users", response_model=List[User])
async def admin_list_users(current_user: User = Depends(get_current_admin_user)):
    """
    List all users (admin only)
    """
    try:
        users = list_all_users()
        logger.info(f"Admin {current_user.username} listed all users")
        return users
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching users",
        )


@router.post("/admin/extend-expiry")
async def admin_extend_expiry(
    request: ExtendExpiryRequest,
    current_user: User = Depends(get_current_admin_user),
):
    """
    Extend a user's account expiry (admin only)
    """
    try:
        if request.additional_days <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Additional days must be positive",
            )

        success = extend_user_expiry(request.username, request.additional_days)
        if success:
            logger.info(
                f"Admin {current_user.username} extended expiry for {request.username} by {request.additional_days} days"
            )
            return {
                "message": f"Successfully extended expiry for user '{request.username}' by {request.additional_days} days"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{request.username}' not found",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extending expiry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while extending expiry",
        )


@router.post("/admin/set-expiry")
async def admin_set_expiry(
    request: SetExpiryRequest,
    current_user: User = Depends(get_current_admin_user),
):
    """
    Set a specific expiry date for a user (admin only)
    """
    try:
        # Parse ISO format datetime string
        expires_at = datetime.fromisoformat(request.expires_at.replace("Z", "+00:00"))

        success = set_user_expiry(request.username, expires_at)
        if success:
            logger.info(
                f"Admin {current_user.username} set expiry for {request.username} to {expires_at}"
            )
            return {
                "message": f"Successfully set expiry for user '{request.username}' to {expires_at.strftime('%Y-%m-%d')}"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{request.username}' not found",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid datetime format: {str(e)}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting expiry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while setting expiry",
        )


@router.post("/admin/set-role")
async def admin_set_role(
    request: SetRoleRequest,
    current_user: User = Depends(get_current_admin_user),
):
    """
    Set a user's role (admin only)
    """
    try:
        # Prevent admin from changing their own role
        if request.username == current_user.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change your own role",
            )

        success = set_user_role(request.username, request.role)
        if success:
            logger.info(
                f"Admin {current_user.username} set role for {request.username} to {request.role}"
            )
            return {
                "message": f"Successfully set role for user '{request.username}' to '{request.role}'"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{request.username}' not found or invalid role",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while setting role",
        )


@router.post("/admin/set-token-limit")
async def admin_set_token_limit(
    request: SetTokenLimitRequest,
    current_user: User = Depends(get_current_admin_user),
):
    """
    Set a user's maximum token limit in millions (admin only)
    Use -1 for unlimited tokens.
    """
    try:
        success = set_user_token_limit(
            request.username, request.max_token_limit_millions
        )
        if success:
            limit_str = (
                "unlimited"
                if request.max_token_limit_millions == -1
                else f"{request.max_token_limit_millions}M"
            )
            logger.info(
                f"Admin {current_user.username} set token limit for {request.username} to {limit_str}"
            )
            return {
                "message": f"Successfully set token limit for user '{request.username}' to {limit_str}"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{request.username}' not found",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting token limit: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while setting token limit",
        )


@router.delete("/admin/delete-user/{username}")
async def admin_delete_user(
    username: str,
    current_user: User = Depends(get_current_admin_user),
):
    """
    Delete a user (admin only)
    """
    try:
        # Prevent admin from deleting themselves
        if username == current_user.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account",
            )

        success = delete_user_from_db(username)
        if success:
            logger.info(f"Admin {current_user.username} deleted user: {username}")
            return {"message": f"Successfully deleted user '{username}'"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{username}' not found",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting user",
        )


@router.get("/admin/usage")
async def admin_get_usage(current_user: User = Depends(get_current_admin_user)):
    """
    Get usage statistics for all users (admin only)
    """
    try:
        from services.usage_service import get_all_users_usage

        usage_stats = get_all_users_usage()
        logger.info(
            f"Admin {current_user.username} fetched usage stats for {len(usage_stats)} users"
        )
        return usage_stats
    except Exception as e:
        logger.error(f"Error fetching usage stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching usage statistics",
        )


@router.get("/admin/usage/{username}/breakdown")
async def admin_get_user_token_breakdown(
    username: str,
    group_by: str = "tag",
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get token usage breakdown for a specific user (admin only)

    Args:
        username: Username to get breakdown for
        group_by: How to group breakdown - "tag", "model", or "both"
    """
    if group_by not in ["tag", "model", "both"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="group_by must be 'tag', 'model', or 'both'",
        )

    try:
        from services.usage_service import get_user_token_breakdown

        breakdown = get_user_token_breakdown(username, group_by)
        logger.info(
            f"Admin {current_user.username} fetched token breakdown for user {username} (group_by={group_by})"
        )
        return breakdown
    except Exception as e:
        logger.error(f"Error fetching token breakdown for {username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching token breakdown",
        )


@router.get("/admin/usage/daily")
async def admin_get_daily_usage(
    days: int = 30,
    username: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get daily usage statistics (admin only)
    Optionally filter by username
    """
    try:
        from services.usage_service import get_daily_usage_stats

        daily_stats = get_daily_usage_stats(days, username)
        log_msg = f"Admin {current_user.username} fetched daily usage stats for last {days} days"
        if username:
            log_msg += f" for user {username}"
        logger.info(log_msg)
        return daily_stats
    except Exception as e:
        logger.error(f"Error fetching daily usage stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching daily usage statistics",
        )
