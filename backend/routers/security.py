"""
Security management endpoints for API keys and monitoring.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

import models
import schemas
from auth import get_current_user, check_user_role, get_db
from security import (
    api_key_auth, security_logger, rate_limit_api, csrf_protection
)

router = APIRouter(prefix="/api/security", tags=["security"])

# API Key Management Schemas
from pydantic import BaseModel

class APIKeyCreate(BaseModel):
    name: str
    permissions: Optional[List[str]] = ["read", "write"]

class APIKeyResponse(BaseModel):
    api_key: str
    name: str
    permissions: List[str]
    created_at: datetime

class APIKeyInfo(BaseModel):
    name: str
    permissions: List[str]
    created_at: datetime
    last_used: Optional[datetime]
    active: bool

class SecurityEvent(BaseModel):
    timestamp: str
    event_type: str
    user_id: Optional[int]
    ip_address: Optional[str]
    details: dict

@router.post("/api-keys", response_model=APIKeyResponse)
@rate_limit_api()
def create_api_key(
    request: Request,
    api_key_data: APIKeyCreate,
    current_user: models.User = Depends(check_user_role("user")),
    db: Session = Depends(get_db)
):
    """Create a new API key for programmatic access."""
    api_key = api_key_auth.create_api_key(
        user_id=current_user.id,
        name=api_key_data.name,
        permissions=api_key_data.permissions
    )
    
    # Log API key creation
    security_logger.log_event(
        "api_key_created",
        user_id=current_user.id,
        ip_address=request.client.host,
        details={"key_name": api_key_data.name, "permissions": api_key_data.permissions}
    )
    
    return APIKeyResponse(
        api_key=api_key,
        name=api_key_data.name,
        permissions=api_key_data.permissions,
        created_at=datetime.utcnow()
    )

@router.get("/api-keys", response_model=List[APIKeyInfo])
@rate_limit_api()
def list_api_keys(
    request: Request,
    current_user: models.User = Depends(check_user_role("user"))
):
    """List all API keys for the current user."""
    user_keys = []
    for key, data in api_key_auth.api_keys.items():
        if data["user_id"] == current_user.id:
            user_keys.append(APIKeyInfo(
                name=data["name"],
                permissions=data["permissions"],
                created_at=data["created_at"],
                last_used=data["last_used"],
                active=data["active"]
            ))
    
    return user_keys

@router.delete("/api-keys/{key_name}")
@rate_limit_api()
def revoke_api_key(
    request: Request,
    key_name: str,
    current_user: models.User = Depends(check_user_role("user"))
):
    """Revoke an API key."""
    # Find the key by name for this user
    key_to_revoke = None
    for key, data in api_key_auth.api_keys.items():
        if data["user_id"] == current_user.id and data["name"] == key_name:
            key_to_revoke = key
            break
    
    if not key_to_revoke:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    api_key_auth.revoke_api_key(key_to_revoke)
    
    # Log API key revocation
    security_logger.log_event(
        "api_key_revoked",
        user_id=current_user.id,
        ip_address=request.client.host,
        details={"key_name": key_name}
    )
    
    return {"message": "API key revoked successfully"}

@router.get("/events", response_model=List[SecurityEvent])
@rate_limit_api()
def get_security_events(
    request: Request,
    event_type: Optional[str] = None,
    hours: int = 24,
    current_user: models.User = Depends(check_user_role("admin"))
):
    """Get security events (admin only)."""
    events = security_logger.get_events(
        event_type=event_type,
        hours=hours
    )
    
    return [SecurityEvent(**event) for event in events]

@router.get("/events/me", response_model=List[SecurityEvent])
@rate_limit_api()
def get_my_security_events(
    request: Request,
    event_type: Optional[str] = None,
    hours: int = 24,
    current_user: models.User = Depends(check_user_role("user"))
):
    """Get security events for the current user."""
    events = security_logger.get_events(
        event_type=event_type,
        user_id=current_user.id,
        hours=hours
    )
    
    return [SecurityEvent(**event) for event in events]

@router.post("/csrf-token")
@rate_limit_api()
def get_csrf_token(
    request: Request,
    current_user: models.User = Depends(check_user_role("user"))
):
    """Get a CSRF token for state-changing operations."""
    session_id = f"user_{current_user.id}"
    token = csrf_protection.generate_token(session_id)
    
    return {"csrf_token": token}

@router.get("/security-status")
@rate_limit_api()
def get_security_status(
    request: Request,
    current_user: models.User = Depends(check_user_role("admin"))
):
    """Get overall security status (admin only)."""
    # Get recent security events
    recent_events = security_logger.get_events(hours=24)
    
    # Count different event types
    event_counts = {}
    for event in recent_events:
        event_type = event["event_type"]
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
    
    # Calculate security score (simplified)
    failed_logins = event_counts.get("failed_login", 0)
    successful_logins = event_counts.get("successful_login", 0)
    
    security_score = 100
    if failed_logins > 10:
        security_score -= min(failed_logins * 2, 50)
    
    status_level = "good"
    if security_score < 70:
        status_level = "warning"
    if security_score < 50:
        status_level = "critical"
    
    return {
        "security_score": security_score,
        "status": status_level,
        "event_counts": event_counts,
        "active_api_keys": len([k for k, v in api_key_auth.api_keys.items() if v["active"]]),
        "blacklisted_tokens": len(csrf_protection.tokens),
        "recommendations": [
            "Enable 2FA for admin accounts" if status_level != "good" else None,
            "Review failed login attempts" if failed_logins > 5 else None,
            "Consider rate limit adjustments" if event_counts.get("rate_limit_exceeded", 0) > 50 else None
        ]
    }