"""
Redis caching and session management service.
"""
import json
import pickle
import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List, Union
from contextlib import asynccontextmanager

import redis
from fakeredis import FakeRedis
import asyncio
from functools import wraps
from pydantic import BaseModel

from config import (
    REDIS_URL, REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, REDIS_SSL,
    CACHE_DEFAULT_TTL, CACHE_LONG_TTL, CACHE_SHORT_TTL,
    SESSION_TTL, SESSION_CLEANUP_INTERVAL,
    CACHE_PREFIX, SESSION_PREFIX, RATE_LIMIT_PREFIX, 
    USER_CACHE_PREFIX, TASK_CACHE_PREFIX
)

class CacheConfig(BaseModel):
    """Cache configuration model."""
    host: str = REDIS_HOST
    port: int = REDIS_PORT
    db: int = REDIS_DB
    password: Optional[str] = REDIS_PASSWORD
    ssl: bool = REDIS_SSL
    url: str = REDIS_URL
    default_ttl: int = CACHE_DEFAULT_TTL
    long_ttl: int = CACHE_LONG_TTL
    short_ttl: int = CACHE_SHORT_TTL

class SessionData(BaseModel):
    """Session data model."""
    user_id: int
    username: str
    role: str
    created_at: datetime
    last_accessed: datetime
    data: Dict[str, Any] = {}

def async_redis_operation(func):
    """Decorator to run Redis operations asynchronously."""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if self.use_fake_redis:
            # For FakeRedis, run in executor to simulate async
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: func(self, *args, **kwargs))
        else:
            # For real Redis, use async directly
            return await func(self, *args, **kwargs)
    return wrapper

class CacheService:
    """Redis caching and session management service."""
    
    def __init__(self, config: CacheConfig = None, use_fake_redis: bool = False):
        self.config = config or CacheConfig()
        self.use_fake_redis = use_fake_redis
        self._redis_client = None
        self._connected = False
        
    async def connect(self):
        """Initialize Redis connections."""
        if self._connected:
            return
            
        try:
            if self.use_fake_redis:
                # Use FakeRedis for testing
                self._redis_client = FakeRedis(
                    host=self.config.host,
                    port=self.config.port,
                    db=self.config.db,
                    decode_responses=True
                )
            else:
                # Real Redis connection
                self._redis_client = redis.Redis(
                    host=self.config.host,
                    port=self.config.port,
                    db=self.config.db,
                    password=self.config.password,
                    ssl=self.config.ssl,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                self._redis_client.ping()
            
            self._connected = True
            redis_type = "FakeRedis" if self.use_fake_redis else "Redis"
            print(f"✓ Connected to {redis_type}: {self.config.host}:{self.config.port}")
            
        except Exception as e:
            print(f"⚠️ Redis connection failed, falling back to FakeRedis: {e}")
            # Fallback to FakeRedis
            self.use_fake_redis = True
            self._redis_client = FakeRedis(decode_responses=True)
            self._connected = True
    
    async def disconnect(self):
        """Close Redis connections."""
        if self._redis_client and not self.use_fake_redis:
            self._redis_client.close()
        self._connected = False
    
    def get_redis(self) -> redis.Redis:
        """Get Redis client."""
        if not self._connected:
            raise RuntimeError("Cache service not connected")
        return self._redis_client
    
    def _make_key(self, prefix: str, key: str) -> str:
        """Create a prefixed cache key."""
        return f"{prefix}{key}"
    
    # Basic cache operations
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, prefix: str = CACHE_PREFIX) -> bool:
        """Set a value in cache."""
        if not self._connected:
            await self.connect()
            
        cache_key = self._make_key(prefix, key)
        ttl = ttl or self.config.default_ttl
        
        try:
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value, default=str)
            else:
                serialized_value = str(value)
            
            if self.use_fake_redis:
                # Run in executor for async compatibility
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, 
                    lambda: self._redis_client.setex(cache_key, ttl, serialized_value)
                )
            else:
                self._redis_client.setex(cache_key, ttl, serialized_value)
            return True
        except Exception as e:
            print(f"Cache set error: {e}")
            return False
    
    async def get(self, key: str, prefix: str = CACHE_PREFIX) -> Optional[Any]:
        """Get a value from cache."""
        if not self._connected:
            await self.connect()
            
        cache_key = self._make_key(prefix, key)
        
        try:
            if self.use_fake_redis:
                # Run in executor for async compatibility
                loop = asyncio.get_event_loop()
                value = await loop.run_in_executor(None, lambda: self._redis_client.get(cache_key))
            else:
                value = self._redis_client.get(cache_key)
            
            if value is None:
                return None
            
            # Try to parse as JSON, fallback to string
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            print(f"Cache get error: {e}")
            return None
    
    async def delete(self, key: str, prefix: str = CACHE_PREFIX) -> bool:
        """Delete a value from cache."""
        redis_client = await self.get_async_redis()
        cache_key = self._make_key(prefix, key)
        
        try:
            if self.use_fake_redis:
                result = redis_client.delete(cache_key)
            else:
                result = await redis_client.delete(cache_key)
            return bool(result)
        except Exception as e:
            print(f"Cache delete error: {e}")
            return False
    
    async def exists(self, key: str, prefix: str = CACHE_PREFIX) -> bool:
        """Check if a key exists in cache."""
        redis_client = await self.get_async_redis()
        cache_key = self._make_key(prefix, key)
        
        try:
            if self.use_fake_redis:
                result = redis_client.exists(cache_key)
            else:
                result = await redis_client.exists(cache_key)
            return bool(result)
        except Exception as e:
            print(f"Cache exists error: {e}")
            return False
    
    async def expire(self, key: str, ttl: int, prefix: str = CACHE_PREFIX) -> bool:
        """Set expiration for a key."""
        redis_client = await self.get_async_redis()
        cache_key = self._make_key(prefix, key)
        
        try:
            if self.use_fake_redis:
                result = redis_client.expire(cache_key, ttl)
            else:
                result = await redis_client.expire(cache_key, ttl)
            return bool(result)
        except Exception as e:
            print(f"Cache expire error: {e}")
            return False
    
    # Pattern-based operations
    async def delete_pattern(self, pattern: str, prefix: str = CACHE_PREFIX) -> int:
        """Delete all keys matching a pattern."""
        redis_client = await self.get_async_redis()
        full_pattern = self._make_key(prefix, pattern)
        
        try:
            if self.use_fake_redis:
                keys = redis_client.keys(full_pattern)
                if keys:
                    return redis_client.delete(*keys)
                return 0
            else:
                keys = await redis_client.keys(full_pattern)
                if keys:
                    return await redis_client.delete(*keys)
                return 0
        except Exception as e:
            print(f"Cache delete pattern error: {e}")
            return 0
    
    async def get_keys(self, pattern: str = "*", prefix: str = CACHE_PREFIX) -> List[str]:
        """Get all keys matching a pattern."""
        redis_client = await self.get_async_redis()
        full_pattern = self._make_key(prefix, pattern)
        
        try:
            if self.use_fake_redis:
                keys = redis_client.keys(full_pattern)
            else:
                keys = await redis_client.keys(full_pattern)
            
            # Remove prefix from keys
            prefix_len = len(prefix)
            return [key[prefix_len:] for key in keys if key.startswith(prefix)]
        except Exception as e:
            print(f"Cache get keys error: {e}")
            return []
    
    # User-specific caching
    async def cache_user_data(self, user_id: int, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Cache user-specific data."""
        return await self.set(str(user_id), data, ttl, USER_CACHE_PREFIX)
    
    async def get_user_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get cached user data."""
        return await self.get(str(user_id), USER_CACHE_PREFIX)
    
    async def invalidate_user_cache(self, user_id: int) -> bool:
        """Invalidate all cached data for a user."""
        pattern = f"{user_id}*"
        deleted = await self.delete_pattern(pattern, USER_CACHE_PREFIX)
        await self.delete_pattern(pattern, TASK_CACHE_PREFIX)
        return deleted > 0
    
    # Task-specific caching
    async def cache_user_tasks(self, user_id: int, tasks: List[Dict[str, Any]], 
                               ttl: Optional[int] = None) -> bool:
        """Cache user's tasks."""
        key = f"user_{user_id}_tasks"
        return await self.set(key, tasks, ttl, TASK_CACHE_PREFIX)
    
    async def get_user_tasks(self, user_id: int) -> Optional[List[Dict[str, Any]]]:
        """Get cached user tasks."""
        key = f"user_{user_id}_tasks"
        return await self.get(key, TASK_CACHE_PREFIX)
    
    async def cache_task(self, task_id: int, task_data: Dict[str, Any], 
                         ttl: Optional[int] = None) -> bool:
        """Cache individual task data."""
        return await self.set(str(task_id), task_data, ttl, TASK_CACHE_PREFIX)
    
    async def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Get cached task data."""
        return await self.get(str(task_id), TASK_CACHE_PREFIX)
    
    async def invalidate_task_cache(self, task_id: int, user_id: Optional[int] = None) -> bool:
        """Invalidate cached data for a specific task."""
        deleted = await self.delete(str(task_id), TASK_CACHE_PREFIX)
        
        # Also invalidate user's task list cache
        if user_id:
            user_tasks_key = f"user_{user_id}_tasks"
            await self.delete(user_tasks_key, TASK_CACHE_PREFIX)
        
        return deleted
    
    # Session management
    async def create_session(self, session_id: str, user_id: int, username: str, 
                             role: str, session_data: Dict[str, Any] = None) -> bool:
        """Create a new session."""
        session = SessionData(
            user_id=user_id,
            username=username,
            role=role,
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            data=session_data or {}
        )
        
        return await self.set(
            session_id, 
            session.dict(), 
            SESSION_TTL, 
            SESSION_PREFIX
        )
    
    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session data."""
        session_data = await self.get(session_id, SESSION_PREFIX)
        if not session_data:
            return None
        
        try:
            # Update last accessed time
            session_data['last_accessed'] = datetime.utcnow().isoformat()
            await self.set(session_id, session_data, SESSION_TTL, SESSION_PREFIX)
            
            # Convert datetime strings back to datetime objects
            session_data['created_at'] = datetime.fromisoformat(session_data['created_at'])
            session_data['last_accessed'] = datetime.fromisoformat(session_data['last_accessed'])
            
            return SessionData(**session_data)
        except Exception as e:
            print(f"Session parse error: {e}")
            return None
    
    async def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Update session data."""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        session.data.update(data)
        session.last_accessed = datetime.utcnow()
        
        return await self.set(
            session_id,
            session.dict(),
            SESSION_TTL,
            SESSION_PREFIX
        )
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        return await self.delete(session_id, SESSION_PREFIX)
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions (manual cleanup for FakeRedis)."""
        if not self.use_fake_redis:
            return 0  # Redis handles TTL automatically
        
        sessions = await self.get_keys("*", SESSION_PREFIX)
        expired_count = 0
        
        for session_id in sessions:
            session = await self.get_session(session_id)
            if not session:
                continue
            
            # Check if session is expired
            if (datetime.utcnow() - session.last_accessed).total_seconds() > SESSION_TTL:
                await self.delete_session(session_id)
                expired_count += 1
        
        return expired_count
    
    # Rate limiting support
    async def increment_rate_limit(self, key: str, window: int = 60) -> int:
        """Increment rate limit counter."""
        redis_client = await self.get_async_redis()
        cache_key = self._make_key(RATE_LIMIT_PREFIX, key)
        
        try:
            if self.use_fake_redis:
                current = redis_client.get(cache_key) or 0
                current = int(current) + 1
                redis_client.setex(cache_key, window, current)
                return current
            else:
                # Use Redis pipeline for atomic operation
                pipe = redis_client.pipeline()
                await pipe.incr(cache_key)
                await pipe.expire(cache_key, window)
                result = await pipe.execute()
                return result[0]
        except Exception as e:
            print(f"Rate limit increment error: {e}")
            return 0
    
    async def get_rate_limit(self, key: str) -> int:
        """Get current rate limit count."""
        return await self.get(key, RATE_LIMIT_PREFIX) or 0
    
    # Cache statistics
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        redis_client = await self.get_async_redis()
        
        try:
            if self.use_fake_redis:
                # Limited stats for FakeRedis
                all_keys = redis_client.keys("*")
                return {
                    "total_keys": len(all_keys),
                    "cache_keys": len([k for k in all_keys if k.startswith(CACHE_PREFIX)]),
                    "session_keys": len([k for k in all_keys if k.startswith(SESSION_PREFIX)]),
                    "user_cache_keys": len([k for k in all_keys if k.startswith(USER_CACHE_PREFIX)]),
                    "task_cache_keys": len([k for k in all_keys if k.startswith(TASK_CACHE_PREFIX)]),
                    "rate_limit_keys": len([k for k in all_keys if k.startswith(RATE_LIMIT_PREFIX)]),
                    "redis_type": "FakeRedis (Testing/Fallback)"
                }
            else:
                info = await redis_client.info()
                return {
                    "total_keys": info.get("db0", {}).get("keys", 0),
                    "memory_usage": info.get("used_memory_human", "N/A"),
                    "connected_clients": info.get("connected_clients", 0),
                    "redis_version": info.get("redis_version", "N/A"),
                    "redis_type": "Real Redis"
                }
        except Exception as e:
            print(f"Cache stats error: {e}")
            return {"error": str(e)}
    
    # Health check
    async def health_check(self) -> bool:
        """Check if cache is healthy."""
        try:
            test_key = "health_check"
            await self.set(test_key, "ok", 10)
            result = await self.get(test_key)
            await self.delete(test_key)
            return result == "ok"
        except Exception:
            return False

# Global cache service instance
cache_service = CacheService()

# Context manager for cache lifecycle
@asynccontextmanager
async def cache_context():
    """Context manager for cache service lifecycle."""
    await cache_service.connect()
    try:
        yield cache_service
    finally:
        await cache_service.disconnect()

# Decorators for caching
def cache_result(key_func=None, ttl=None, prefix=CACHE_PREFIX):
    """Decorator to cache function results."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached_result = await cache_service.get(cache_key, prefix)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            if result is not None:
                await cache_service.set(cache_key, result, ttl, prefix)
            
            return result
        return wrapper
    return decorator

# Cache invalidation helpers
async def invalidate_user_data(user_id: int):
    """Invalidate all cached data for a user."""
    await cache_service.invalidate_user_cache(user_id)

async def invalidate_task_data(task_id: int, user_id: int = None):
    """Invalidate cached data for a task."""
    await cache_service.invalidate_task_cache(task_id, user_id)