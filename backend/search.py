"""
Search and filtering service for the Todo API.
Provides full-text search, filtering, and advanced query capabilities.
"""
import re
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from enum import Enum
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, not_, func, text, desc, asc
from sqlalchemy.sql.expression import cast
from sqlalchemy.types import Date

from models import Task, User
from cache import cache_service


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class SortField(str, Enum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at" 
    DUE_DATE = "due_date"
    TITLE = "title"
    PRIORITY = "priority"
    COMPLETED = "completed"


@dataclass
class SearchFilters:
    """Search and filter parameters."""
    query: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None
    due_date_from: Optional[date] = None
    due_date_to: Optional[date] = None
    created_from: Optional[date] = None
    created_to: Optional[date] = None
    user_id: Optional[int] = None
    tags: Optional[List[str]] = None
    sort_by: SortField = SortField.CREATED_AT
    sort_order: SortOrder = SortOrder.DESC
    skip: int = 0
    limit: int = 100


@dataclass 
class SearchResult:
    """Search result with metadata."""
    tasks: List[Dict[str, Any]]
    total: int
    page: int
    size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    search_time_ms: Optional[float] = None


class SearchService:
    """Search and filtering service."""
    
    def __init__(self):
        self.search_operators = {
            "AND": " AND ",
            "OR": " OR ",
            "NOT": " NOT "
        }
    
    def _parse_search_query(self, query: str) -> Tuple[str, List[str]]:
        """Parse search query into SQL LIKE patterns and extract keywords."""
        if not query:
            return "", []
        
        # Remove special characters except spaces, quotes, and operators
        cleaned_query = re.sub(r'[^\w\s"()+-]', '', query)
        
        # Extract quoted phrases
        phrases = re.findall(r'"([^"]+)"', cleaned_query)
        
        # Remove quoted phrases from the main query
        for phrase in phrases:
            cleaned_query = cleaned_query.replace(f'"{phrase}"', '')
        
        # Extract individual words
        words = cleaned_query.split()
        
        # Combine phrases and words
        keywords = phrases + words
        keywords = [kw.strip() for kw in keywords if kw.strip()]
        
        # Create SQL pattern
        sql_pattern = " ".join([f"%{kw}%" for kw in keywords])
        
        return sql_pattern, keywords
    
    def _build_search_conditions(self, query: str, keywords: List[str]):
        """Build search conditions for title and description."""
        if not keywords:
            return None
        
        conditions = []
        
        for keyword in keywords:
            keyword_pattern = f"%{keyword}%"
            conditions.append(
                or_(
                    Task.title.ilike(keyword_pattern),
                    Task.description.ilike(keyword_pattern)
                )
            )
        
        # All keywords must match (AND logic by default)
        return and_(*conditions)
    
    def _apply_filters(self, query, filters: SearchFilters):
        """Apply filters to the query."""
        
        # Text search
        if filters.query:
            _, keywords = self._parse_search_query(filters.query)
            search_condition = self._build_search_conditions(filters.query, keywords)
            if search_condition is not None:
                query = query.filter(search_condition)
        
        # Completion filter
        if filters.completed is not None:
            query = query.filter(Task.completed == filters.completed)
        
        # Priority filter
        if filters.priority:
            priorities = filters.priority.split(',') if ',' in filters.priority else [filters.priority]
            query = query.filter(Task.priority.in_(priorities))
        
        # Due date range
        if filters.due_date_from:
            query = query.filter(cast(Task.due_date, Date) >= filters.due_date_from)
        if filters.due_date_to:
            query = query.filter(cast(Task.due_date, Date) <= filters.due_date_to)
        
        # Created date range
        if filters.created_from:
            query = query.filter(cast(Task.created_at, Date) >= filters.created_from)
        if filters.created_to:
            query = query.filter(cast(Task.created_at, Date) <= filters.created_to)
        
        # User filter
        if filters.user_id:
            query = query.filter(Task.user_id == filters.user_id)
        
        return query
    
    def _apply_sorting(self, query, filters: SearchFilters):
        """Apply sorting to the query."""
        sort_field = getattr(Task, filters.sort_by.value)
        
        if filters.sort_order == SortOrder.DESC:
            query = query.order_by(desc(sort_field))
        else:
            query = query.order_by(asc(sort_field))
        
        # Secondary sort by created_at for consistency
        if filters.sort_by != SortField.CREATED_AT:
            query = query.order_by(desc(Task.created_at))
        
        return query
    
    async def search_tasks(
        self, 
        db: Session, 
        filters: SearchFilters,
        user: User,
        cache_results: bool = True
    ) -> SearchResult:
        """Search tasks with filters and pagination."""
        start_time = datetime.now()
        
        # Create cache key for search results
        cache_key = None
        if cache_results and not filters.query:  # Only cache simple filters, not text search
            cache_key = self._generate_cache_key(filters, user)
            cached_result = await cache_service.get(cache_key, "search:")
            if cached_result:
                cached_result["search_time_ms"] = (datetime.now() - start_time).total_seconds() * 1000
                return SearchResult(**cached_result)
        
        # Build base query
        query = db.query(Task)
        
        # Apply user scope (non-admin users only see their tasks)
        if user.role != "admin":
            query = query.filter(Task.user_id == user.id)
        
        # Apply filters
        query = self._apply_filters(query, filters)
        
        # Get total count before pagination
        total = query.count()
        
        # Apply sorting
        query = self._apply_sorting(query, filters)
        
        # Apply pagination
        query = query.offset(filters.skip).limit(filters.limit)
        
        # Execute query
        tasks = query.all()
        
        # Convert to dict format
        tasks_data = [
            {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "completed": task.completed,
                "priority": task.priority,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "user_id": task.user_id,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat()
            }
            for task in tasks
        ]
        
        # Calculate pagination metadata
        page = (filters.skip // filters.limit) + 1
        total_pages = (total + filters.limit - 1) // filters.limit
        has_next = filters.skip + filters.limit < total
        has_prev = filters.skip > 0
        
        search_time = (datetime.now() - start_time).total_seconds() * 1000
        
        result = SearchResult(
            tasks=tasks_data,
            total=total,
            page=page,
            size=len(tasks_data),
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev,
            search_time_ms=search_time
        )
        
        # Cache results if applicable
        if cache_key and not filters.query:
            await cache_service.set(
                cache_key, 
                {
                    "tasks": tasks_data,
                    "total": total,
                    "page": page,
                    "size": len(tasks_data),
                    "total_pages": total_pages,
                    "has_next": has_next,
                    "has_prev": has_prev
                }, 
                ttl=300,  # 5 minutes
                prefix="search:"
            )
        
        return result
    
    def _generate_cache_key(self, filters: SearchFilters, user: User) -> str:
        """Generate cache key for search results."""
        key_parts = [
            f"user_{user.id}",
            f"completed_{filters.completed}",
            f"priority_{filters.priority or 'all'}",
            f"due_from_{filters.due_date_from or 'none'}",
            f"due_to_{filters.due_date_to or 'none'}",
            f"created_from_{filters.created_from or 'none'}",
            f"created_to_{filters.created_to or 'none'}",
            f"sort_{filters.sort_by}_{filters.sort_order}",
            f"skip_{filters.skip}",
            f"limit_{filters.limit}"
        ]
        return "_".join(key_parts)
    
    async def get_search_suggestions(
        self,
        db: Session,
        query: str,
        user: User,
        limit: int = 10
    ) -> List[str]:
        """Get search suggestions/autocomplete."""
        if not query or len(query) < 2:
            return []
        
        # Cache key for suggestions
        cache_key = f"user_{user.id}_suggestions_{query.lower()}"
        cached_suggestions = await cache_service.get(cache_key, "suggestions:")
        if cached_suggestions:
            return cached_suggestions
        
        query_pattern = f"%{query}%"
        
        # Get unique titles and descriptions that match
        suggestions = set()
        
        # Query for matching titles
        title_query = db.query(Task.title).filter(
            Task.title.ilike(query_pattern)
        )
        if user.role != "admin":
            title_query = title_query.filter(Task.user_id == user.id)
        
        titles = title_query.distinct().limit(limit).all()
        for (title,) in titles:
            if title and query.lower() in title.lower():
                suggestions.add(title)
        
        # Extract words from descriptions
        desc_query = db.query(Task.description).filter(
            Task.description.ilike(query_pattern)
        )
        if user.role != "admin":
            desc_query = desc_query.filter(Task.user_id == user.id)
        
        descriptions = desc_query.distinct().limit(limit * 2).all()
        for (desc,) in descriptions:
            if desc:
                words = desc.split()
                for word in words:
                    if len(word) >= 3 and query.lower() in word.lower():
                        suggestions.add(word)
        
        # Convert to sorted list
        suggestion_list = sorted(list(suggestions))[:limit]
        
        # Cache suggestions
        await cache_service.set(
            cache_key,
            suggestion_list,
            ttl=3600,  # 1 hour
            prefix="suggestions:"
        )
        
        return suggestion_list
    
    async def get_filter_statistics(
        self,
        db: Session,
        user: User
    ) -> Dict[str, Any]:
        """Get statistics for filter options."""
        cache_key = f"user_{user.id}_filter_stats"
        cached_stats = await cache_service.get(cache_key, "stats:")
        if cached_stats:
            return cached_stats
        
        # Base query for user's tasks
        base_query = db.query(Task)
        if user.role != "admin":
            base_query = base_query.filter(Task.user_id == user.id)
        
        # Get priority distribution
        priority_stats = db.query(
            Task.priority,
            func.count(Task.id).label('count')
        ).filter(Task.user_id == user.id if user.role != "admin" else True)\
         .group_by(Task.priority).all()
        
        # Get completion statistics
        completion_stats = db.query(
            Task.completed,
            func.count(Task.id).label('count')
        ).filter(Task.user_id == user.id if user.role != "admin" else True)\
         .group_by(Task.completed).all()
        
        # Get date ranges
        date_stats = db.query(
            func.min(Task.created_at).label('min_created'),
            func.max(Task.created_at).label('max_created'),
            func.min(Task.due_date).label('min_due'),
            func.max(Task.due_date).label('max_due')
        ).filter(Task.user_id == user.id if user.role != "admin" else True).first()
        
        stats = {
            "priorities": {priority: count for priority, count in priority_stats},
            "completion": {str(completed): count for completed, count in completion_stats},
            "date_ranges": {
                "created_from": date_stats.min_created.isoformat() if date_stats.min_created else None,
                "created_to": date_stats.max_created.isoformat() if date_stats.max_created else None,
                "due_from": date_stats.min_due.isoformat() if date_stats.min_due else None,
                "due_to": date_stats.max_due.isoformat() if date_stats.max_due else None
            },
            "total_tasks": sum(count for _, count in completion_stats)
        }
        
        # Cache statistics
        await cache_service.set(
            cache_key,
            stats,
            ttl=1800,  # 30 minutes
            prefix="stats:"
        )
        
        return stats
    
    async def invalidate_search_cache(self, user_id: int):
        """Invalidate search-related cache for a user."""
        patterns = [
            f"user_{user_id}_*",
            f"*user_{user_id}*"
        ]
        
        for pattern in patterns:
            await cache_service.delete_pattern(pattern, "search:")
            await cache_service.delete_pattern(pattern, "suggestions:")
            await cache_service.delete_pattern(pattern, "stats:")


# Global search service instance
search_service = SearchService()