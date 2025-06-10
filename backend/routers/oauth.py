"""
OAuth2 authentication endpoints for Google and GitHub integration.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from auth import get_current_user, get_db
from oauth import oauth_service
from security import rate_limit_auth, rate_limit_api, security_logger

router = APIRouter(prefix="/api/auth/oauth", tags=["oauth"])

@router.get("/providers")
@rate_limit_api()
def get_oauth_providers(request: Request):
    """Get list of available OAuth providers."""
    providers = []
    
    # Check if providers are configured
    from config import GOOGLE_CLIENT_ID, GITHUB_CLIENT_ID
    
    if GOOGLE_CLIENT_ID:
        providers.append({
            "name": "google",
            "display_name": "Google",
            "icon": "google",
            "configured": True
        })
    
    if GITHUB_CLIENT_ID:
        providers.append({
            "name": "github", 
            "display_name": "GitHub",
            "icon": "github",
            "configured": True
        })
    
    return {"providers": providers}

@router.post("/authorize", response_model=schemas.OAuthAuthorizationResponse)
@rate_limit_auth()
async def get_authorization_url(
    request: Request,
    auth_request: schemas.OAuthAuthorizationRequest
):
    """Get OAuth authorization URL for a provider."""
    try:
        auth_response = await oauth_service.get_authorization_url(auth_request.provider)
        
        # Log OAuth initiation
        security_logger.log_event(
            "oauth_authorization_initiated",
            ip_address=request.client.host,
            details={"provider": auth_request.provider}
        )
        
        return auth_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get authorization URL: {str(e)}"
        )

@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    state: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle OAuth callback from provider."""
    try:
        # Handle the OAuth callback
        token_response = await oauth_service.handle_callback(provider, code, state, db)
        
        # In a real application, you might want to redirect to frontend with token
        # For now, return the token directly
        return {
            "message": "OAuth authentication successful",
            "access_token": token_response.access_token,
            "refresh_token": token_response.refresh_token,
            "token_type": token_response.token_type
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        security_logger.log_event(
            "oauth_callback_error",
            ip_address=request.client.host,
            details={"provider": provider, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth callback failed: {str(e)}"
        )

@router.post("/{provider}/link")
@rate_limit_api()
async def link_oauth_account(
    provider: str,
    link_request: schemas.AccountLinkRequest,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Link an OAuth account to existing user."""
    try:
        # Verify link token
        token_data = oauth_service.verify_link_token(link_request.link_token)
        
        if token_data["user_id"] != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Link token not valid for current user"
            )
        
        if token_data["provider"] != provider:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider mismatch"
            )
        
        # Check if account is already linked
        existing_link = db.query(models.OAuthAccount).filter(
            models.OAuthAccount.user_id == current_user.id,
            models.OAuthAccount.provider == provider
        ).first()
        
        if existing_link:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Account already linked to {provider}"
            )
        
        # Generate authorization URL for linking
        auth_response = await oauth_service.get_authorization_url(provider)
        
        # Log account linking initiation
        security_logger.log_event(
            "oauth_account_linking_initiated",
            user_id=current_user.id,
            ip_address=request.client.host,
            details={"provider": provider}
        )
        
        return auth_response
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account linking failed: {str(e)}"
        )

@router.get("/accounts")
@rate_limit_api()
def get_linked_accounts(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[schemas.OAuthAccount]:
    """Get user's linked OAuth accounts."""
    oauth_accounts = db.query(models.OAuthAccount).filter(
        models.OAuthAccount.user_id == current_user.id
    ).all()
    
    return [
        schemas.OAuthAccount(
            provider=account.provider,
            provider_user_id=account.provider_user_id,
            email=account.email,
            username=account.username,
            avatar_url=account.avatar_url,
            created_at=account.created_at,
            updated_at=account.updated_at
        )
        for account in oauth_accounts
    ]

@router.delete("/accounts/{provider}")
@rate_limit_api()
def unlink_oauth_account(
    provider: str,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unlink an OAuth account from user."""
    # Find the OAuth account
    oauth_account = db.query(models.OAuthAccount).filter(
        models.OAuthAccount.user_id == current_user.id,
        models.OAuthAccount.provider == provider
    ).first()
    
    if not oauth_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {provider} account linked"
        )
    
    # Check if user has password or other OAuth accounts (prevent account lockout)
    if not current_user.hashed_password:
        other_accounts = db.query(models.OAuthAccount).filter(
            models.OAuthAccount.user_id == current_user.id,
            models.OAuthAccount.provider != provider
        ).count()
        
        if other_accounts == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot unlink last authentication method. Set a password first."
            )
    
    # Remove the OAuth account
    db.delete(oauth_account)
    db.commit()
    
    # Log account unlinking
    security_logger.log_event(
        "oauth_account_unlinked",
        user_id=current_user.id,
        ip_address=request.client.host,
        details={"provider": provider}
    )
    
    return {"message": f"{provider.title()} account unlinked successfully"}

@router.post("/link-token")
@rate_limit_api()
def generate_link_token(
    provider: str,
    request: Request,
    current_user: models.User = Depends(get_current_user)
):
    """Generate a temporary token for account linking."""
    # Check if account is already linked
    from auth import get_db
    db = next(get_db())
    
    existing_link = db.query(models.OAuthAccount).filter(
        models.OAuthAccount.user_id == current_user.id,
        models.OAuthAccount.provider == provider
    ).first()
    
    if existing_link:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account already linked to {provider}"
        )
    
    # Generate link token
    link_token = oauth_service.generate_link_token(current_user.id, provider)
    
    return {"link_token": link_token, "expires_in": 300}  # 5 minutes

@router.get("/user-info/{provider}")
@rate_limit_api()
async def get_oauth_user_info(
    provider: str,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user info from OAuth provider (if account is linked)."""
    # Find linked OAuth account
    oauth_account = db.query(models.OAuthAccount).filter(
        models.OAuthAccount.user_id == current_user.id,
        models.OAuthAccount.provider == provider
    ).first()
    
    if not oauth_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {provider} account linked"
        )
    
    if not oauth_account.access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid access token available"
        )
    
    try:
        # Get fresh user info from provider
        oauth_provider = oauth_service.get_provider(provider)
        user_info = await oauth_provider.get_user_info(oauth_account.access_token)
        
        return {
            "provider": provider,
            "user_info": user_info.dict(),
            "linked_at": oauth_account.created_at,
            "last_updated": oauth_account.updated_at
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get user info from {provider}: {str(e)}"
        )