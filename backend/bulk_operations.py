"""
Bulk Operations and Task Management Service

Provides efficient bulk operations for tasks including:
- Bulk creation, update, and deletion
- Batch status changes
- Task reordering and drag-and-drop
- Undo/redo functionality
- Task templates
- Progress tracking for long operations
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
from enum import Enum
from dataclasses import dataclass, asdict
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, not_, func
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel

from models import Task, User
from cache import cache_service
from search import search_service


class BulkOperationType(str, Enum):
    """Types of bulk operations."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    STATUS_CHANGE = "status_change"
    PRIORITY_CHANGE = "priority_change"
    REORDER = "reorder"
    DUPLICATE = "duplicate"
    ARCHIVE = "archive"


class OperationStatus(str, Enum):
    """Status of bulk operations."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BulkOperation:
    """Bulk operation metadata."""
    id: str
    user_id: int
    operation_type: BulkOperationType
    status: OperationStatus
    total_items: int
    processed_items: int = 0
    failed_items: int = 0
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    undo_data: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_items == 0:
            return 100.0
        return (self.processed_items / self.total_items) * 100.0
    
    @property
    def is_completed(self) -> bool:
        """Check if operation is completed."""
        return self.status in [OperationStatus.COMPLETED, OperationStatus.FAILED, OperationStatus.CANCELLED]


class TaskTemplate(BaseModel):
    """Task template for common workflows."""
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    tasks: List[Dict[str, Any]]
    category: Optional[str] = None
    is_public: bool = False
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None


class BulkOperationService:
    """Service for bulk operations and task management."""
    
    def __init__(self):
        self._active_operations: Dict[str, BulkOperation] = {}
        self._undo_stack: Dict[int, List[BulkOperation]] = {}  # user_id -> operations
        self._max_undo_operations = 10
    
    async def create_bulk_operation(
        self,
        user_id: int,
        operation_type: BulkOperationType,
        total_items: int
    ) -> str:
        """Create a new bulk operation tracking record."""
        operation_id = str(uuid4())
        operation = BulkOperation(
            id=operation_id,
            user_id=user_id,
            operation_type=operation_type,
            status=OperationStatus.PENDING,
            total_items=total_items
        )
        
        self._active_operations[operation_id] = operation
        
        # Cache operation for status tracking
        await cache_service.set(
            f"bulk_op_{operation_id}",
            asdict(operation),
            ttl=3600,  # 1 hour
            prefix="bulk:"
        )
        
        return operation_id
    
    async def update_operation_progress(
        self,
        operation_id: str,
        processed: int,
        failed: int = 0,
        error_message: Optional[str] = None
    ):
        """Update operation progress."""
        if operation_id not in self._active_operations:
            return
        
        operation = self._active_operations[operation_id]
        operation.processed_items = processed
        operation.failed_items = failed
        
        if error_message:
            operation.error_message = error_message
            operation.status = OperationStatus.FAILED
            operation.completed_at = datetime.utcnow()
        elif processed >= operation.total_items:
            operation.status = OperationStatus.COMPLETED
            operation.completed_at = datetime.utcnow()
        elif operation.status == OperationStatus.PENDING:
            operation.status = OperationStatus.RUNNING
            operation.started_at = datetime.utcnow()
        
        # Update cache
        await cache_service.set(
            f"bulk_op_{operation_id}",
            asdict(operation),
            ttl=3600,
            prefix="bulk:"
        )
    
    async def get_operation_status(self, operation_id: str) -> Optional[BulkOperation]:
        """Get operation status."""
        # Try memory first
        if operation_id in self._active_operations:
            return self._active_operations[operation_id]
        
        # Try cache
        cached_data = await cache_service.get(f"bulk_op_{operation_id}", "bulk:")
        if cached_data:
            return BulkOperation(**cached_data)
        
        return None
    
    async def bulk_create_tasks(
        self,
        db: Session,
        user: User,
        tasks_data: List[Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Create multiple tasks in bulk."""
        operation_id = await self.create_bulk_operation(
            user.id,
            BulkOperationType.CREATE,
            len(tasks_data)
        )
        
        created_tasks = []
        failed_items = 0
        
        try:
            for i, task_data in enumerate(tasks_data):
                try:
                    # Add user_id to task data
                    task_data["user_id"] = user.id
                    
                    # Create task
                    db_task = Task(**task_data)
                    db.add(db_task)
                    db.flush()  # Get ID without committing
                    
                    created_tasks.append({
                        "id": db_task.id,
                        "title": db_task.title,
                        "description": db_task.description,
                        "completed": db_task.completed,
                        "priority": db_task.priority,
                        "due_date": db_task.due_date.isoformat() if db_task.due_date else None,
                        "user_id": db_task.user_id,
                        "created_at": db_task.created_at.isoformat(),
                        "updated_at": db_task.updated_at.isoformat()
                    })
                    
                    await self.update_operation_progress(operation_id, i + 1, failed_items)
                    
                except Exception as e:
                    failed_items += 1
                    await self.update_operation_progress(
                        operation_id, i + 1, failed_items, str(e)
                    )
            
            # Commit all changes
            db.commit()
            
            # Invalidate cache
            await search_service.invalidate_search_cache(user.id)
            await cache_service.invalidate_user_cache(user.id)
            
            # Store undo data
            operation = await self.get_operation_status(operation_id)
            if operation:
                operation.undo_data = {
                    "operation": "delete",
                    "task_ids": [task["id"] for task in created_tasks]
                }
                await self._add_to_undo_stack(user.id, operation)
            
            return operation_id, created_tasks
            
        except Exception as e:
            db.rollback()
            await self.update_operation_progress(
                operation_id, 0, len(tasks_data), str(e)
            )
            raise
    
    async def bulk_update_tasks(
        self,
        db: Session,
        user: User,
        task_ids: List[int],
        update_data: Dict[str, Any]
    ) -> str:
        """Update multiple tasks in bulk."""
        operation_id = await self.create_bulk_operation(
            user.id,
            BulkOperationType.UPDATE,
            len(task_ids)
        )
        
        try:
            # Get existing tasks for undo data
            original_tasks = []
            query = db.query(Task).filter(Task.id.in_(task_ids))
            if user.role != "admin":
                query = query.filter(Task.user_id == user.id)
            
            tasks = query.all()
            
            for task in tasks:
                original_tasks.append({
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "completed": task.completed,
                    "priority": task.priority,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "updated_at": task.updated_at.isoformat()
                })
            
            # Update tasks
            processed = 0
            for task in tasks:
                for key, value in update_data.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                
                processed += 1
                await self.update_operation_progress(operation_id, processed)
            
            db.commit()
            
            # Invalidate cache
            await search_service.invalidate_search_cache(user.id)
            await cache_service.invalidate_user_cache(user.id)
            
            # Store undo data
            operation = await self.get_operation_status(operation_id)
            if operation:
                operation.undo_data = {
                    "operation": "update",
                    "tasks": original_tasks
                }
                await self._add_to_undo_stack(user.id, operation)
            
            return operation_id
            
        except Exception as e:
            db.rollback()
            await self.update_operation_progress(
                operation_id, 0, len(task_ids), str(e)
            )
            raise
    
    async def bulk_delete_tasks(
        self,
        db: Session,
        user: User,
        task_ids: List[int]
    ) -> str:
        """Delete multiple tasks in bulk."""
        operation_id = await self.create_bulk_operation(
            user.id,
            BulkOperationType.DELETE,
            len(task_ids)
        )
        
        try:
            # Get tasks for undo data
            query = db.query(Task).filter(Task.id.in_(task_ids))
            if user.role != "admin":
                query = query.filter(Task.user_id == user.id)
            
            tasks = query.all()
            deleted_tasks = []
            
            for task in tasks:
                deleted_tasks.append({
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "completed": task.completed,
                    "priority": task.priority,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "user_id": task.user_id,
                    "created_at": task.created_at.isoformat(),
                    "updated_at": task.updated_at.isoformat()
                })
                
                db.delete(task)
                await self.update_operation_progress(operation_id, len(deleted_tasks))
            
            db.commit()
            
            # Invalidate cache
            await search_service.invalidate_search_cache(user.id)
            await cache_service.invalidate_user_cache(user.id)
            
            # Store undo data
            operation = await self.get_operation_status(operation_id)
            if operation:
                operation.undo_data = {
                    "operation": "create",
                    "tasks": deleted_tasks
                }
                await self._add_to_undo_stack(user.id, operation)
            
            return operation_id
            
        except Exception as e:
            db.rollback()
            await self.update_operation_progress(
                operation_id, 0, len(task_ids), str(e)
            )
            raise
    
    async def bulk_status_change(
        self,
        db: Session,
        user: User,
        task_ids: List[int],
        completed: bool
    ) -> str:
        """Change completion status for multiple tasks."""
        return await self.bulk_update_tasks(
            db, user, task_ids, {"completed": completed}
        )
    
    async def bulk_priority_change(
        self,
        db: Session,
        user: User,
        task_ids: List[int],
        priority: str
    ) -> str:
        """Change priority for multiple tasks."""
        return await self.bulk_update_tasks(
            db, user, task_ids, {"priority": priority}
        )
    
    async def reorder_tasks(
        self,
        db: Session,
        user: User,
        task_positions: List[Dict[str, int]]  # [{"id": task_id, "position": new_position}]
    ) -> str:
        """Reorder tasks (for drag-and-drop functionality)."""
        operation_id = await self.create_bulk_operation(
            user.id,
            BulkOperationType.REORDER,
            len(task_positions)
        )
        
        try:
            # For simplicity, we'll use updated_at to track order
            # In a real app, you might add a position/order field
            
            processed = 0
            for item in task_positions:
                task_id = item["id"]
                # Use a timestamp-based ordering system
                # Earlier positions get earlier timestamps
                order_time = datetime.utcnow() - timedelta(seconds=item["position"])
                
                task = db.query(Task).filter(Task.id == task_id).first()
                if task and (user.role == "admin" or task.user_id == user.id):
                    task.updated_at = order_time
                    processed += 1
                    await self.update_operation_progress(operation_id, processed)
            
            db.commit()
            
            # Invalidate cache
            await search_service.invalidate_search_cache(user.id)
            await cache_service.invalidate_user_cache(user.id)
            
            return operation_id
            
        except Exception as e:
            db.rollback()
            await self.update_operation_progress(
                operation_id, 0, len(task_positions), str(e)
            )
            raise
    
    async def duplicate_tasks(
        self,
        db: Session,
        user: User,
        task_ids: List[int],
        suffix: str = " (Copy)"
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Duplicate multiple tasks."""
        operation_id = await self.create_bulk_operation(
            user.id,
            BulkOperationType.DUPLICATE,
            len(task_ids)
        )
        
        duplicated_tasks = []
        
        try:
            query = db.query(Task).filter(Task.id.in_(task_ids))
            if user.role != "admin":
                query = query.filter(Task.user_id == user.id)
            
            tasks = query.all()
            processed = 0
            
            for task in tasks:
                # Create duplicate
                duplicate_data = {
                    "title": task.title + suffix,
                    "description": task.description,
                    "priority": task.priority,
                    "due_date": task.due_date,
                    "user_id": user.id,
                    "completed": False  # Reset completion status
                }
                
                db_task = Task(**duplicate_data)
                db.add(db_task)
                db.flush()
                
                duplicated_tasks.append({
                    "id": db_task.id,
                    "title": db_task.title,
                    "description": db_task.description,
                    "completed": db_task.completed,
                    "priority": db_task.priority,
                    "due_date": db_task.due_date.isoformat() if db_task.due_date else None,
                    "user_id": db_task.user_id,
                    "created_at": db_task.created_at.isoformat(),
                    "updated_at": db_task.updated_at.isoformat()
                })
                
                processed += 1
                await self.update_operation_progress(operation_id, processed)
            
            db.commit()
            
            # Invalidate cache
            await search_service.invalidate_search_cache(user.id)
            await cache_service.invalidate_user_cache(user.id)
            
            return operation_id, duplicated_tasks
            
        except Exception as e:
            db.rollback()
            await self.update_operation_progress(
                operation_id, 0, len(task_ids), str(e)
            )
            raise
    
    async def undo_operation(
        self,
        db: Session,
        user: User,
        operation_id: Optional[str] = None
    ) -> bool:
        """Undo a bulk operation."""
        user_stack = self._undo_stack.get(user.id, [])
        if not user_stack:
            return False
        
        # Get operation to undo
        if operation_id:
            operation = next((op for op in user_stack if op.id == operation_id), None)
            if not operation:
                return False
        else:
            operation = user_stack[-1]  # Most recent
        
        if not operation.undo_data:
            return False
        
        try:
            undo_data = operation.undo_data
            
            if undo_data["operation"] == "delete":
                # Undo create: delete the created tasks
                task_ids = undo_data["task_ids"]
                db.query(Task).filter(Task.id.in_(task_ids)).delete()
                
            elif undo_data["operation"] == "create":
                # Undo delete: recreate the tasks
                for task_data in undo_data["tasks"]:
                    task_data.pop("id", None)  # Remove ID for new creation
                    db_task = Task(**task_data)
                    db.add(db_task)
                
            elif undo_data["operation"] == "update":
                # Undo update: restore original values
                for task_data in undo_data["tasks"]:
                    task = db.query(Task).filter(Task.id == task_data["id"]).first()
                    if task:
                        for key, value in task_data.items():
                            if key != "id" and hasattr(task, key):
                                setattr(task, key, value)
            
            db.commit()
            
            # Remove from undo stack
            if operation in user_stack:
                user_stack.remove(operation)
            
            # Invalidate cache
            await search_service.invalidate_search_cache(user.id)
            await cache_service.invalidate_user_cache(user.id)
            
            return True
            
        except Exception as e:
            db.rollback()
            return False
    
    async def get_undo_history(self, user_id: int) -> List[Dict[str, Any]]:
        """Get undo history for a user."""
        user_stack = self._undo_stack.get(user_id, [])
        return [
            {
                "id": op.id,
                "operation_type": op.operation_type,
                "total_items": op.total_items,
                "created_at": op.created_at.isoformat() if op.created_at else None,
                "can_undo": bool(op.undo_data)
            }
            for op in reversed(user_stack)  # Most recent first
        ]
    
    async def _add_to_undo_stack(self, user_id: int, operation: BulkOperation):
        """Add operation to undo stack."""
        if user_id not in self._undo_stack:
            self._undo_stack[user_id] = []
        
        stack = self._undo_stack[user_id]
        stack.append(operation)
        
        # Limit stack size
        if len(stack) > self._max_undo_operations:
            stack.pop(0)  # Remove oldest
    
    # Task Templates
    async def create_task_template(
        self,
        user: User,
        template_data: Dict[str, Any]
    ) -> TaskTemplate:
        """Create a task template."""
        template = TaskTemplate(
            id=str(uuid4()),
            name=template_data["name"],
            description=template_data.get("description"),
            tasks=template_data["tasks"],
            category=template_data.get("category"),
            is_public=template_data.get("is_public", False),
            created_by=user.id,
            created_at=datetime.utcnow()
        )
        
        # Cache template
        await cache_service.set(
            f"template_{template.id}",
            template.dict(),
            ttl=86400,  # 24 hours
            prefix="templates:"
        )
        
        # Add to user's templates list
        user_templates = await cache_service.get(f"user_{user.id}_templates", "templates:")
        if not user_templates:
            user_templates = []
        
        user_templates.append(template.id)
        await cache_service.set(
            f"user_{user.id}_templates",
            user_templates,
            ttl=86400,
            prefix="templates:"
        )
        
        return template
    
    async def get_task_templates(
        self,
        user: User,
        category: Optional[str] = None,
        include_public: bool = True
    ) -> List[TaskTemplate]:
        """Get task templates for a user."""
        templates = []
        
        # Get user's templates
        user_templates = await cache_service.get(f"user_{user.id}_templates", "templates:")
        if user_templates:
            for template_id in user_templates:
                template_data = await cache_service.get(f"template_{template_id}", "templates:")
                if template_data:
                    template = TaskTemplate(**template_data)
                    if not category or template.category == category:
                        templates.append(template)
        
        # TODO: Get public templates (would need database storage)
        
        return templates
    
    async def apply_task_template(
        self,
        db: Session,
        user: User,
        template_id: str,
        customizations: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Apply a task template to create tasks."""
        template_data = await cache_service.get(f"template_{template_id}", "templates:")
        if not template_data:
            raise ValueError("Template not found")
        
        template = TaskTemplate(**template_data)
        tasks_data = template.tasks.copy()
        
        # Apply customizations
        if customizations:
            for task_data in tasks_data:
                task_data.update(customizations)
        
        # Create tasks from template
        return await self.bulk_create_tasks(db, user, tasks_data)


# Global bulk operations service
bulk_service = BulkOperationService()