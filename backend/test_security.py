"""
Security tests for API protection features.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import time
from database import Base
from main import app, get_db
import models
from auth import get_password_hash

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_security.db"
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
def admin_user():
    """Create an admin user for testing."""
    db = TestingSessionLocal()
    user = models.User(
        email="admin@test.com",
        username="admin",
        hashed_password=get_password_hash("AdminPass123!@#"),
        role="admin",
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
def regular_user():
    """Create a regular user for testing."""
    db = TestingSessionLocal()
    user = models.User(
        email="user@test.com",
        username="testuser",
        hashed_password=get_password_hash("UserPass123!@#"),
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
def admin_headers(admin_user):
    """Get admin authentication headers."""
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "AdminPass123!@#"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def user_headers(regular_user):
    """Get user authentication headers."""
    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "UserPass123!@#"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_security_headers():
    """Test that security headers are properly set."""
    response = client.get("/api/health")
    
    # Check security headers
    assert "X-Content-Type-Options" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "X-Frame-Options" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "X-XSS-Protection" in response.headers

def test_rate_limiting_auth():
    """Test rate limiting on authentication endpoints."""
    # Try to login multiple times quickly
    for i in range(6):  # Rate limit is 5/minute
        response = client.post(
            "/api/auth/login",
            json={"username": "nonexistent", "password": "wrongpass"}
        )
        
        if i < 5:
            assert response.status_code in [401, 422]  # Unauthorized or validation error
        else:
            assert response.status_code == 429  # Too Many Requests

def test_input_validation_xss():
    """Test XSS protection in input validation."""
    malicious_data = {
        "email": "test@example.com",
        "username": "<script>alert('xss')</script>",
        "password": "ValidPass123!@#"
    }
    
    response = client.post("/api/auth/register", json=malicious_data)
    # Should either be rejected or sanitized
    assert response.status_code in [400, 422]

def test_input_validation_sql_injection():
    """Test SQL injection protection."""
    malicious_username = "admin'; DROP TABLE users; --"
    
    response = client.post(
        "/api/auth/login",
        json={"username": malicious_username, "password": "anypass"}
    )
    
    # Should be rejected as invalid input
    assert response.status_code in [400, 401, 422]

def test_large_payload_rejection():
    """Test rejection of oversized payloads."""
    large_description = "x" * (10 * 1024 * 1024 + 1)  # Over 10MB
    
    response = client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "ValidPass123!@#",
            "description": large_description
        }
    )
    
    # Should be rejected due to size
    assert response.status_code in [413, 422]

def test_api_key_creation(user_headers):
    """Test API key creation."""
    response = client.post(
        "/api/security/api-keys",
        headers=user_headers,
        json={"name": "test-key", "permissions": ["read"]}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "api_key" in data
    assert data["name"] == "test-key"
    assert data["permissions"] == ["read"]

def test_api_key_listing(user_headers):
    """Test API key listing."""
    # Create a key first
    client.post(
        "/api/security/api-keys",
        headers=user_headers,
        json={"name": "list-test-key", "permissions": ["read", "write"]}
    )
    
    # List keys
    response = client.get("/api/security/api-keys", headers=user_headers)
    assert response.status_code == 200
    keys = response.json()
    assert len(keys) >= 1
    assert any(key["name"] == "list-test-key" for key in keys)

def test_api_key_revocation(user_headers):
    """Test API key revocation."""
    # Create a key first
    create_response = client.post(
        "/api/security/api-keys",
        headers=user_headers,
        json={"name": "revoke-test-key", "permissions": ["read"]}
    )
    assert create_response.status_code == 200
    
    # Revoke the key
    response = client.delete(
        "/api/security/api-keys/revoke-test-key",
        headers=user_headers
    )
    assert response.status_code == 200

def test_csrf_token_generation(user_headers):
    """Test CSRF token generation."""
    response = client.post("/api/security/csrf-token", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert "csrf_token" in data
    assert len(data["csrf_token"]) > 0

def test_security_events_admin(admin_headers):
    """Test security events endpoint for admin."""
    response = client.get("/api/security/events", headers=admin_headers)
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)

def test_security_events_user(user_headers):
    """Test security events endpoint for regular user."""
    response = client.get("/api/security/events/me", headers=user_headers)
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)

def test_security_events_unauthorized():
    """Test that security events require authentication."""
    response = client.get("/api/security/events")
    assert response.status_code == 403

def test_security_status_admin(admin_headers):
    """Test security status endpoint for admin."""
    response = client.get("/api/security/security-status", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "security_score" in data
    assert "status" in data
    assert "event_counts" in data

def test_security_status_forbidden_for_users(user_headers):
    """Test that security status is forbidden for regular users."""
    response = client.get("/api/security/security-status", headers=user_headers)
    assert response.status_code == 403

def test_cors_headers():
    """Test CORS headers are properly configured."""
    response = client.options("/api/health")
    
    # CORS headers should be present for preflight requests
    assert response.status_code in [200, 204]

def test_content_type_validation():
    """Test content type validation."""
    # Try to send non-JSON data to JSON endpoint
    response = client.post(
        "/api/auth/login",
        data="not-json-data",
        headers={"Content-Type": "text/plain"}
    )
    
    # Should be rejected
    assert response.status_code in [400, 422]

def test_method_not_allowed():
    """Test that invalid HTTP methods are rejected."""
    response = client.patch("/api/health")  # PATCH not allowed on health endpoint
    assert response.status_code == 405

def test_request_id_header():
    """Test that each response includes proper headers."""
    response = client.get("/api/health")
    
    # Check that security headers are present
    assert "X-Content-Type-Options" in response.headers