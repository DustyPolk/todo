"""
Security middleware and utilities for API protection.
"""
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from secure import Secure
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
import hashlib
import secrets
from typing import Dict, Set
import re
from datetime import datetime, timedelta

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)

# Security headers configuration
secure_headers = Secure(
    csp="default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' https:; connect-src 'self'; frame-ancestors 'none';",
    hsts="max-age=31536000; includeSubDomains",
    referrer="strict-origin-when-cross-origin",
    cache="no-cache, no-store, must-revalidate",
    content="nosniff"
)

class SecurityMiddleware(BaseHTTPMiddleware):
    """Custom security middleware for additional protections."""
    
    def __init__(self, app, api_keys: Set[str] = None):
        super().__init__(app)
        self.api_keys = api_keys or set()
        self.blocked_ips: Set[str] = set()
        self.failed_attempts: Dict[str, int] = {}
        self.attempt_timestamps: Dict[str, datetime] = {}
        
    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = get_remote_address(request)
        
        # Check if IP is blocked
        if client_ip in self.blocked_ips:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "IP address blocked due to suspicious activity"}
            )
        
        # Input validation and sanitization
        await self._validate_request(request)
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        secure_headers.framework.fastapi(response)
        
        # Add custom security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        return response
    
    async def _validate_request(self, request: Request):
        """Validate and sanitize incoming requests."""
        # Check for common injection patterns
        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',  # XSS
            r'javascript:',  # JavaScript injection
            r'on\w+\s*=',  # Event handlers
            r'UNION\s+SELECT',  # SQL injection
            r'DROP\s+TABLE',  # SQL injection
            r'INSERT\s+INTO',  # SQL injection
            r'DELETE\s+FROM',  # SQL injection
        ]
        
        # Check URL path
        path = str(request.url.path)
        for pattern in dangerous_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid request format"
                )
        
        # Check query parameters
        for key, value in request.query_params.items():
            for pattern in dangerous_patterns:
                if re.search(pattern, str(value), re.IGNORECASE):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid query parameter"
                    )
        
        # Validate Content-Length to prevent large payloads
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Request payload too large"
            )

class CSRFProtection:
    """CSRF protection implementation."""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.tokens: Dict[str, datetime] = {}
        
    def generate_token(self, session_id: str) -> str:
        """Generate a CSRF token for a session."""
        timestamp = str(int(time.time()))
        token_data = f"{session_id}:{timestamp}"
        token_hash = hashlib.sha256(
            f"{self.secret_key}:{token_data}".encode()
        ).hexdigest()
        token = f"{timestamp}:{token_hash}"
        
        # Store token with expiration (1 hour)
        self.tokens[token] = datetime.utcnow() + timedelta(hours=1)
        return token
    
    def validate_token(self, token: str, session_id: str) -> bool:
        """Validate a CSRF token."""
        if not token or token not in self.tokens:
            return False
        
        # Check if token is expired
        if datetime.utcnow() > self.tokens[token]:
            del self.tokens[token]
            return False
        
        try:
            timestamp, token_hash = token.split(":", 1)
            token_data = f"{session_id}:{timestamp}"
            expected_hash = hashlib.sha256(
                f"{self.secret_key}:{token_data}".encode()
            ).hexdigest()
            
            return token_hash == expected_hash
        except ValueError:
            return False
    
    def cleanup_expired_tokens(self):
        """Remove expired tokens."""
        now = datetime.utcnow()
        expired_tokens = [
            token for token, expiry in self.tokens.items()
            if now > expiry
        ]
        for token in expired_tokens:
            del self.tokens[token]

class APIKeyAuth:
    """API Key authentication for programmatic access."""
    
    def __init__(self):
        self.api_keys: Dict[str, Dict] = {}
    
    def create_api_key(self, user_id: int, name: str, permissions: list = None) -> str:
        """Create a new API key."""
        api_key = f"todo_{secrets.token_urlsafe(32)}"
        self.api_keys[api_key] = {
            "user_id": user_id,
            "name": name,
            "permissions": permissions or ["read", "write"],
            "created_at": datetime.utcnow(),
            "last_used": None,
            "active": True
        }
        return api_key
    
    def validate_api_key(self, api_key: str) -> Dict:
        """Validate an API key and return associated data."""
        if api_key not in self.api_keys:
            return None
        
        key_data = self.api_keys[api_key]
        if not key_data["active"]:
            return None
        
        # Update last used timestamp
        key_data["last_used"] = datetime.utcnow()
        return key_data
    
    def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an API key."""
        if api_key in self.api_keys:
            self.api_keys[api_key]["active"] = False
            return True
        return False

# Rate limiting decorators for different endpoints
def rate_limit_auth():
    """Rate limit for authentication endpoints."""
    return limiter.limit("5/minute")

def rate_limit_api():
    """Rate limit for API endpoints."""
    return limiter.limit("100/minute")

def rate_limit_public():
    """Rate limit for public endpoints."""
    return limiter.limit("1000/hour")

# Input sanitization functions
def sanitize_string(value: str, max_length: int = 1000) -> str:
    """Sanitize string input."""
    if not isinstance(value, str):
        return str(value)
    
    # Truncate to max length
    value = value[:max_length]
    
    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', '\x00']
    for char in dangerous_chars:
        value = value.replace(char, '')
    
    return value.strip()

def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_username(username: str) -> bool:
    """Validate username format."""
    # Allow alphanumeric, underscore, hyphen, 3-50 characters
    pattern = r'^[a-zA-Z0-9_-]{3,50}$'
    return re.match(pattern, username) is not None

# Security audit logging
class SecurityAuditLogger:
    """Log security-related events."""
    
    def __init__(self):
        self.events = []
    
    def log_event(self, event_type: str, user_id: int = None, ip_address: str = None, 
                  details: dict = None):
        """Log a security event."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "ip_address": ip_address,
            "details": details or {}
        }
        self.events.append(event)
        
        # In production, this would write to a proper logging system
        print(f"SECURITY EVENT: {event}")
    
    def get_events(self, event_type: str = None, user_id: int = None, 
                   hours: int = 24) -> list:
        """Get security events based on filters."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        filtered_events = []
        for event in self.events:
            event_time = datetime.fromisoformat(event["timestamp"])
            if event_time < cutoff:
                continue
                
            if event_type and event["event_type"] != event_type:
                continue
                
            if user_id and event["user_id"] != user_id:
                continue
                
            filtered_events.append(event)
        
        return filtered_events

# Global instances
csrf_protection = CSRFProtection("your-csrf-secret-key")
api_key_auth = APIKeyAuth()
security_logger = SecurityAuditLogger()