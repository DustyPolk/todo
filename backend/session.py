"""
Session management middleware and utilities.
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from cache import cache_service, SessionData
from config import SESSION_TTL
import models

class SessionMiddleware(BaseHTTPMiddleware):
    """Middleware for session management."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request with session handling."""
        # Extract session ID from headers or cookies
        session_id = None
        
        # Try to get session from Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Session "):
            session_id = auth_header.replace("Session ", "")
        
        # Try to get session from cookie
        if not session_id:
            session_id = request.cookies.get("session_id")
        
        # Try to get session from custom header
        if not session_id:
            session_id = request.headers.get("X-Session-ID")
        
        # Add session to request state
        request.state.session_id = session_id
        request.state.session = None
        
        if session_id:
            session = await cache_service.get_session(session_id)
            request.state.session = session
        
        response = await call_next(request)
        
        # Add session headers to response
        if hasattr(request.state, 'new_session_id'):
            response.headers["X-Session-ID"] = request.state.new_session_id
            # Also set as cookie (optional)
            response.set_cookie(
                "session_id", 
                request.state.new_session_id,
                max_age=SESSION_TTL,
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="lax"
            )
        
        return response

class SessionManager:
    """Session management utilities."""
    
    @staticmethod
    def generate_session_id() -> str:
        """Generate a secure session ID."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    async def create_session(user: models.User, additional_data: Dict[str, Any] = None) -> str:
        """Create a new session for a user."""
        session_id = SessionManager.generate_session_id()
        
        success = await cache_service.create_session(
            session_id=session_id,
            user_id=user.id,
            username=user.username,
            role=user.role,
            session_data=additional_data or {}
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session"
            )
        
        return session_id
    
    @staticmethod
    async def get_session(session_id: str) -> Optional[SessionData]:
        """Get session data."""
        return await cache_service.get_session(session_id)
    
    @staticmethod
    async def update_session(session_id: str, data: Dict[str, Any]) -> bool:
        """Update session data."""
        return await cache_service.update_session(session_id, data)
    
    @staticmethod
    async def delete_session(session_id: str) -> bool:
        """Delete a session."""
        return await cache_service.delete_session(session_id)
    
    @staticmethod
    async def cleanup_expired_sessions() -> int:
        """Clean up expired sessions."""
        return await cache_service.cleanup_expired_sessions()

# Session dependency for FastAPI
async def get_current_session(request: Request) -> Optional[SessionData]:
    """Get current session from request."""
    return getattr(request.state, 'session', None)

async def require_session(request: Request) -> SessionData:
    """Require a valid session."""
    session = await get_current_session(request)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid session required"
        )
    return session

async def get_session_user_id(request: Request) -> Optional[int]:
    """Get user ID from session."""
    session = await get_current_session(request)
    return session.user_id if session else None

async def require_session_user_id(request: Request) -> int:
    """Require session and return user ID."""
    session = await require_session(request)
    return session.user_id

# Session-based authentication (alternative to JWT)
class SessionAuth:
    """Session-based authentication handler."""
    
    def __init__(self):
        self.security = HTTPBearer(auto_error=False)
    
    async def __call__(self, request: Request) -> Optional[models.User]:
        """Authenticate user via session."""
        session = await get_current_session(request)
        if not session:
            return None
        
        # Get user from database (could be cached)
        from auth import get_db
        db = next(get_db())
        
        try:
            user = db.query(models.User).filter(models.User.id == session.user_id).first()
            if user and user.is_active:
                return user
            return None
        finally:
            db.close()

# Mixed authentication (JWT or Session)
class MixedAuth:
    """Support both JWT and Session authentication."""
    
    def __init__(self):
        self.jwt_auth = HTTPBearer(auto_error=False)
        self.session_auth = SessionAuth()
    
    async def __call__(self, request: Request) -> Optional[models.User]:
        """Authenticate user via JWT or Session."""
        # Try JWT first
        credentials = await self.jwt_auth(request)
        if credentials:
            # Use existing JWT authentication
            from auth import verify_token, get_db
            db = next(get_db())
            try:
                token_data = verify_token(credentials.credentials, db)
                user = db.query(models.User).filter(models.User.id == token_data.user_id).first()
                if user and user.is_active:
                    return user
            except:
                pass  # Fall through to session auth
            finally:
                db.close()
        
        # Try session authentication
        return await self.session_auth(request)

# Global instances
session_manager = SessionManager()
session_auth = SessionAuth()
mixed_auth = MixedAuth()

# Session utility functions
async def login_with_session(user: models.User, request: Request, 
                             additional_data: Dict[str, Any] = None) -> str:
    """Login user and create session."""
    session_id = await session_manager.create_session(user, additional_data)
    
    # Add session ID to request state for middleware
    request.state.new_session_id = session_id
    
    return session_id

async def logout_session(request: Request) -> bool:
    """Logout current session."""
    session_id = getattr(request.state, 'session_id', None)
    if session_id:
        return await session_manager.delete_session(session_id)
    return False

async def refresh_session(request: Request) -> bool:
    """Refresh current session TTL."""
    session_id = getattr(request.state, 'session_id', None)
    if session_id:
        session = await session_manager.get_session(session_id)
        if session:
            # Update last accessed time (automatically done in get_session)
            return True
    return False

# Session decorators
def require_session_decorator(func):
    """Decorator to require valid session."""
    async def wrapper(*args, **kwargs):
        # Extract request from args
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        
        if not request:
            raise ValueError("Request object not found in function arguments")
        
        await require_session(request)
        return await func(*args, **kwargs)
    
    return wrapper

def session_user_required(func):
    """Decorator to require session user."""
    async def wrapper(*args, **kwargs):
        # Extract request from args
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        
        if not request:
            raise ValueError("Request object not found in function arguments")
        
        user_id = await require_session_user_id(request)
        # Add user_id to kwargs if not present
        if 'user_id' not in kwargs:
            kwargs['user_id'] = user_id
        
        return await func(*args, **kwargs)
    
    return wrapper