from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime
from typing import Optional, List
import re

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    role: str = "user"
    is_active: bool = True
    is_verified: bool = False

class UserCreate(UserBase):
    password: Optional[str] = Field(None, min_length=12)  # Optional for OAuth users
    
    @validator('password')
    def validate_password(cls, v):
        if v is None:  # Skip validation for OAuth users
            return v
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    role: Optional[str] = None

class User(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    oauth_provider: Optional[str] = None
    oauth_id: Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True

class UserInDB(User):
    hashed_password: Optional[str] = None

# OAuth2 Schemas
class OAuthAccount(BaseModel):
    provider: str
    provider_user_id: str
    email: Optional[str] = None
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class OAuthAuthorizationRequest(BaseModel):
    provider: str  # google or github

class OAuthAuthorizationResponse(BaseModel):
    authorization_url: str
    state: str

class OAuthCallbackRequest(BaseModel):
    code: str
    state: str

class OAuthUserInfo(BaseModel):
    id: str
    email: Optional[str]
    name: Optional[str]
    username: Optional[str]
    avatar_url: Optional[str]
    verified_email: Optional[bool] = False

class AccountLinkRequest(BaseModel):
    provider: str
    link_token: str  # Temporary token to link accounts

# Authentication Schemas
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[int] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class LoginRequest(BaseModel):
    username: str
    password: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=12)
    
    @validator('new_password')
    def validate_password(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v

# Task Schemas
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    completed: bool = False
    priority: str = "medium"
    due_date: Optional[datetime] = None

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None
    due_date: Optional[datetime] = None

class Task(TaskBase):
    id: int
    user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    owner: Optional[User] = None

    class Config:
        from_attributes = True