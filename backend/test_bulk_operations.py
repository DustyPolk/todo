"""
Tests for bulk operations and task management functionality.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from database import Base, get_db
from models import User, Task
from auth import create_access_token
from bulk_operations import bulk_service, BulkOperationType, OperationStatus

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_bulk.db"
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
    
    user = User(
        email="bulktest@example.com",
        username="bulktester",
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
            title="Task 1",
            description="First task",
            priority="high",
            completed=False,
            user_id=test_user.id
        ),
        Task(
            title="Task 2", 
            description="Second task",
            priority="medium",
            completed=False,
            user_id=test_user.id
        ),
        Task(
            title="Task 3",
            description="Third task",
            priority="low",
            completed=True,
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

class TestBulkCreate:
    """Test bulk task creation."""
    
    def test_bulk_create_tasks(self, client, auth_headers, test_user, setup_database):
        """Test creating multiple tasks in bulk."""
        tasks_data = [
            {
                "title": "Bulk Task 1",
                "description": "First bulk task",
                "priority": "high"
            },
            {
                "title": "Bulk Task 2",
                "description": "Second bulk task",
                "priority": "medium"
            },
            {
                "title": "Bulk Task 3",
                "description": "Third bulk task",
                "priority": "low"
            }
        ]
        
        response = client.post(
            "/api/bulk/create",
            json={"tasks": tasks_data},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "operation_id" in data
        assert data["status"] in ["completed", "running"]
        assert len(data["created_tasks"]) == 3
        assert data["total_items"] == 3
    
    def test_bulk_create_validation(self, client, auth_headers, setup_database):
        """Test bulk create validation."""
        # Empty tasks list
        response = client.post(
            "/api/bulk/create",
            json={"tasks": []},
            headers=auth_headers
        )
        assert response.status_code == 422
        
        # Task without title
        response = client.post(
            "/api/bulk/create", 
            json={"tasks": [{"description": "No title"}]},
            headers=auth_headers
        )
        assert response.status_code == 422

class TestBulkUpdate:
    """Test bulk task updates."""
    
    def test_bulk_update_tasks(self, client, auth_headers, sample_tasks, setup_database):
        """Test updating multiple tasks in bulk."""
        task_ids = [task.id for task in sample_tasks]
        update_data = {
            "priority": "high",
            "completed": True
        }
        
        response = client.put(
            "/api/bulk/update",
            json={
                "task_ids": task_ids,
                "update_data": update_data
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "operation_id" in data
        assert data["status"] in ["completed", "running"]
        assert data["total_items"] == len(task_ids)
    
    def test_bulk_status_change(self, client, auth_headers, sample_tasks, setup_database):
        """Test bulk status change."""
        task_ids = [task.id for task in sample_tasks[:2]]  # First 2 tasks
        
        response = client.put(
            "/api/bulk/status",
            json={
                "task_ids": task_ids,
                "completed": True
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "operation_id" in data
        assert "completed" in data["message"]
    
    def test_bulk_priority_change(self, client, auth_headers, sample_tasks, setup_database):
        """Test bulk priority change."""
        task_ids = [task.id for task in sample_tasks]
        
        response = client.put(
            "/api/bulk/priority",
            json={
                "task_ids": task_ids,
                "priority": "high"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "operation_id" in data
        assert "high priority" in data["message"]

class TestBulkDelete:
    """Test bulk task deletion."""
    
    def test_bulk_delete_tasks(self, client, auth_headers, sample_tasks, setup_database):
        """Test deleting multiple tasks in bulk."""
        task_ids = [task.id for task in sample_tasks[:2]]  # Delete first 2 tasks
        
        response = client.delete(
            "/api/bulk/delete",
            json={"task_ids": task_ids},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "operation_id" in data
        assert data["status"] in ["completed", "running"]
        assert data["total_items"] == len(task_ids)

class TestTaskReordering:
    """Test task reordering functionality."""
    
    def test_reorder_tasks(self, client, auth_headers, sample_tasks, setup_database):
        """Test reordering tasks for drag-and-drop."""
        task_positions = [
            {"id": sample_tasks[0].id, "position": 2},
            {"id": sample_tasks[1].id, "position": 1},
            {"id": sample_tasks[2].id, "position": 0}
        ]
        
        response = client.put(
            "/api/bulk/reorder",
            json={"task_positions": task_positions},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "operation_id" in data
        assert "reordered" in data["message"]

class TestBulkDuplicate:
    """Test bulk task duplication."""
    
    def test_bulk_duplicate_tasks(self, client, auth_headers, sample_tasks, setup_database):
        """Test duplicating multiple tasks."""
        task_ids = [task.id for task in sample_tasks[:2]]
        
        response = client.post(
            "/api/bulk/duplicate",
            json={
                "task_ids": task_ids,
                "suffix": " (Duplicate)"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "operation_id" in data
        assert len(data["duplicated_tasks"]) == 2
        
        # Check that duplicated tasks have the suffix
        for task in data["duplicated_tasks"]:
            assert "(Duplicate)" in task["title"]
            assert not task["completed"]  # Should reset completion status

class TestOperationStatus:
    """Test operation status tracking."""
    
    def test_get_operation_status(self, client, auth_headers, sample_tasks, setup_database):
        """Test getting operation status."""
        # First create a bulk operation
        task_ids = [task.id for task in sample_tasks]
        response = client.put(
            "/api/bulk/status",
            json={
                "task_ids": task_ids,
                "completed": True
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        operation_id = response.json()["operation_id"]
        
        # Then check its status
        response = client.get(
            f"/api/bulk/status/{operation_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["operation_id"] == operation_id
        assert "status" in data
        assert "progress_percentage" in data

class TestUndoRedo:
    """Test undo/redo functionality."""
    
    def test_undo_operation(self, client, auth_headers, sample_tasks, setup_database):
        """Test undoing a bulk operation."""
        # First create tasks to undo
        tasks_data = [
            {"title": "Undo Test 1", "priority": "high"},
            {"title": "Undo Test 2", "priority": "medium"}
        ]
        
        response = client.post(
            "/api/bulk/create",
            json={"tasks": tasks_data},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        operation_id = response.json()["operation_id"]
        
        # Then undo the operation
        response = client.post(
            "/api/bulk/undo",
            json={},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "undone successfully" in data["message"]
    
    def test_get_undo_history(self, client, auth_headers, sample_tasks, setup_database):
        """Test getting undo history."""
        response = client.get(
            "/api/bulk/undo/history",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "undo_history" in data
        assert isinstance(data["undo_history"], list)

class TestTaskTemplates:
    """Test task templates functionality."""
    
    def test_create_task_template(self, client, auth_headers, setup_database):
        """Test creating a task template."""
        template_data = {
            "name": "Project Setup",
            "description": "Standard project setup tasks",
            "category": "development",
            "tasks": [
                {"title": "Initialize repository", "priority": "high"},
                {"title": "Setup development environment", "priority": "medium"},
                {"title": "Create documentation", "priority": "low"}
            ]
        }
        
        response = client.post(
            "/api/bulk/templates",
            json=template_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "template_id" in data
        assert data["name"] == "Project Setup"
    
    def test_get_task_templates(self, client, auth_headers, setup_database):
        """Test getting task templates."""
        response = client.get(
            "/api/bulk/templates",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        assert isinstance(data["templates"], list)
    
    def test_apply_task_template(self, client, auth_headers, setup_database):
        """Test applying a task template."""
        # First create a template
        template_data = {
            "name": "Quick Template",
            "tasks": [
                {"title": "Template Task 1", "priority": "high"},
                {"title": "Template Task 2", "priority": "medium"}
            ]
        }
        
        response = client.post(
            "/api/bulk/templates",
            json=template_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        template_id = response.json()["template_id"]
        
        # Then apply it
        response = client.post(
            "/api/bulk/templates/apply",
            json={
                "template_id": template_id,
                "customizations": {"priority": "high"}
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["created_tasks"]) == 2

class TestBulkService:
    """Test bulk operations service directly."""
    
    @pytest.mark.asyncio
    async def test_create_bulk_operation(self, test_user):
        """Test creating a bulk operation tracking record."""
        operation_id = await bulk_service.create_bulk_operation(
            test_user.id,
            BulkOperationType.CREATE,
            5
        )
        
        assert operation_id is not None
        
        operation = await bulk_service.get_operation_status(operation_id)
        assert operation is not None
        assert operation.user_id == test_user.id
        assert operation.operation_type == BulkOperationType.CREATE
        assert operation.total_items == 5
        assert operation.status == OperationStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_update_operation_progress(self, test_user):
        """Test updating operation progress."""
        operation_id = await bulk_service.create_bulk_operation(
            test_user.id,
            BulkOperationType.UPDATE,
            10
        )
        
        # Update progress
        await bulk_service.update_operation_progress(operation_id, 5)
        
        operation = await bulk_service.get_operation_status(operation_id)
        assert operation.processed_items == 5
        assert operation.status == OperationStatus.RUNNING
        assert operation.progress_percentage == 50.0
        
        # Complete operation
        await bulk_service.update_operation_progress(operation_id, 10)
        
        operation = await bulk_service.get_operation_status(operation_id)
        assert operation.processed_items == 10
        assert operation.status == OperationStatus.COMPLETED
        assert operation.progress_percentage == 100.0
        assert operation.is_completed

class TestKeyboardShortcuts:
    """Test keyboard shortcuts support."""
    
    def test_get_keyboard_shortcuts(self, client, auth_headers, setup_database):
        """Test getting keyboard shortcuts information."""
        response = client.get(
            "/api/bulk/shortcuts",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "shortcuts" in data
        assert "bulk_operations" in data
        assert "Ctrl+A / Cmd+A" in data["shortcuts"]
        assert "Delete" in data["shortcuts"]

class TestValidation:
    """Test input validation for bulk operations."""
    
    def test_task_limit_validation(self, client, auth_headers, setup_database):
        """Test task limit validation."""
        # Try to create too many tasks
        large_task_list = [{"title": f"Task {i}"} for i in range(101)]
        
        response = client.post(
            "/api/bulk/create",
            json={"tasks": large_task_list},
            headers=auth_headers
        )
        
        assert response.status_code == 422
        assert "Maximum 100 tasks" in str(response.content)
    
    def test_invalid_priority_validation(self, client, auth_headers, sample_tasks, setup_database):
        """Test invalid priority validation."""
        task_ids = [task.id for task in sample_tasks]
        
        response = client.put(
            "/api/bulk/priority",
            json={
                "task_ids": task_ids,
                "priority": "invalid_priority"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422

if __name__ == "__main__":
    pytest.main([__file__])