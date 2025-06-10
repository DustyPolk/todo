"""
Cache management endpoints and utilities.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

import models
import schemas
from auth import get_current_user, check_user_role, get_db
from cache import cache_service, invalidate_user_data, invalidate_task_data
from session import get_current_session, SessionData
from security import rate_limit_api, security_logger

router = APIRouter(prefix="/api/cache", tags=["cache"])

@router.get("/stats")
@rate_limit_api()
async def get_cache_stats(
    request: Request,
    current_user: models.User = Depends(check_user_role("admin"))
):
    """Get cache statistics (admin only)."""
    stats = await cache_service.get_cache_stats()
    health = await cache_service.health_check()
    
    return {
        "cache_stats": stats,
        "health": health,
        "timestamp": "2024-12-10T22:50:00Z"
    }

@router.post("/clear")
@rate_limit_api()
async def clear_cache(
    request: Request,
    cache_type: Optional[str] = None,
    current_user: models.User = Depends(check_user_role("admin"))
):
    """Clear cache (admin only)."""
    try:
        if cache_type == "users":
            # Clear user cache
            deleted = await cache_service.delete_pattern("*", "todo_user:")
        elif cache_type == "tasks":
            # Clear task cache
            deleted = await cache_service.delete_pattern("*", "todo_task:")
        elif cache_type == "sessions":
            # Clear sessions
            deleted = await cache_service.delete_pattern("*", "todo_session:")
        elif cache_type == "all":
            # Clear all cache
            user_deleted = await cache_service.delete_pattern("*", "todo_user:")
            task_deleted = await cache_service.delete_pattern("*", "todo_task:")
            cache_deleted = await cache_service.delete_pattern("*", "todo_cache:")
            deleted = user_deleted + task_deleted + cache_deleted
        else:
            # Clear general cache
            deleted = await cache_service.delete_pattern("*", "todo_cache:")
        
        # Log cache clear
        security_logger.log_event(
            "cache_cleared",
            user_id=current_user.id,
            ip_address=request.client.host,
            details={"cache_type": cache_type or "general", "keys_deleted": deleted}
        )
        
        return {
            "message": f"Cache cleared: {cache_type or 'general'}",
            "keys_deleted": deleted
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}"
        )

@router.post("/invalidate/user/{user_id}")
@rate_limit_api()
async def invalidate_user_cache(
    user_id: int,
    request: Request,
    current_user: models.User = Depends(check_user_role("admin"))
):
    """Invalidate cache for a specific user (admin only)."""
    try:
        await invalidate_user_data(user_id)
        
        # Log cache invalidation
        security_logger.log_event(
            "user_cache_invalidated",
            user_id=current_user.id,
            ip_address=request.client.host,
            details={"target_user_id": user_id}
        )
        
        return {"message": f"Cache invalidated for user {user_id}"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invalidate user cache: {str(e)}"
        )

@router.post("/invalidate/task/{task_id}")
@rate_limit_api()
async def invalidate_task_cache(
    task_id: int,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Invalidate cache for a specific task."""
    # Check if user owns the task or is admin
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    if current_user.role != "admin" and task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to invalidate this task's cache"
        )
    
    try:
        await invalidate_task_data(task_id, task.user_id)
        
        return {"message": f"Cache invalidated for task {task_id}"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invalidate task cache: {str(e)}"
        )

@router.post("/invalidate/my-cache")
@rate_limit_api()
async def invalidate_my_cache(
    request: Request,
    current_user: models.User = Depends(get_current_user)
):
    """Invalidate cache for current user."""
    try:
        await invalidate_user_data(current_user.id)
        
        return {"message": "Your cache has been invalidated"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invalidate cache: {str(e)}"
        )

@router.get("/keys")
@rate_limit_api()
async def list_cache_keys(
    request: Request,
    prefix: Optional[str] = None,
    pattern: str = "*",
    current_user: models.User = Depends(check_user_role("admin"))
):
    """List cache keys (admin only)."""
    try:
        cache_prefix = {
            "users": "todo_user:",
            "tasks": "todo_task:",
            "sessions": "todo_session:",
            "cache": "todo_cache:",
            "ratelimit": "todo_ratelimit:"
        }.get(prefix, "todo_cache:")
        
        keys = await cache_service.get_keys(pattern, cache_prefix)
        
        return {
            "prefix": cache_prefix,
            "pattern": pattern,
            "keys": keys,
            "count": len(keys)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list cache keys: {str(e)}"
        )

@router.get("/session/info")
@rate_limit_api()
async def get_session_info(
    request: Request,
    current_user: models.User = Depends(get_current_user)
):
    """Get current session information."""
    session = await get_current_session(request)
    
    if not session:
        return {
            "session_active": False,
            "authentication_method": "JWT"
        }
    
    return {
        "session_active": True,
        "authentication_method": "Session",
        "session_id": getattr(request.state, 'session_id', None),
        "user_id": session.user_id,
        "username": session.username,
        "role": session.role,
        "created_at": session.created_at,
        "last_accessed": session.last_accessed,
        "session_data": session.data
    }

@router.post("/session/update")
@rate_limit_api()
async def update_session_data(
    request: Request,
    session_data: Dict[str, Any],
    current_user: models.User = Depends(get_current_user)
):
    """Update current session data."""
    session_id = getattr(request.state, 'session_id', None)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active session found"
        )
    
    try:
        from session import session_manager
        success = await session_manager.update_session(session_id, session_data)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        return {"message": "Session data updated successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session: {str(e)}"
        )

@router.delete("/session")
@rate_limit_api()
async def delete_current_session(
    request: Request,
    current_user: models.User = Depends(get_current_user)
):
    """Delete current session (logout)."""
    session_id = getattr(request.state, 'session_id', None)
    if not session_id:
        return {"message": "No active session to delete"}
    
    try:
        from session import session_manager
        success = await session_manager.delete_session(session_id)
        
        # Log session deletion
        security_logger.log_event(
            "session_deleted",
            user_id=current_user.id,
            ip_address=request.client.host,
            details={"session_id": session_id[:16] + "..."}  # Partial ID for privacy
        )
        
        return {"message": "Session deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )

@router.post("/session/cleanup")
@rate_limit_api()
async def cleanup_expired_sessions(
    request: Request,
    current_user: models.User = Depends(check_user_role("admin"))
):
    """Clean up expired sessions (admin only)."""
    try:
        from session import session_manager
        cleaned_count = await session_manager.cleanup_expired_sessions()
        
        # Log session cleanup
        security_logger.log_event(
            "sessions_cleaned",
            user_id=current_user.id,
            ip_address=request.client.host,
            details={"sessions_cleaned": cleaned_count}
        )
        
        return {
            "message": f"Cleaned up {cleaned_count} expired sessions",
            "sessions_cleaned": cleaned_count
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup sessions: {str(e)}"
        )