from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import models
import schemas
from database import SessionLocal
from config import (
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_DELTA,
    REFRESH_TOKEN_EXPIRE_DELTA, BCRYPT_ROUNDS, MAX_LOGIN_ATTEMPTS,
    LOCKOUT_DURATION_DELTA
)
import secrets

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=BCRYPT_ROUNDS)

# Security scheme
security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create an access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + ACCESS_TOKEN_EXPIRE_DELTA
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(user_id: int, db: Session) -> str:
    """Create a refresh token and store it in the database."""
    # Generate a unique token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + REFRESH_TOKEN_EXPIRE_DELTA
    
    # Store in database
    db_token = models.RefreshToken(
        token=token,
        user_id=user_id,
        expires_at=expires_at
    )
    db.add(db_token)
    db.commit()
    
    return token

def verify_token(token: str, db: Session) -> schemas.TokenData:
    """Verify and decode a JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Check if token is blacklisted
        blacklisted = db.query(models.BlacklistedToken).filter(
            models.BlacklistedToken.token == token
        ).first()
        if blacklisted:
            raise credentials_exception
        
        # Decode token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        username: str = payload.get("username")
        role: str = payload.get("role")
        exp: int = payload.get("exp")
        
        if user_id is None:
            raise credentials_exception
            
        token_data = schemas.TokenData(
            user_id=user_id,
            username=username,
            role=role,
            exp=exp
        )
        return token_data
    except JWTError:
        raise credentials_exception

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> models.User:
    """Get the current authenticated user."""
    token = credentials.credentials
    token_data = verify_token(token, db)
    
    user = db.query(models.User).filter(models.User.id == token_data.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user

def get_current_active_user(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """Ensure the current user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user

def check_user_role(required_role: str):
    """Dependency to check if user has required role."""
    def role_checker(current_user: models.User = Depends(get_current_active_user)):
        role_hierarchy = {"guest": 0, "user": 1, "admin": 2}
        
        if role_hierarchy.get(current_user.role, 0) < role_hierarchy.get(required_role, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not enough permissions. Required role: {required_role}"
            )
        return current_user
    return role_checker

def authenticate_user(db: Session, username: str, password: str) -> Union[models.User, None]:
    """Authenticate a user by username and password."""
    user = db.query(models.User).filter(
        (models.User.username == username) | (models.User.email == username)
    ).first()
    
    if not user:
        return None
    
    # Check if account is locked
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked until {user.locked_until.isoformat()}"
        )
    
    # Verify password
    if not verify_password(password, user.hashed_password):
        # Increment failed login attempts
        user.failed_login_attempts += 1
        
        # Lock account if too many failed attempts
        if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.utcnow() + LOCKOUT_DURATION_DELTA
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account locked due to too many failed login attempts"
            )
        
        db.commit()
        return None
    
    # Reset failed login attempts on successful login
    if user.failed_login_attempts > 0:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
    
    return user

def revoke_refresh_token(token: str, db: Session) -> bool:
    """Revoke a refresh token."""
    db_token = db.query(models.RefreshToken).filter(
        models.RefreshToken.token == token
    ).first()
    
    if db_token:
        db_token.revoked = True
        db.commit()
        return True
    return False

def blacklist_token(token: str, expires_at: datetime, db: Session):
    """Add a token to the blacklist."""
    blacklisted = models.BlacklistedToken(
        token=token,
        expires_at=expires_at
    )
    db.add(blacklisted)
    db.commit()

def cleanup_expired_tokens(db: Session):
    """Remove expired tokens from the database."""
    now = datetime.utcnow()
    
    # Remove expired refresh tokens
    db.query(models.RefreshToken).filter(
        models.RefreshToken.expires_at < now
    ).delete()
    
    # Remove expired blacklisted tokens
    db.query(models.BlacklistedToken).filter(
        models.BlacklistedToken.expires_at < now
    ).delete()
    
    db.commit()