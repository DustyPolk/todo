"""
Simplified Redis caching and session management service.
"""
import json
import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List
from functools import wraps
from contextlib import asynccontextmanager

import redis
from fakeredis import FakeRedis
from pydantic import BaseModel

from config import (
    REDIS_URL, REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, REDIS_SSL,
    CACHE_DEFAULT_TTL, CACHE_LONG_TTL, CACHE_SHORT_TTL,
    SESSION_TTL, CACHE_PREFIX, SESSION_PREFIX, RATE_LIMIT_PREFIX, 
    USER_CACHE_PREFIX, TASK_CACHE_PREFIX
)

class SessionData(BaseModel):
    """Session data model."""
    user_id: int
    username: str
    role: str
    created_at: datetime
    last_accessed: datetime
    data: Dict[str, Any] = {}

class SimpleCacheService:
    """Simplified Redis caching service."""
    
    def __init__(self, use_fake_redis: bool = False):
        self.use_fake_redis = use_fake_redis
        self._redis = None
        self._connected = False
        
    async def connect(self):
        """Initialize Redis connection."""
        if self._connected:
            return
            
        try:
            if self.use_fake_redis:
                self._redis = FakeRedis(decode_responses=True)
            else:
                self._redis = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=REDIS_DB,
                    password=REDIS_PASSWORD,
                    ssl=REDIS_SSL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                self._redis.ping()
            
            self._connected = True
            redis_type = "FakeRedis" if self.use_fake_redis else "Redis"
            print(f"✓ Connected to {redis_type}: {REDIS_HOST}:{REDIS_PORT}")
            
        except Exception as e:
            print(f"⚠️ Redis connection failed, using FakeRedis: {e}")
            self.use_fake_redis = True
            self._redis = FakeRedis(decode_responses=True)
            self._connected = True
    
    async def disconnect(self):
        """Close Redis connection."""
        if self._redis and not self.use_fake_redis:
            self._redis.close()
        self._connected = False
    
    async def _run_redis_op(self, operation):
        """Run Redis operation async-safe."""
        if not self._connected:
            await self.connect()
        
        if self.use_fake_redis:
            # FakeRedis is synchronous, run in executor
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, operation)
        else:
            # Real Redis is synchronous too in this simplified version
            return operation()
    
    def _make_key(self, prefix: str, key: str) -> str:
        """Create prefixed cache key."""
        return f"{prefix}{key}"
    
    async def set(self, key: str, value: Any, ttl: int = CACHE_DEFAULT_TTL, prefix: str = CACHE_PREFIX) -> bool:
        """Set value in cache."""
        try:
            cache_key = self._make_key(prefix, key)
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value, default=str)
            else:
                serialized_value = str(value)
            
            result = await self._run_redis_op(
                lambda: self._redis.setex(cache_key, ttl, serialized_value)
            )
            return True
        except Exception as e:
            print(f"Cache set error: {e}")
            return False
    
    async def get(self, key: str, prefix: str = CACHE_PREFIX) -> Optional[Any]:
        """Get value from cache."""
        try:
            cache_key = self._make_key(prefix, key)
            value = await self._run_redis_op(lambda: self._redis.get(cache_key))
            
            if value is None:
                return None
            
            # Try JSON decode, fallback to string
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            print(f"Cache get error: {e}")
            return None
    
    async def delete(self, key: str, prefix: str = CACHE_PREFIX) -> bool:
        """Delete value from cache."""
        try:
            cache_key = self._make_key(prefix, key)
            result = await self._run_redis_op(lambda: self._redis.delete(cache_key))
            return bool(result)
        except Exception as e:
            print(f"Cache delete error: {e}")
            return False
    
    async def exists(self, key: str, prefix: str = CACHE_PREFIX) -> bool:
        """Check if key exists."""
        try:
            cache_key = self._make_key(prefix, key)
            result = await self._run_redis_op(lambda: self._redis.exists(cache_key))
            return bool(result)
        except Exception as e:
            print(f"Cache exists error: {e}")
            return False
    
    async def delete_pattern(self, pattern: str, prefix: str = CACHE_PREFIX) -> int:
        """Delete keys matching pattern."""
        try:
            full_pattern = self._make_key(prefix, pattern)
            keys = await self._run_redis_op(lambda: self._redis.keys(full_pattern))
            if keys:
                deleted = await self._run_redis_op(lambda: self._redis.delete(*keys))
                return deleted
            return 0
        except Exception as e:
            print(f"Cache delete pattern error: {e}")
            return 0
    
    async def get_keys(self, pattern: str = "*", prefix: str = CACHE_PREFIX) -> List[str]:
        """Get keys matching pattern."""
        try:
            full_pattern = self._make_key(prefix, pattern)
            keys = await self._run_redis_op(lambda: self._redis.keys(full_pattern))
            # Remove prefix
            prefix_len = len(prefix)
            return [key[prefix_len:] for key in keys if key.startswith(prefix)]
        except Exception as e:
            print(f"Cache get keys error: {e}")
            return []
    
    # User-specific operations
    async def cache_user_data(self, user_id: int, data: Dict[str, Any], ttl: int = CACHE_DEFAULT_TTL) -> bool:
        """Cache user data."""
        return await self.set(str(user_id), data, ttl, USER_CACHE_PREFIX)
    
    async def get_user_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user data."""
        return await self.get(str(user_id), USER_CACHE_PREFIX)
    
    async def cache_user_tasks(self, user_id: int, tasks: List[Dict[str, Any]], ttl: int = CACHE_DEFAULT_TTL) -> bool:
        """Cache user tasks."""
        key = f"user_{user_id}_tasks"
        return await self.set(key, tasks, ttl, TASK_CACHE_PREFIX)
    
    async def get_user_tasks(self, user_id: int) -> Optional[List[Dict[str, Any]]]:
        """Get user tasks."""
        key = f"user_{user_id}_tasks"
        return await self.get(key, TASK_CACHE_PREFIX)
    
    async def cache_task(self, task_id: int, task_data: Dict[str, Any], ttl: int = CACHE_DEFAULT_TTL) -> bool:
        """Cache task data."""
        return await self.set(str(task_id), task_data, ttl, TASK_CACHE_PREFIX)
    
    async def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Get task data."""
        return await self.get(str(task_id), TASK_CACHE_PREFIX)
    
    async def invalidate_user_cache(self, user_id: int) -> bool:
        """Invalidate user cache."""
        # Delete specific user data
        deleted1 = await self.delete(str(user_id), USER_CACHE_PREFIX)
        
        # Delete user's task list
        user_tasks_key = f"user_{user_id}_tasks"
        deleted2 = await self.delete(user_tasks_key, TASK_CACHE_PREFIX)
        
        return deleted1 or deleted2
    
    async def invalidate_task_cache(self, task_id: int, user_id: Optional[int] = None) -> bool:
        """Invalidate task cache."""
        deleted = await self.delete(str(task_id), TASK_CACHE_PREFIX)
        if user_id:
            user_tasks_key = f"user_{user_id}_tasks"
            await self.delete(user_tasks_key, TASK_CACHE_PREFIX)
        return deleted
    
    # Session operations
    async def create_session(self, session_id: str, user_id: int, username: str, role: str, 
                             session_data: Dict[str, Any] = None) -> bool:
        """Create session."""
        session = SessionData(
            user_id=user_id,
            username=username,
            role=role,
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            data=session_data or {}
        )
        return await self.set(session_id, session.dict(), SESSION_TTL, SESSION_PREFIX)
    
    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session."""
        session_data = await self.get(session_id, SESSION_PREFIX)
        if not session_data:
            return None
        
        try:
            # Update last accessed
            session_data['last_accessed'] = datetime.utcnow().isoformat()
            await self.set(session_id, session_data, SESSION_TTL, SESSION_PREFIX)
            
            # Parse datetime strings
            session_data['created_at'] = datetime.fromisoformat(session_data['created_at'])
            session_data['last_accessed'] = datetime.fromisoformat(session_data['last_accessed'])
            
            return SessionData(**session_data)
        except Exception as e:
            print(f"Session parse error: {e}")
            return None
    
    async def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Update session."""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        session.data.update(data)
        session.last_accessed = datetime.utcnow()
        return await self.set(session_id, session.dict(), SESSION_TTL, SESSION_PREFIX)
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session."""
        return await self.delete(session_id, SESSION_PREFIX)
    
    # Rate limiting
    async def increment_rate_limit(self, key: str, window: int = 60) -> int:
        """Increment rate limit counter."""
        try:
            cache_key = self._make_key(RATE_LIMIT_PREFIX, key)
            current = await self._run_redis_op(lambda: self._redis.get(cache_key)) or 0
            current = int(current) + 1
            await self._run_redis_op(lambda: self._redis.setex(cache_key, window, current))
            return current
        except Exception as e:
            print(f"Rate limit error: {e}")
            return 0
    
    async def get_rate_limit(self, key: str) -> int:
        """Get rate limit count."""
        result = await self.get(key, RATE_LIMIT_PREFIX)
        return int(result) if result else 0
    
    # Health and stats
    async def health_check(self) -> bool:
        """Check cache health."""
        try:
            test_key = "health_check"
            await self.set(test_key, "ok", 10)
            result = await self.get(test_key)
            await self.delete(test_key)
            return result == "ok"
        except Exception:
            return False
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache stats."""
        try:
            if self.use_fake_redis:
                all_keys = await self._run_redis_op(lambda: self._redis.keys("*"))
                return {
                    "total_keys": len(all_keys),
                    "cache_keys": len([k for k in all_keys if k.startswith(CACHE_PREFIX)]),
                    "session_keys": len([k for k in all_keys if k.startswith(SESSION_PREFIX)]),
                    "user_cache_keys": len([k for k in all_keys if k.startswith(USER_CACHE_PREFIX)]),
                    "task_cache_keys": len([k for k in all_keys if k.startswith(TASK_CACHE_PREFIX)]),
                    "rate_limit_keys": len([k for k in all_keys if k.startswith(RATE_LIMIT_PREFIX)]),
                    "redis_type": "FakeRedis"
                }
            else:
                info = await self._run_redis_op(lambda: self._redis.info())
                return {
                    "total_keys": info.get("db0", {}).get("keys", 0),
                    "memory_usage": info.get("used_memory_human", "N/A"),
                    "connected_clients": info.get("connected_clients", 0),
                    "redis_version": info.get("redis_version", "N/A"),
                    "redis_type": "Redis"
                }
        except Exception as e:
            return {"error": str(e)}

# Global cache service
cache_service = SimpleCacheService(use_fake_redis=True)  # Default to FakeRedis for safety

# Alias for compatibility
CacheService = SimpleCacheService

# Helper functions
async def invalidate_user_data(user_id: int):
    """Invalidate user data."""
    await cache_service.invalidate_user_cache(user_id)

async def invalidate_task_data(task_id: int, user_id: int = None):
    """Invalidate task data."""
    await cache_service.invalidate_task_cache(task_id, user_id)

# Context manager for cache lifecycle
@asynccontextmanager
async def cache_context():
    """Context manager for cache service lifecycle."""
    await cache_service.connect()
    try:
        yield cache_service
    finally:
        await cache_service.disconnect()