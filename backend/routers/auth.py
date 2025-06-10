from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional

import models
import schemas
from database import SessionLocal
from auth import (
    get_db, get_password_hash, authenticate_user, create_access_token,
    create_refresh_token, verify_token, revoke_refresh_token, blacklist_token,
    security, get_current_user, cleanup_expired_tokens
)
from config import ACCESS_TOKEN_EXPIRE_DELTA, SECRET_KEY, ALGORITHM
from jose import JWTError, jwt

router = APIRouter(prefix="/api/auth", tags=["authentication"])

@router.post("/register", response_model=schemas.User)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    # Check if user already exists
    existing_user = db.query(models.User).filter(
        (models.User.email == user.email) | (models.User.username == user.username)
    ).first()
    
    if existing_user:
        if existing_user.email == user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

@router.post("/login", response_model=schemas.Token)
def login(login_request: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Login and receive access and refresh tokens."""
    # Clean up expired tokens periodically
    cleanup_expired_tokens(db)
    
    user = authenticate_user(db, login_request.username, login_request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create tokens
    access_token_data = {
        "sub": user.id,
        "username": user.username,
        "role": user.role
    }
    access_token = create_access_token(access_token_data)
    refresh_token = create_refresh_token(user.id, db)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh", response_model=schemas.Token)
def refresh_token(
    refresh_request: schemas.RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token."""
    # Find refresh token in database
    db_token = db.query(models.RefreshToken).filter(
        models.RefreshToken.token == refresh_request.refresh_token,
        models.RefreshToken.revoked == False
    ).first()
    
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Check if token is expired
    if db_token.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired"
        )
    
    # Get user
    user = db.query(models.User).filter(models.User.id == db_token.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Revoke old refresh token
    db_token.revoked = True
    db.commit()
    
    # Create new tokens
    access_token_data = {
        "sub": user.id,
        "username": user.username,
        "role": user.role
    }
    access_token = create_access_token(access_token_data)
    new_refresh_token = create_refresh_token(user.id, db)
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }

@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Logout user by blacklisting the access token."""
    token = credentials.credentials
    
    try:
        # Verify token and get expiration
        token_data = verify_token(token, db)
        
        # Blacklist the token
        blacklist_token(token, token_data.exp, db)
        
        return {"message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to logout"
        )

@router.get("/me", response_model=schemas.User)
def get_current_user_info(current_user: models.User = Depends(get_current_user)):
    """Get current user information."""
    return current_user

@router.post("/password-reset-request")
def request_password_reset(
    reset_request: schemas.PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """Request a password reset token."""
    user = db.query(models.User).filter(models.User.email == reset_request.email).first()
    
    # Don't reveal if email exists or not
    if user:
        # In a real application, you would send an email here
        # For now, we'll just create a reset token
        reset_token_data = {
            "sub": user.id,
            "purpose": "password_reset"
        }
        reset_token = create_access_token(
            reset_token_data,
            expires_delta=timedelta(hours=1)
        )
        
        # In production, send this token via email
        # For development, we'll return it (DO NOT DO THIS IN PRODUCTION)
        return {
            "message": "If the email exists, a password reset link has been sent",
            "reset_token": reset_token  # Remove this in production
        }
    
    return {"message": "If the email exists, a password reset link has been sent"}

@router.post("/password-reset-confirm")
def confirm_password_reset(
    reset_confirm: schemas.PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """Reset password using reset token."""
    try:
        # Decode reset token
        payload = jwt.decode(reset_confirm.token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        purpose = payload.get("purpose")
        
        if purpose != "password_reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token"
            )
        
        # Get user and update password
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update password
        user.hashed_password = get_password_hash(reset_confirm.new_password)
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
        
        return {"message": "Password successfully reset"}
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )