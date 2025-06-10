"""
Bulk Operations API endpoints.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator

from database import SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
from auth import get_current_active_user, check_user_role
from models import User
from bulk_operations import bulk_service, BulkOperationType, TaskTemplate
from security import rate_limit_api

router = APIRouter(prefix="/api/bulk", tags=["bulk-operations"])


class BulkCreateRequest(BaseModel):
    """Bulk task creation request."""
    tasks: List[Dict[str, Any]]
    
    @validator('tasks')
    def validate_tasks(cls, v):
        if len(v) == 0:
            raise ValueError("At least one task is required")
        if len(v) > 100:
            raise ValueError("Maximum 100 tasks per bulk operation")
        
        for task in v:
            if not task.get("title"):
                raise ValueError("Each task must have a title")
        
        return v


class BulkUpdateRequest(BaseModel):
    """Bulk task update request."""
    task_ids: List[int]
    update_data: Dict[str, Any]
    
    @validator('task_ids')
    def validate_task_ids(cls, v):
        if len(v) == 0:
            raise ValueError("At least one task ID is required")
        if len(v) > 1000:
            raise ValueError("Maximum 1000 tasks per bulk operation")
        return v


class BulkDeleteRequest(BaseModel):
    """Bulk task deletion request."""
    task_ids: List[int]
    
    @validator('task_ids')
    def validate_task_ids(cls, v):
        if len(v) == 0:
            raise ValueError("At least one task ID is required")
        if len(v) > 1000:
            raise ValueError("Maximum 1000 tasks per bulk operation")
        return v


class BulkStatusChangeRequest(BaseModel):
    """Bulk status change request."""
    task_ids: List[int]
    completed: bool
    
    @validator('task_ids')
    def validate_task_ids(cls, v):
        if len(v) == 0:
            raise ValueError("At least one task ID is required")
        if len(v) > 1000:
            raise ValueError("Maximum 1000 tasks per bulk operation")
        return v


class BulkPriorityChangeRequest(BaseModel):
    """Bulk priority change request."""
    task_ids: List[int]
    priority: str
    
    @validator('task_ids')
    def validate_task_ids(cls, v):
        if len(v) == 0:
            raise ValueError("At least one task ID is required")
        if len(v) > 1000:
            raise ValueError("Maximum 1000 tasks per bulk operation")
        return v
    
    @validator('priority')
    def validate_priority(cls, v):
        if v not in ["low", "medium", "high"]:
            raise ValueError("Priority must be low, medium, or high")
        return v


class TaskReorderRequest(BaseModel):
    """Task reorder request for drag-and-drop."""
    task_positions: List[Dict[str, int]]  # [{"id": task_id, "position": new_position}]
    
    @validator('task_positions')
    def validate_positions(cls, v):
        if len(v) == 0:
            raise ValueError("At least one task position is required")
        if len(v) > 1000:
            raise ValueError("Maximum 1000 tasks per reorder operation")
        
        for item in v:
            if "id" not in item or "position" not in item:
                raise ValueError("Each item must have 'id' and 'position'")
        
        return v


class BulkDuplicateRequest(BaseModel):
    """Bulk task duplication request."""
    task_ids: List[int]
    suffix: str = " (Copy)"
    
    @validator('task_ids')
    def validate_task_ids(cls, v):
        if len(v) == 0:
            raise ValueError("At least one task ID is required")
        if len(v) > 100:
            raise ValueError("Maximum 100 tasks per duplication operation")
        return v


class TemplateCreateRequest(BaseModel):
    """Task template creation request."""
    name: str
    description: Optional[str] = None
    tasks: List[Dict[str, Any]]
    category: Optional[str] = None
    is_public: bool = False
    
    @validator('name')
    def validate_name(cls, v):
        if len(v.strip()) == 0:
            raise ValueError("Template name is required")
        if len(v) > 100:
            raise ValueError("Template name must be less than 100 characters")
        return v.strip()
    
    @validator('tasks')
    def validate_tasks(cls, v):
        if len(v) == 0:
            raise ValueError("At least one task is required")
        if len(v) > 50:
            raise ValueError("Maximum 50 tasks per template")
        return v


class TemplateApplyRequest(BaseModel):
    """Template application request."""
    template_id: str
    customizations: Optional[Dict[str, Any]] = None


class BulkOperationResponse(BaseModel):
    """Bulk operation response."""
    operation_id: str
    status: str
    message: str
    total_items: int
    processed_items: int = 0
    failed_items: int = 0
    progress_percentage: float = 0.0


class BulkCreateResponse(BulkOperationResponse):
    """Bulk create response with created tasks."""
    created_tasks: List[Dict[str, Any]] = []


class BulkDuplicateResponse(BulkOperationResponse):
    """Bulk duplicate response with duplicated tasks."""
    duplicated_tasks: List[Dict[str, Any]] = []


@router.post("/create", response_model=BulkCreateResponse)
@rate_limit_api()
async def bulk_create_tasks(
    request: Request,
    bulk_request: BulkCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create multiple tasks in bulk.
    
    Features:
    - Atomic transaction (all or nothing)
    - Progress tracking
    - Undo support
    - Cache invalidation
    """
    try:
        operation_id, created_tasks = await bulk_service.bulk_create_tasks(
            db, current_user, bulk_request.tasks
        )
        
        operation = await bulk_service.get_operation_status(operation_id)
        
        return BulkCreateResponse(
            operation_id=operation_id,
            status=operation.status,
            message=f"Successfully created {len(created_tasks)} tasks",
            total_items=operation.total_items,
            processed_items=operation.processed_items,
            failed_items=operation.failed_items,
            progress_percentage=operation.progress_percentage,
            created_tasks=created_tasks
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk create failed: {str(e)}")


@router.put("/update", response_model=BulkOperationResponse)
@rate_limit_api()
async def bulk_update_tasks(
    request: Request,
    bulk_request: BulkUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update multiple tasks in bulk.
    
    Supports updating any task field including:
    - title, description
    - priority, completed status
    - due_date
    """
    try:
        operation_id = await bulk_service.bulk_update_tasks(
            db, current_user, bulk_request.task_ids, bulk_request.update_data
        )
        
        operation = await bulk_service.get_operation_status(operation_id)
        
        return BulkOperationResponse(
            operation_id=operation_id,
            status=operation.status,
            message=f"Successfully updated {operation.processed_items} tasks",
            total_items=operation.total_items,
            processed_items=operation.processed_items,
            failed_items=operation.failed_items,
            progress_percentage=operation.progress_percentage
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk update failed: {str(e)}")


@router.delete("/delete", response_model=BulkOperationResponse)
@rate_limit_api()
async def bulk_delete_tasks(
    request: Request,
    bulk_request: BulkDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete multiple tasks in bulk.
    
    Features:
    - Atomic transaction
    - Undo support (tasks can be restored)
    - Permission checking
    """
    try:
        operation_id = await bulk_service.bulk_delete_tasks(
            db, current_user, bulk_request.task_ids
        )
        
        operation = await bulk_service.get_operation_status(operation_id)
        
        return BulkOperationResponse(
            operation_id=operation_id,
            status=operation.status,
            message=f"Successfully deleted {operation.processed_items} tasks",
            total_items=operation.total_items,
            processed_items=operation.processed_items,
            failed_items=operation.failed_items,
            progress_percentage=operation.progress_percentage
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk delete failed: {str(e)}")


@router.put("/status", response_model=BulkOperationResponse)
@rate_limit_api()
async def bulk_change_status(
    request: Request,
    bulk_request: BulkStatusChangeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Change completion status for multiple tasks.
    
    Useful for:
    - Marking multiple tasks as complete
    - Reopening completed tasks
    - Batch status management
    """
    try:
        operation_id = await bulk_service.bulk_status_change(
            db, current_user, bulk_request.task_ids, bulk_request.completed
        )
        
        operation = await bulk_service.get_operation_status(operation_id)
        status_text = "completed" if bulk_request.completed else "incomplete"
        
        return BulkOperationResponse(
            operation_id=operation_id,
            status=operation.status,
            message=f"Successfully marked {operation.processed_items} tasks as {status_text}",
            total_items=operation.total_items,
            processed_items=operation.processed_items,
            failed_items=operation.failed_items,
            progress_percentage=operation.progress_percentage
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk status change failed: {str(e)}")


@router.put("/priority", response_model=BulkOperationResponse)
@rate_limit_api()
async def bulk_change_priority(
    request: Request,
    bulk_request: BulkPriorityChangeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Change priority for multiple tasks.
    
    Useful for:
    - Escalating task priorities
    - Bulk priority management
    - Project prioritization
    """
    try:
        operation_id = await bulk_service.bulk_priority_change(
            db, current_user, bulk_request.task_ids, bulk_request.priority
        )
        
        operation = await bulk_service.get_operation_status(operation_id)
        
        return BulkOperationResponse(
            operation_id=operation_id,
            status=operation.status,
            message=f"Successfully changed {operation.processed_items} tasks to {bulk_request.priority} priority",
            total_items=operation.total_items,
            processed_items=operation.processed_items,
            failed_items=operation.failed_items,
            progress_percentage=operation.progress_percentage
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk priority change failed: {str(e)}")


@router.put("/reorder", response_model=BulkOperationResponse)
@rate_limit_api()
async def reorder_tasks(
    request: Request,
    reorder_request: TaskReorderRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Reorder tasks for drag-and-drop functionality.
    
    Features:
    - Optimistic updates support
    - Conflict resolution
    - Real-time position updates
    """
    try:
        operation_id = await bulk_service.reorder_tasks(
            db, current_user, reorder_request.task_positions
        )
        
        operation = await bulk_service.get_operation_status(operation_id)
        
        return BulkOperationResponse(
            operation_id=operation_id,
            status=operation.status,
            message=f"Successfully reordered {operation.processed_items} tasks",
            total_items=operation.total_items,
            processed_items=operation.processed_items,
            failed_items=operation.failed_items,
            progress_percentage=operation.progress_percentage
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Task reorder failed: {str(e)}")


@router.post("/duplicate", response_model=BulkDuplicateResponse)
@rate_limit_api()
async def bulk_duplicate_tasks(
    request: Request,
    bulk_request: BulkDuplicateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Duplicate multiple tasks.
    
    Features:
    - Custom suffix for duplicated tasks
    - Reset completion status
    - Preserve task relationships
    """
    try:
        operation_id, duplicated_tasks = await bulk_service.duplicate_tasks(
            db, current_user, bulk_request.task_ids, bulk_request.suffix
        )
        
        operation = await bulk_service.get_operation_status(operation_id)
        
        return BulkDuplicateResponse(
            operation_id=operation_id,
            status=operation.status,
            message=f"Successfully duplicated {len(duplicated_tasks)} tasks",
            total_items=operation.total_items,
            processed_items=operation.processed_items,
            failed_items=operation.failed_items,
            progress_percentage=operation.progress_percentage,
            duplicated_tasks=duplicated_tasks
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk duplicate failed: {str(e)}")


@router.get("/status/{operation_id}")
@rate_limit_api()
async def get_operation_status(
    request: Request,
    operation_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the status of a bulk operation.
    
    Useful for:
    - Progress tracking
    - Long-running operation monitoring
    - Error checking
    """
    operation = await bulk_service.get_operation_status(operation_id)
    
    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    if operation.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view this operation")
    
    return {
        "operation_id": operation.id,
        "operation_type": operation.operation_type,
        "status": operation.status,
        "total_items": operation.total_items,
        "processed_items": operation.processed_items,
        "failed_items": operation.failed_items,
        "progress_percentage": operation.progress_percentage,
        "created_at": operation.created_at.isoformat() if operation.created_at else None,
        "started_at": operation.started_at.isoformat() if operation.started_at else None,
        "completed_at": operation.completed_at.isoformat() if operation.completed_at else None,
        "error_message": operation.error_message,
        "is_completed": operation.is_completed
    }


@router.post("/undo")
@rate_limit_api()
async def undo_operation(
    request: Request,
    operation_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Undo a bulk operation.
    
    Features:
    - Reverse any bulk operation
    - Restore deleted tasks
    - Revert bulk changes
    """
    try:
        success = await bulk_service.undo_operation(db, current_user, operation_id)
        
        if not success:
            raise HTTPException(status_code=400, detail="Cannot undo operation")
        
        return {"message": "Operation undone successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Undo failed: {str(e)}")


@router.get("/undo/history")
@rate_limit_api()
async def get_undo_history(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get undo history for the current user.
    
    Returns list of operations that can be undone.
    """
    try:
        history = await bulk_service.get_undo_history(current_user.id)
        return {"undo_history": history}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get undo history: {str(e)}")


# Task Templates
@router.post("/templates", response_model=dict)
@rate_limit_api()
async def create_task_template(
    request: Request,
    template_request: TemplateCreateRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a task template for common workflows.
    
    Templates allow users to quickly create sets of related tasks.
    """
    try:
        template = await bulk_service.create_task_template(
            current_user, template_request.dict()
        )
        
        return {
            "template_id": template.id,
            "name": template.name,
            "message": "Template created successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template creation failed: {str(e)}")


@router.get("/templates")
@rate_limit_api()
async def get_task_templates(
    request: Request,
    category: Optional[str] = None,
    include_public: bool = True,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get task templates for the current user.
    
    Includes user's own templates and optionally public templates.
    """
    try:
        templates = await bulk_service.get_task_templates(
            current_user, category, include_public
        )
        
        return {
            "templates": [
                {
                    "id": template.id,
                    "name": template.name,
                    "description": template.description,
                    "category": template.category,
                    "task_count": len(template.tasks),
                    "is_public": template.is_public,
                    "created_at": template.created_at.isoformat() if template.created_at else None
                }
                for template in templates
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get templates: {str(e)}")


@router.post("/templates/apply", response_model=BulkCreateResponse)
@rate_limit_api()
async def apply_task_template(
    request: Request,
    template_request: TemplateApplyRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Apply a task template to create tasks.
    
    Features:
    - Template customization
    - Bulk task creation
    - Undo support
    """
    try:
        operation_id, created_tasks = await bulk_service.apply_task_template(
            db, current_user, template_request.template_id, template_request.customizations
        )
        
        operation = await bulk_service.get_operation_status(operation_id)
        
        return BulkCreateResponse(
            operation_id=operation_id,
            status=operation.status,
            message=f"Successfully created {len(created_tasks)} tasks from template",
            total_items=operation.total_items,
            processed_items=operation.processed_items,
            failed_items=operation.failed_items,
            progress_percentage=operation.progress_percentage,
            created_tasks=created_tasks
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template application failed: {str(e)}")


# Keyboard shortcuts support endpoints
@router.get("/shortcuts")
@rate_limit_api()
async def get_keyboard_shortcuts(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get available keyboard shortcuts for bulk operations.
    
    Returns mapping of keyboard shortcuts to operations.
    """
    return {
        "shortcuts": {
            "Ctrl+A / Cmd+A": "Select all tasks",
            "Delete": "Delete selected tasks",
            "Ctrl+D / Cmd+D": "Duplicate selected tasks",
            "Ctrl+Z / Cmd+Z": "Undo last operation",
            "Ctrl+Shift+Z / Cmd+Shift+Z": "Redo operation",
            "Space": "Toggle completion status",
            "1": "Set priority to high",
            "2": "Set priority to medium", 
            "3": "Set priority to low",
            "Enter": "Edit selected task",
            "Escape": "Clear selection"
        },
        "bulk_operations": {
            "select_all": "/api/search/tasks",
            "bulk_delete": "/api/bulk/delete",
            "bulk_duplicate": "/api/bulk/duplicate",
            "bulk_status": "/api/bulk/status",
            "bulk_priority": "/api/bulk/priority",
            "undo": "/api/bulk/undo"
        }
    }