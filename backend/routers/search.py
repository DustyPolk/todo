"""
Search and filtering API endpoints.
"""
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from auth import get_current_active_user
from models import User
from search import search_service, SearchFilters, SortField, SortOrder
from security import rate_limit_api

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchRequest(BaseModel):
    """Search request model."""
    query: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None
    due_date_from: Optional[date] = None
    due_date_to: Optional[date] = None
    created_from: Optional[date] = None
    created_to: Optional[date] = None
    tags: Optional[List[str]] = None
    sort_by: SortField = SortField.CREATED_AT
    sort_order: SortOrder = SortOrder.DESC
    page: int = 1
    size: int = 20


class SearchResponse(BaseModel):
    """Search response model."""
    tasks: List[dict]
    total: int
    page: int
    size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    search_time_ms: Optional[float] = None


class SuggestionResponse(BaseModel):
    """Autocomplete suggestion response."""
    suggestions: List[str]
    query: str


class FilterStatsResponse(BaseModel):
    """Filter statistics response."""
    priorities: dict
    completion: dict
    date_ranges: dict
    total_tasks: int


@router.get("/tasks", response_model=SearchResponse)
@rate_limit_api()
async def search_tasks(
    request: Request,
    query: Optional[str] = Query(None, description="Search query for titles and descriptions"),
    completed: Optional[bool] = Query(None, description="Filter by completion status"),
    priority: Optional[str] = Query(None, description="Filter by priority (comma-separated for multiple)"),
    due_date_from: Optional[date] = Query(None, description="Filter by due date from (YYYY-MM-DD)"),
    due_date_to: Optional[date] = Query(None, description="Filter by due date to (YYYY-MM-DD)"),
    created_from: Optional[date] = Query(None, description="Filter by creation date from (YYYY-MM-DD)"),
    created_to: Optional[date] = Query(None, description="Filter by creation date to (YYYY-MM-DD)"),
    sort_by: SortField = Query(SortField.CREATED_AT, description="Field to sort by"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Search and filter tasks with advanced options.
    
    Features:
    - Full-text search in titles and descriptions
    - Multiple filter options
    - Flexible sorting
    - Pagination
    - Result caching
    """
    # Convert page-based pagination to offset-based
    skip = (page - 1) * size
    
    filters = SearchFilters(
        query=query,
        completed=completed,
        priority=priority,
        due_date_from=due_date_from,
        due_date_to=due_date_to,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=size
    )
    
    try:
        result = await search_service.search_tasks(db, filters, current_user)
        return SearchResponse(**result.__dict__)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/tasks", response_model=SearchResponse)
@rate_limit_api()
async def search_tasks_post(
    request: Request,
    search_request: SearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Search tasks using POST method for complex queries.
    
    Useful for complex search requests that might exceed URL length limits.
    """
    # Convert page-based pagination to offset-based
    skip = (search_request.page - 1) * search_request.size
    
    filters = SearchFilters(
        query=search_request.query,
        completed=search_request.completed,
        priority=search_request.priority,
        due_date_from=search_request.due_date_from,
        due_date_to=search_request.due_date_to,
        created_from=search_request.created_from,
        created_to=search_request.created_to,
        tags=search_request.tags,
        sort_by=search_request.sort_by,
        sort_order=search_request.sort_order,
        skip=skip,
        limit=search_request.size
    )
    
    try:
        result = await search_service.search_tasks(db, filters, current_user)
        return SearchResponse(**result.__dict__)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/suggestions", response_model=SuggestionResponse)
@rate_limit_api()
async def get_search_suggestions(
    request: Request,
    q: str = Query(..., min_length=2, description="Search query for suggestions"),
    limit: int = Query(10, ge=1, le=20, description="Maximum number of suggestions"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get autocomplete suggestions for search queries.
    
    Returns relevant titles and keywords based on user's tasks.
    """
    try:
        suggestions = await search_service.get_search_suggestions(db, q, current_user, limit)
        return SuggestionResponse(suggestions=suggestions, query=q)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get suggestions: {str(e)}")


@router.get("/filters/stats", response_model=FilterStatsResponse)
@rate_limit_api()
async def get_filter_statistics(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get statistics for filter options.
    
    Returns counts for priorities, completion status, and date ranges
    to help build dynamic filter UI components.
    """
    try:
        stats = await search_service.get_filter_statistics(db, current_user)
        return FilterStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get filter stats: {str(e)}")


@router.delete("/cache")
@rate_limit_api()
async def clear_search_cache(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Clear search cache for the current user.
    
    Useful when user wants fresh search results or after making many changes.
    """
    try:
        await search_service.invalidate_search_cache(current_user.id)
        return {"message": "Search cache cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.get("/recent")
@rate_limit_api()
async def get_recent_searches(
    request: Request,
    limit: int = Query(10, ge=1, le=20, description="Number of recent searches"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get recent search queries for the user.
    
    Note: This would require implementing search history tracking.
    Currently returns empty list as placeholder.
    """
    # TODO: Implement search history tracking
    return {"recent_searches": [], "message": "Search history not yet implemented"}


# Advanced search endpoints
@router.get("/advanced/fields")
@rate_limit_api()
async def get_searchable_fields(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get available searchable fields and their metadata.
    
    Useful for building advanced search forms.
    """
    return {
        "fields": {
            "title": {
                "type": "text",
                "searchable": True,
                "sortable": True,
                "description": "Task title"
            },
            "description": {
                "type": "text", 
                "searchable": True,
                "sortable": False,
                "description": "Task description"
            },
            "completed": {
                "type": "boolean",
                "searchable": False,
                "sortable": True,
                "filterable": True,
                "options": [True, False]
            },
            "priority": {
                "type": "enum",
                "searchable": False,
                "sortable": True,
                "filterable": True,
                "options": ["low", "medium", "high"]
            },
            "due_date": {
                "type": "datetime",
                "searchable": False,
                "sortable": True,
                "filterable": True,
                "description": "Task due date"
            },
            "created_at": {
                "type": "datetime",
                "searchable": False,
                "sortable": True,
                "filterable": True,
                "description": "Task creation date"
            },
            "updated_at": {
                "type": "datetime",
                "searchable": False,
                "sortable": True,
                "filterable": False,
                "description": "Last update date"
            }
        },
        "operators": {
            "text": ["contains", "starts_with", "ends_with", "equals"],
            "boolean": ["equals"],
            "enum": ["equals", "in"],
            "datetime": ["equals", "greater_than", "less_than", "between"]
        }
    }


@router.get("/export")
@rate_limit_api()
async def export_search_results(
    request: Request,
    query: Optional[str] = Query(None),
    completed: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None),
    format: str = Query("json", description="Export format: json, csv"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Export search results in various formats.
    
    Currently supports JSON format. CSV support can be added.
    """
    if format not in ["json", "csv"]:
        raise HTTPException(status_code=400, detail="Unsupported export format")
    
    # Use large limit for export
    filters = SearchFilters(
        query=query,
        completed=completed,
        priority=priority,
        skip=0,
        limit=10000  # Large limit for export
    )
    
    try:
        result = await search_service.search_tasks(db, filters, current_user, cache_results=False)
        
        if format == "json":
            return {
                "format": "json",
                "exported_at": "2024-12-10T22:00:00Z",
                "total_records": result.total,
                "data": result.tasks
            }
        elif format == "csv":
            # TODO: Implement CSV export
            raise HTTPException(status_code=501, detail="CSV export not yet implemented")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")