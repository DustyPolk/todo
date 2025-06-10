"""
Tests for search and filtering functionality.
"""
import pytest
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from database import Base, get_db
from models import User, Task
from auth import create_access_token
from search import search_service, SearchFilters, SortField, SortOrder

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_search.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module")
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def test_user():
    db = TestingSessionLocal()
    
    # Create test user
    user = User(
        email="testuser@example.com",
        username="testuser",
        hashed_password="hashed_password",
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
    token = create_access_token(data={"sub": test_user.email})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def sample_tasks(test_user):
    db = TestingSessionLocal()
    
    tasks = [
        Task(
            title="Learn Python",
            description="Study Python programming fundamentals",
            priority="high",
            completed=False,
            user_id=test_user.id,
            due_date=datetime.now() + timedelta(days=7)
        ),
        Task(
            title="Build API",
            description="Create REST API with FastAPI",
            priority="medium",
            completed=False,
            user_id=test_user.id,
            due_date=datetime.now() + timedelta(days=14)
        ),
        Task(
            title="Write tests",
            description="Add unit tests for the API endpoints",
            priority="low",
            completed=True,
            user_id=test_user.id,
            due_date=datetime.now() - timedelta(days=1)
        ),
        Task(
            title="Deploy application",
            description="Deploy to production server",
            priority="high",
            completed=False,
            user_id=test_user.id,
            due_date=datetime.now() + timedelta(days=21)
        ),
        Task(
            title="Database optimization",
            description="Optimize database queries and indexes",
            priority="medium",
            completed=False,
            user_id=test_user.id
        )
    ]
    
    for task in tasks:
        db.add(task)
    db.commit()
    
    for task in tasks:
        db.refresh(task)
    
    yield tasks
    
    # Cleanup
    for task in tasks:
        db.delete(task)
    db.commit()
    db.close()

class TestSearch:
    """Test search functionality."""
    
    def test_basic_text_search(self, client, auth_headers, sample_tasks, setup_database):
        """Test basic text search in titles and descriptions."""
        response = client.get(
            "/api/search/tasks?query=Python",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any("Python" in task["title"] or "Python" in (task["description"] or "") 
                  for task in data["tasks"])
    
    def test_search_multiple_keywords(self, client, auth_headers, sample_tasks, setup_database):
        """Test search with multiple keywords."""
        response = client.get(
            "/api/search/tasks?query=API FastAPI",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
    
    def test_priority_filter(self, client, auth_headers, sample_tasks, setup_database):
        """Test filtering by priority."""
        response = client.get(
            "/api/search/tasks?priority=high",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert all(task["priority"] == "high" for task in data["tasks"])
    
    def test_completion_filter(self, client, auth_headers, sample_tasks, setup_database):
        """Test filtering by completion status."""
        response = client.get(
            "/api/search/tasks?completed=true",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert all(task["completed"] for task in data["tasks"])
    
    def test_date_range_filter(self, client, auth_headers, sample_tasks, setup_database):
        """Test filtering by date range."""
        today = date.today()
        future_date = today + timedelta(days=30)
        
        response = client.get(
            f"/api/search/tasks?due_date_from={today}&due_date_to={future_date}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 0
    
    def test_sorting(self, client, auth_headers, sample_tasks, setup_database):
        """Test sorting by different fields."""
        # Sort by title ascending
        response = client.get(
            "/api/search/tasks?sort_by=title&sort_order=asc",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        titles = [task["title"] for task in data["tasks"]]
        assert titles == sorted(titles)
        
        # Sort by priority descending
        response = client.get(
            "/api/search/tasks?sort_by=priority&sort_order=desc",
            headers=auth_headers
        )
        assert response.status_code == 200
    
    def test_pagination(self, client, auth_headers, sample_tasks, setup_database):
        """Test pagination."""
        response = client.get(
            "/api/search/tasks?page=1&size=2",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["size"] <= 2
        assert data["page"] == 1
        assert "has_next" in data
        assert "has_prev" in data
    
    def test_combined_filters(self, client, auth_headers, sample_tasks, setup_database):
        """Test combining multiple filters."""
        response = client.get(
            "/api/search/tasks?query=API&priority=medium&completed=false",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for task in data["tasks"]:
            assert task["priority"] == "medium"
            assert not task["completed"]

class TestSearchPost:
    """Test POST search endpoint."""
    
    def test_post_search(self, client, auth_headers, sample_tasks, setup_database):
        """Test POST search with complex query."""
        search_data = {
            "query": "Python",
            "priority": "high",
            "completed": False,
            "sort_by": "title",
            "sort_order": "asc",
            "page": 1,
            "size": 10
        }
        
        response = client.post(
            "/api/search/tasks",
            json=search_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "total" in data

class TestSuggestions:
    """Test autocomplete suggestions."""
    
    def test_get_suggestions(self, client, auth_headers, sample_tasks, setup_database):
        """Test getting search suggestions."""
        response = client.get(
            "/api/search/suggestions?q=Py",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert "query" in data
        assert data["query"] == "Py"
    
    def test_suggestions_min_length(self, client, auth_headers, setup_database):
        """Test suggestions minimum query length."""
        response = client.get(
            "/api/search/suggestions?q=P",
            headers=auth_headers
        )
        assert response.status_code == 422  # Validation error

class TestFilterStats:
    """Test filter statistics."""
    
    def test_get_filter_stats(self, client, auth_headers, sample_tasks, setup_database):
        """Test getting filter statistics."""
        response = client.get(
            "/api/search/filters/stats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "priorities" in data
        assert "completion" in data
        assert "date_ranges" in data
        assert "total_tasks" in data

class TestSearchService:
    """Test search service directly."""
    
    def test_search_filters(self, test_user, sample_tasks, setup_database):
        """Test search service with various filters."""
        db = TestingSessionLocal()
        
        # Test basic search
        filters = SearchFilters(query="Python")
        result = pytest.run(search_service.search_tasks(db, filters, test_user))
        assert result.total >= 0
        
        # Test priority filter
        filters = SearchFilters(priority="high")
        result = pytest.run(search_service.search_tasks(db, filters, test_user))
        assert result.total >= 0
        
        db.close()
    
    def test_parse_search_query(self):
        """Test search query parsing."""
        pattern, keywords = search_service._parse_search_query('Python "REST API" framework')
        assert "Python" in keywords
        assert "REST API" in keywords
        assert "framework" in keywords
    
    def test_cache_key_generation(self, test_user):
        """Test cache key generation."""
        filters = SearchFilters(query="test", priority="high")
        cache_key = search_service._generate_cache_key(filters, test_user)
        assert f"user_{test_user.id}" in cache_key
        assert "priority_high" in cache_key

class TestAdvancedFeatures:
    """Test advanced search features."""
    
    def test_searchable_fields(self, client, auth_headers, setup_database):
        """Test getting searchable fields metadata."""
        response = client.get(
            "/api/search/advanced/fields",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "fields" in data
        assert "operators" in data
        assert "title" in data["fields"]
        assert "description" in data["fields"]
    
    def test_export_search_results(self, client, auth_headers, sample_tasks, setup_database):
        """Test exporting search results."""
        response = client.get(
            "/api/search/export?format=json",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "format" in data
        assert "data" in data
        assert data["format"] == "json"
    
    def test_clear_search_cache(self, client, auth_headers, setup_database):
        """Test clearing search cache."""
        response = client.delete(
            "/api/search/cache",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

if __name__ == "__main__":
    pytest.main([__file__])