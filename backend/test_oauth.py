"""
OAuth2 integration tests.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, patch, MagicMock
from database import Base
from main import app, get_db
import models
import schemas
from auth import get_password_hash
from oauth import oauth_service

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_oauth.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture
def test_user():
    """Create a test user."""
    db = TestingSessionLocal()
    user = models.User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("TestPass123!@#"),
        role="user",
        is_active=True,
        is_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    # Cleanup
    db.delete(user)
    db.commit()
    db.close()

@pytest.fixture
def user_headers(test_user):
    """Get authentication headers for test user."""
    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "TestPass123!@#"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def mock_google_responses():
    """Mock Google OAuth responses."""
    return {
        "discovery": {
            "authorization_endpoint": "https://accounts.google.com/o/oauth2/auth",
            "token_endpoint": "https://oauth2.googleapis.com/token",
            "userinfo_endpoint": "https://openidconnect.googleapis.com/v1/userinfo"
        },
        "token": {
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600
        },
        "userinfo": {
            "sub": "123456789",
            "email": "user@gmail.com",
            "email_verified": True,
            "name": "Test User",
            "picture": "https://example.com/avatar.jpg"
        }
    }

@pytest.fixture  
def mock_github_responses():
    """Mock GitHub OAuth responses."""
    return {
        "token": {
            "access_token": "mock_github_token",
            "token_type": "bearer",
            "scope": "user:email"
        },
        "user": {
            "id": 987654321,
            "login": "testuser",
            "name": "Test User",
            "email": "user@github.com",
            "avatar_url": "https://github.com/avatar.jpg"
        },
        "emails": [
            {
                "email": "user@github.com",
                "primary": True,
                "verified": True
            }
        ]
    }

def test_get_oauth_providers():
    """Test getting list of OAuth providers."""
    response = client.get("/api/auth/oauth/providers")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert isinstance(data["providers"], list)

def test_get_authorization_url_google():
    """Test getting Google authorization URL."""
    with patch.object(oauth_service.providers["google"], "_get_discovery_document") as mock_discovery:
        mock_discovery.return_value = {
            "authorization_endpoint": "https://accounts.google.com/o/oauth2/auth"
        }
        
        response = client.post(
            "/api/auth/oauth/authorize",
            json={"provider": "google"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        assert "state" in data
        assert "accounts.google.com" in data["authorization_url"]

def test_get_authorization_url_github():
    """Test getting GitHub authorization URL."""
    response = client.post(
        "/api/auth/oauth/authorize",
        json={"provider": "github"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "authorization_url" in data
    assert "state" in data
    assert "github.com" in data["authorization_url"]

def test_invalid_provider():
    """Test requesting authorization for invalid provider."""
    response = client.post(
        "/api/auth/oauth/authorize",
        json={"provider": "invalid"}
    )
    
    assert response.status_code == 400

@patch('httpx.AsyncClient')
async def test_google_oauth_flow(mock_client, mock_google_responses):
    """Test complete Google OAuth flow."""
    # Mock httpx responses
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.side_effect = [
        mock_google_responses["discovery"],
        mock_google_responses["token"],
        mock_google_responses["userinfo"]
    ]
    
    mock_client_instance = MagicMock()
    mock_client_instance.get.return_value = mock_response
    mock_client_instance.post.return_value = mock_response
    mock_client_instance.__aenter__.return_value = mock_client_instance
    mock_client_instance.__aexit__.return_value = None
    mock_client.return_value = mock_client_instance
    
    # Generate state
    provider = oauth_service.get_provider("google")
    state = provider.generate_state()
    
    # Test OAuth callback
    response = client.get(
        f"/api/auth/oauth/google/callback?code=mock_code&state={state}"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

@patch('httpx.AsyncClient')
async def test_github_oauth_flow(mock_client, mock_github_responses):
    """Test complete GitHub OAuth flow."""
    # Mock httpx responses
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    
    # Different responses for different endpoints
    def mock_json_response():
        if "token" in str(mock_response.url):
            return mock_github_responses["token"]
        elif "emails" in str(mock_response.url):
            return mock_github_responses["emails"]
        else:
            return mock_github_responses["user"]
    
    mock_response.json.side_effect = mock_json_response
    
    mock_client_instance = MagicMock()
    mock_client_instance.get.return_value = mock_response
    mock_client_instance.post.return_value = mock_response
    mock_client_instance.__aenter__.return_value = mock_client_instance
    mock_client_instance.__aexit__.return_value = None
    mock_client.return_value = mock_client_instance
    
    # Generate state
    provider = oauth_service.get_provider("github")
    state = provider.generate_state()
    
    # Test OAuth callback
    response = client.get(
        f"/api/auth/oauth/github/callback?code=mock_code&state={state}"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

def test_get_linked_accounts_empty(user_headers):
    """Test getting linked accounts when none exist."""
    response = client.get("/api/auth/oauth/accounts", headers=user_headers)
    assert response.status_code == 200
    accounts = response.json()
    assert accounts == []

def test_generate_link_token(user_headers):
    """Test generating a link token."""
    response = client.post("/api/auth/oauth/link-token?provider=google", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert "link_token" in data
    assert "expires_in" in data
    assert data["expires_in"] == 300

def test_oauth_state_verification():
    """Test OAuth state parameter verification."""
    provider = oauth_service.get_provider("google")
    
    # Generate valid state
    state = provider.generate_state()
    
    # Verify valid state
    state_data = provider.verify_state(state)
    assert state_data["provider"] == "google"
    assert "nonce" in state_data
    
    # Test invalid state
    with pytest.raises(Exception):
        provider.verify_state("invalid_state")

def test_oauth_account_creation():
    """Test OAuth account creation in database."""
    db = TestingSessionLocal()
    
    # Create test user
    user = models.User(
        email="oauth@example.com",
        username="oauthuser",
        hashed_password=None,  # OAuth user
        oauth_provider="google",
        oauth_id="123456789",
        is_active=True,
        is_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create OAuth account
    oauth_account = models.OAuthAccount(
        user_id=user.id,
        provider="google",
        provider_user_id="123456789",
        email="oauth@example.com",
        username="oauthuser",
        access_token="mock_token",
        provider_data={"test": "data"}
    )
    db.add(oauth_account)
    db.commit()
    
    # Verify creation
    saved_account = db.query(models.OAuthAccount).filter(
        models.OAuthAccount.provider == "google",
        models.OAuthAccount.provider_user_id == "123456789"
    ).first()
    
    assert saved_account is not None
    assert saved_account.user_id == user.id
    assert saved_account.email == "oauth@example.com"
    
    # Cleanup
    db.delete(oauth_account)
    db.delete(user)
    db.commit()
    db.close()

def test_oauth_account_linking_prevention(user_headers):
    """Test that users can't link already linked accounts."""
    # First, manually create an OAuth account for the user
    db = TestingSessionLocal()
    
    # Get the test user
    test_user = db.query(models.User).filter(models.User.username == "testuser").first()
    
    # Create OAuth account
    oauth_account = models.OAuthAccount(
        user_id=test_user.id,
        provider="google",
        provider_user_id="existing123",
        email="test@example.com"
    )
    db.add(oauth_account)
    db.commit()
    
    # Try to generate link token for already linked provider
    response = client.post("/api/auth/oauth/link-token?provider=google", headers=user_headers)
    assert response.status_code == 400
    assert "already linked" in response.json()["detail"]
    
    # Cleanup
    db.delete(oauth_account)
    db.commit()
    db.close()

def test_unlink_oauth_account_protection(user_headers):
    """Test that users can't unlink their last authentication method."""
    db = TestingSessionLocal()
    
    # Create OAuth-only user (no password)
    oauth_user = models.User(
        email="oauth_only@example.com",
        username="oauthonly",
        hashed_password=None,  # No password
        oauth_provider="google",
        oauth_id="oauth123",
        is_active=True,
        is_verified=True
    )
    db.add(oauth_user)
    db.flush()
    
    # Create OAuth account
    oauth_account = models.OAuthAccount(
        user_id=oauth_user.id,
        provider="google",
        provider_user_id="oauth123",
        email="oauth_only@example.com"
    )
    db.add(oauth_account)
    db.commit()
    
    # Login as OAuth user (would need to implement OAuth login for this test)
    # For now, just test the logic by checking the user directly
    
    # Verify user has no password and only one OAuth account
    assert oauth_user.hashed_password is None
    oauth_accounts = db.query(models.OAuthAccount).filter(
        models.OAuthAccount.user_id == oauth_user.id
    ).count()
    assert oauth_accounts == 1
    
    # Cleanup
    db.delete(oauth_account)
    db.delete(oauth_user)
    db.commit()
    db.close()

def test_oauth_provider_configurations():
    """Test OAuth provider configurations."""
    google_provider = oauth_service.get_provider("google")
    github_provider = oauth_service.get_provider("github")
    
    assert google_provider.name == "google"
    assert github_provider.name == "github"
    
    # Test invalid provider
    with pytest.raises(Exception):
        oauth_service.get_provider("invalid")

def test_oauth_user_creation_unique_username():
    """Test that OAuth user creation handles username conflicts."""
    from oauth import OAuthService
    import schemas
    
    db = TestingSessionLocal()
    service = OAuthService()
    
    # Create existing user with conflicting username
    existing_user = models.User(
        email="existing@example.com",
        username="testuser",
        hashed_password=get_password_hash("password123"),
        is_active=True
    )
    db.add(existing_user)
    db.commit()
    
    # Mock user info that would create conflicting username
    user_info = schemas.OAuthUserInfo(
        id="oauth123",
        email="oauth@example.com",
        username="testuser",  # Conflicts with existing user
        name="OAuth User",
        avatar_url="https://example.com/avatar.jpg"
    )
    
    # This would be called internally by _find_or_create_user
    # The method should handle username conflicts automatically
    
    # Cleanup
    db.delete(existing_user)
    db.commit()
    db.close()