"""
OAuth2 integration service for Google and GitHub authentication.
"""
import httpx
import secrets
from urllib.parse import urlencode
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from itsdangerous import URLSafeTimedSerializer, BadSignature
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

import models
import schemas
from auth import get_password_hash, create_access_token, create_refresh_token
from config import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_DISCOVERY_URL, GOOGLE_REDIRECT_URI,
    GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_AUTHORIZE_URL, 
    GITHUB_TOKEN_URL, GITHUB_USER_URL, GITHUB_REDIRECT_URI,
    OAUTH_STATE_SECRET
)
from security import security_logger

class OAuthProvider:
    """Base OAuth provider class."""
    
    def __init__(self, name: str):
        self.name = name
        self.state_serializer = URLSafeTimedSerializer(OAUTH_STATE_SECRET)
    
    def generate_state(self, user_id: Optional[int] = None) -> str:
        """Generate a secure state parameter."""
        data = {
            "provider": self.name,
            "nonce": secrets.token_urlsafe(16),
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        return self.state_serializer.dumps(data)
    
    def verify_state(self, state: str, max_age: int = 600) -> Dict:
        """Verify and decode state parameter."""
        try:
            return self.state_serializer.loads(state, max_age=max_age)
        except BadSignature:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired state parameter"
            )
    
    async def get_authorization_url(self, scopes: list = None) -> Tuple[str, str]:
        """Generate authorization URL and state."""
        raise NotImplementedError
    
    async def exchange_code_for_token(self, code: str, state: str) -> Dict:
        """Exchange authorization code for access token."""
        raise NotImplementedError
    
    async def get_user_info(self, access_token: str) -> schemas.OAuthUserInfo:
        """Get user information from provider."""
        raise NotImplementedError

class GoogleOAuthProvider(OAuthProvider):
    """Google OAuth2 provider implementation."""
    
    def __init__(self):
        super().__init__("google")
        self.client_id = GOOGLE_CLIENT_ID
        self.client_secret = GOOGLE_CLIENT_SECRET
        self.redirect_uri = GOOGLE_REDIRECT_URI
        self.discovery_cache = {}
        self.discovery_cache_time = None
    
    async def _get_discovery_document(self) -> Dict:
        """Get Google's OpenID Connect discovery document."""
        # Cache discovery document for 1 hour
        if (self.discovery_cache_time and 
            datetime.utcnow() - self.discovery_cache_time < timedelta(hours=1)):
            return self.discovery_cache
        
        async with httpx.AsyncClient() as client:
            response = await client.get(GOOGLE_DISCOVERY_URL)
            response.raise_for_status()
            self.discovery_cache = response.json()
            self.discovery_cache_time = datetime.utcnow()
            return self.discovery_cache
    
    async def get_authorization_url(self, scopes: list = None) -> Tuple[str, str]:
        """Generate Google authorization URL."""
        if not self.client_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Google OAuth not configured"
            )
        
        discovery = await self._get_discovery_document()
        auth_endpoint = discovery["authorization_endpoint"]
        
        state = self.generate_state()
        scopes = scopes or ["openid", "email", "profile"]
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes),
            "response_type": "code",
            "state": state,
            "access_type": "offline",
            "prompt": "consent"
        }
        
        auth_url = f"{auth_endpoint}?{urlencode(params)}"
        return auth_url, state
    
    async def exchange_code_for_token(self, code: str, state: str) -> Dict:
        """Exchange authorization code for Google access token."""
        self.verify_state(state)
        
        discovery = await self._get_discovery_document()
        token_endpoint = discovery["token_endpoint"]
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(token_endpoint, data=data)
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> schemas.OAuthUserInfo:
        """Get user information from Google."""
        discovery = await self._get_discovery_document()
        userinfo_endpoint = discovery["userinfo_endpoint"]
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(userinfo_endpoint, headers=headers)
            response.raise_for_status()
            user_data = response.json()
        
        return schemas.OAuthUserInfo(
            id=user_data["sub"],
            email=user_data.get("email"),
            name=user_data.get("name"),
            username=user_data.get("preferred_username"),
            avatar_url=user_data.get("picture"),
            verified_email=user_data.get("email_verified", False)
        )

class GitHubOAuthProvider(OAuthProvider):
    """GitHub OAuth2 provider implementation."""
    
    def __init__(self):
        super().__init__("github")
        self.client_id = GITHUB_CLIENT_ID
        self.client_secret = GITHUB_CLIENT_SECRET
        self.redirect_uri = GITHUB_REDIRECT_URI
    
    async def get_authorization_url(self, scopes: list = None) -> Tuple[str, str]:
        """Generate GitHub authorization URL."""
        if not self.client_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GitHub OAuth not configured"
            )
        
        state = self.generate_state()
        scopes = scopes or ["user:email"]
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
            "allow_signup": "true"
        }
        
        auth_url = f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"
        return auth_url, state
    
    async def exchange_code_for_token(self, code: str, state: str) -> Dict:
        """Exchange authorization code for GitHub access token."""
        self.verify_state(state)
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code
        }
        
        headers = {"Accept": "application/json"}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(GITHUB_TOKEN_URL, data=data, headers=headers)
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> schemas.OAuthUserInfo:
        """Get user information from GitHub."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        async with httpx.AsyncClient() as client:
            # Get user profile
            user_response = await client.get(GITHUB_USER_URL, headers=headers)
            user_response.raise_for_status()
            user_data = user_response.json()
            
            # Get user emails
            emails_response = await client.get(f"{GITHUB_USER_URL}/emails", headers=headers)
            emails_response.raise_for_status()
            emails_data = emails_response.json()
            
            # Find primary email
            primary_email = None
            verified_email = False
            for email_info in emails_data:
                if email_info.get("primary", False):
                    primary_email = email_info["email"]
                    verified_email = email_info.get("verified", False)
                    break
        
        return schemas.OAuthUserInfo(
            id=str(user_data["id"]),
            email=primary_email or user_data.get("email"),
            name=user_data.get("name"),
            username=user_data.get("login"),
            avatar_url=user_data.get("avatar_url"),
            verified_email=verified_email
        )

class OAuthService:
    """OAuth service for managing OAuth authentication."""
    
    def __init__(self):
        self.providers = {
            "google": GoogleOAuthProvider(),
            "github": GitHubOAuthProvider()
        }
        self.link_token_serializer = URLSafeTimedSerializer(OAUTH_STATE_SECRET)
    
    def get_provider(self, provider_name: str) -> OAuthProvider:
        """Get OAuth provider by name."""
        if provider_name not in self.providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported OAuth provider: {provider_name}"
            )
        return self.providers[provider_name]
    
    async def get_authorization_url(self, provider_name: str) -> schemas.OAuthAuthorizationResponse:
        """Get authorization URL for a provider."""
        provider = self.get_provider(provider_name)
        auth_url, state = await provider.get_authorization_url()
        
        return schemas.OAuthAuthorizationResponse(
            authorization_url=auth_url,
            state=state
        )
    
    async def handle_callback(self, provider_name: str, code: str, state: str, db: Session) -> schemas.Token:
        """Handle OAuth callback and create/login user."""
        provider = self.get_provider(provider_name)
        
        # Exchange code for token
        token_data = await provider.exchange_code_for_token(code, state)
        access_token = token_data["access_token"]
        
        # Get user info
        user_info = await provider.get_user_info(access_token)
        
        # Find or create user
        user = await self._find_or_create_user(provider_name, user_info, token_data, db)
        
        # Log OAuth login
        security_logger.log_event(
            "oauth_login",
            user_id=user.id,
            details={
                "provider": provider_name,
                "oauth_id": user_info.id,
                "email": user_info.email
            }
        )
        
        # Create JWT tokens
        jwt_data = {
            "sub": user.id,
            "username": user.username,
            "role": user.role
        }
        jwt_access_token = create_access_token(jwt_data)
        jwt_refresh_token = create_refresh_token(user.id, db)
        
        return schemas.Token(
            access_token=jwt_access_token,
            refresh_token=jwt_refresh_token,
            token_type="bearer"
        )
    
    async def _find_or_create_user(self, provider: str, user_info: schemas.OAuthUserInfo, 
                                   token_data: Dict, db: Session) -> models.User:
        """Find existing user or create new one."""
        # Try to find existing OAuth account
        oauth_account = db.query(models.OAuthAccount).filter(
            models.OAuthAccount.provider == provider,
            models.OAuthAccount.provider_user_id == user_info.id
        ).first()
        
        if oauth_account:
            # Update OAuth account with new token
            oauth_account.access_token = token_data.get("access_token")
            oauth_account.refresh_token = token_data.get("refresh_token")
            oauth_account.updated_at = datetime.utcnow()
            db.commit()
            return oauth_account.user
        
        # Try to find user by email for account linking
        existing_user = None
        if user_info.email:
            existing_user = db.query(models.User).filter(
                models.User.email == user_info.email
            ).first()
        
        if existing_user:
            # Link OAuth account to existing user
            new_oauth_account = models.OAuthAccount(
                user_id=existing_user.id,
                provider=provider,
                provider_user_id=user_info.id,
                email=user_info.email,
                username=user_info.username,
                avatar_url=user_info.avatar_url,
                access_token=token_data.get("access_token"),
                refresh_token=token_data.get("refresh_token"),
                provider_data=token_data
            )
            db.add(new_oauth_account)
            
            # Update user with OAuth info if not set
            if not existing_user.avatar_url and user_info.avatar_url:
                existing_user.avatar_url = user_info.avatar_url
            if not existing_user.is_verified and user_info.verified_email:
                existing_user.is_verified = True
            
            db.commit()
            return existing_user
        
        # Create new user
        username = user_info.username or user_info.email.split("@")[0] if user_info.email else f"{provider}_user_{user_info.id}"
        
        # Ensure username is unique
        base_username = username
        counter = 1
        while db.query(models.User).filter(models.User.username == username).first():
            username = f"{base_username}_{counter}"
            counter += 1
        
        new_user = models.User(
            email=user_info.email or f"{username}@{provider}.oauth",
            username=username,
            hashed_password=None,  # OAuth user, no password
            is_active=True,
            is_verified=user_info.verified_email,
            role="user",
            oauth_provider=provider,
            oauth_id=user_info.id,
            avatar_url=user_info.avatar_url,
            provider_data=token_data
        )
        
        db.add(new_user)
        db.flush()  # Get user ID
        
        # Create OAuth account
        oauth_account = models.OAuthAccount(
            user_id=new_user.id,
            provider=provider,
            provider_user_id=user_info.id,
            email=user_info.email,
            username=user_info.username,
            avatar_url=user_info.avatar_url,
            access_token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            provider_data=token_data
        )
        
        db.add(oauth_account)
        db.commit()
        
        return new_user
    
    def generate_link_token(self, user_id: int, provider: str) -> str:
        """Generate a temporary token for account linking."""
        data = {
            "user_id": user_id,
            "provider": provider,
            "action": "link"
        }
        return self.link_token_serializer.dumps(data)
    
    def verify_link_token(self, token: str) -> Dict:
        """Verify account linking token."""
        try:
            return self.link_token_serializer.loads(token, max_age=300)  # 5 minutes
        except BadSignature:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired link token"
            )

# Global OAuth service instance
oauth_service = OAuthService()