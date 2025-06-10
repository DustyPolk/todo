import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
from main import app, get_db
import models
from auth import get_password_hash

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
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
    """Create a test user for authentication tests."""
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
def auth_headers(test_user):
    """Get authentication headers for test user."""
    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "TestPass123!@#"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_register_user():
    """Test user registration."""
    response = client.post(
        "/api/auth/register",
        json={
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "NewPass123!@#"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["username"] == "newuser"
    assert "hashed_password" not in data

def test_register_duplicate_email():
    """Test registration with duplicate email."""
    # First registration
    client.post(
        "/api/auth/register",
        json={
            "email": "duplicate@example.com",
            "username": "user1",
            "password": "Pass123!@#$"
        }
    )
    
    # Duplicate email
    response = client.post(
        "/api/auth/register",
        json={
            "email": "duplicate@example.com",
            "username": "user2",
            "password": "Pass123!@#$"
        }
    )
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]

def test_login_success(test_user):
    """Test successful login."""
    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "TestPass123!@#"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

def test_login_invalid_password(test_user):
    """Test login with invalid password."""
    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "WrongPassword123!"}
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]

def test_get_current_user(test_user, auth_headers):
    """Test getting current user info."""
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"

def test_refresh_token(test_user):
    """Test token refresh."""
    # Login first
    login_response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "TestPass123!@#"}
    )
    refresh_token = login_response.json()["refresh_token"]
    
    # Refresh token
    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

def test_logout(test_user, auth_headers):
    """Test logout functionality."""
    response = client.post("/api/auth/logout", headers=auth_headers)
    assert response.status_code == 200
    
    # Try to use the same token again
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 401

def test_password_complexity():
    """Test password complexity requirements."""
    # Too short
    response = client.post(
        "/api/auth/register",
        json={
            "email": "test1@example.com",
            "username": "test1",
            "password": "Short1!"
        }
    )
    assert response.status_code == 422
    
    # No uppercase
    response = client.post(
        "/api/auth/register",
        json={
            "email": "test2@example.com",
            "username": "test2",
            "password": "nouppercase123!"
        }
    )
    assert response.status_code == 422
    
    # No special character
    response = client.post(
        "/api/auth/register",
        json={
            "email": "test3@example.com",
            "username": "test3",
            "password": "NoSpecialChar123"
        }
    )
    assert response.status_code == 422

def test_protected_endpoints_without_auth():
    """Test accessing protected endpoints without authentication."""
    response = client.get("/api/tasks")
    assert response.status_code == 403
    
    response = client.post("/api/tasks", json={"title": "Test Task"})
    assert response.status_code == 403

def test_task_isolation(test_user, auth_headers):
    """Test that users can only see their own tasks."""
    # Create a task
    response = client.post(
        "/api/tasks",
        headers=auth_headers,
        json={"title": "User's Task", "description": "Private task"}
    )
    assert response.status_code == 200
    task_id = response.json()["id"]
    
    # Create another user
    client.post(
        "/api/auth/register",
        json={
            "email": "otheruser@example.com",
            "username": "otheruser",
            "password": "OtherPass123!@#"
        }
    )
    
    # Login as other user
    other_login = client.post(
        "/api/auth/login",
        json={"username": "otheruser", "password": "OtherPass123!@#"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
    
    # Try to access first user's task
    response = client.get(f"/api/tasks/{task_id}", headers=other_headers)
    assert response.status_code == 403
    
    # List tasks should not include other user's tasks
    response = client.get("/api/tasks", headers=other_headers)
    assert response.status_code == 200
    assert len(response.json()) == 0