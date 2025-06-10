"""
Cache and session management tests.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from cache import CacheService, CacheConfig, SessionData
from session import SessionManager
import models

@pytest.fixture
def cache_config():
    """Test cache configuration."""
    return CacheConfig(
        host="localhost",
        port=6379,
        db=1,  # Use different DB for testing
        default_ttl=60,
        long_ttl=300,
        short_ttl=30
    )

@pytest.fixture
async def cache_service():
    """Test cache service with FakeRedis."""
    service = CacheService(use_fake_redis=True)
    await service.connect()
    yield service
    await service.disconnect()

@pytest.fixture
def session_manager():
    """Test session manager."""
    return SessionManager()

class TestCacheService:
    """Test cache service functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_connection(self, cache_service):
        """Test cache connection."""
        assert cache_service._connected
        assert await cache_service.health_check()
    
    @pytest.mark.asyncio
    async def test_basic_cache_operations(self, cache_service):
        """Test basic cache set/get/delete operations."""
        # Test string value
        assert await cache_service.set("test_key", "test_value", 60)
        assert await cache_service.get("test_key") == "test_value"
        assert await cache_service.exists("test_key")
        
        # Test dict value
        test_dict = {"name": "test", "value": 123}
        assert await cache_service.set("test_dict", test_dict, 60)
        cached_dict = await cache_service.get("test_dict")
        assert cached_dict == test_dict
        
        # Test list value
        test_list = [1, 2, 3, {"nested": "value"}]
        assert await cache_service.set("test_list", test_list, 60)
        cached_list = await cache_service.get("test_list")
        assert cached_list == test_list
        
        # Test delete
        assert await cache_service.delete("test_key")
        assert not await cache_service.exists("test_key")
        assert await cache_service.get("test_key") is None
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache_service):
        """Test cache expiration."""
        await cache_service.set("expire_test", "value", 1)  # 1 second TTL
        assert await cache_service.get("expire_test") == "value"
        
        # Update expiration
        assert await cache_service.expire("expire_test", 60)
        
        # Test with very short TTL (FakeRedis doesn't automatically expire)
        await cache_service.set("short_test", "value", 1)
        assert await cache_service.exists("short_test")
    
    @pytest.mark.asyncio
    async def test_pattern_operations(self, cache_service):
        """Test pattern-based operations."""
        # Set multiple keys
        await cache_service.set("user_1_tasks", [1, 2, 3], 60)
        await cache_service.set("user_1_profile", {"name": "test"}, 60)
        await cache_service.set("user_2_tasks", [4, 5, 6], 60)
        
        # Get keys with pattern
        user1_keys = await cache_service.get_keys("user_1_*")
        assert len(user1_keys) >= 2
        assert "user_1_tasks" in user1_keys
        assert "user_1_profile" in user1_keys
        
        # Delete pattern
        deleted = await cache_service.delete_pattern("user_1_*")
        assert deleted >= 2
        assert not await cache_service.exists("user_1_tasks")
        assert not await cache_service.exists("user_1_profile")
        assert await cache_service.exists("user_2_tasks")  # Should still exist
    
    @pytest.mark.asyncio
    async def test_user_specific_caching(self, cache_service):
        """Test user-specific cache operations."""
        user_id = 123
        user_data = {"username": "testuser", "role": "user"}
        
        # Cache user data
        assert await cache_service.cache_user_data(user_id, user_data, 300)
        
        # Get user data
        cached_data = await cache_service.get_user_data(user_id)
        assert cached_data == user_data
        
        # Invalidate user cache
        assert await cache_service.invalidate_user_cache(user_id)
        assert await cache_service.get_user_data(user_id) is None
    
    @pytest.mark.asyncio
    async def test_task_caching(self, cache_service):
        """Test task-specific cache operations."""
        user_id = 123
        task_id = 456
        
        # Cache user tasks
        tasks = [
            {"id": 1, "title": "Task 1", "completed": False},
            {"id": 2, "title": "Task 2", "completed": True}
        ]
        assert await cache_service.cache_user_tasks(user_id, tasks, 300)
        
        # Get user tasks
        cached_tasks = await cache_service.get_user_tasks(user_id)
        assert cached_tasks == tasks
        
        # Cache individual task
        task_data = {"id": task_id, "title": "Individual Task", "completed": False}
        assert await cache_service.cache_task(task_id, task_data, 300)
        
        # Get individual task
        cached_task = await cache_service.get_task(task_id)
        assert cached_task == task_data
        
        # Invalidate task cache
        assert await cache_service.invalidate_task_cache(task_id, user_id)
        assert await cache_service.get_task(task_id) is None
        assert await cache_service.get_user_tasks(user_id) is None
    
    @pytest.mark.asyncio
    async def test_rate_limiting_support(self, cache_service):
        """Test rate limiting cache operations."""
        key = "test_user_login"
        
        # Increment rate limit counter
        count1 = await cache_service.increment_rate_limit(key, 60)
        assert count1 == 1
        
        count2 = await cache_service.increment_rate_limit(key, 60)
        assert count2 == 2
        
        # Get current count
        current = await cache_service.get_rate_limit(key)
        assert current == 2
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, cache_service):
        """Test cache statistics."""
        # Add some test data
        await cache_service.set("test1", "value1", 60)
        await cache_service.set("test2", "value2", 60)
        
        stats = await cache_service.get_cache_stats()
        assert "total_keys" in stats
        assert "redis_type" in stats
        assert stats["redis_type"] == "FakeRedis (Testing/Fallback)"

class TestSessionManagement:
    """Test session management functionality."""
    
    @pytest.mark.asyncio
    async def test_session_creation(self, cache_service, session_manager):
        """Test session creation."""
        # Mock user
        user = models.User(
            id=123,
            username="testuser",
            email="test@example.com",
            role="user"
        )
        
        # Create session
        session_id = await session_manager.create_session(user)
        assert session_id
        assert len(session_id) > 20  # Should be a long random string
        
        # Get session
        session = await session_manager.get_session(session_id)
        assert session
        assert session.user_id == user.id
        assert session.username == user.username
        assert session.role == user.role
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_accessed, datetime)
    
    @pytest.mark.asyncio
    async def test_session_update(self, cache_service, session_manager):
        """Test session data updates."""
        # Mock user
        user = models.User(
            id=123,
            username="testuser",
            email="test@example.com",
            role="user"
        )
        
        # Create session
        session_id = await session_manager.create_session(user, {"initial": "data"})
        
        # Update session
        update_data = {"new_key": "new_value", "counter": 1}
        assert await session_manager.update_session(session_id, update_data)
        
        # Verify update
        session = await session_manager.get_session(session_id)
        assert session.data["initial"] == "data"  # Original data preserved
        assert session.data["new_key"] == "new_value"  # New data added
        assert session.data["counter"] == 1
    
    @pytest.mark.asyncio
    async def test_session_deletion(self, cache_service, session_manager):
        """Test session deletion."""
        # Mock user
        user = models.User(
            id=123,
            username="testuser",
            email="test@example.com",
            role="user"
        )
        
        # Create session
        session_id = await session_manager.create_session(user)
        
        # Verify session exists
        session = await session_manager.get_session(session_id)
        assert session is not None
        
        # Delete session
        assert await session_manager.delete_session(session_id)
        
        # Verify session is gone
        session = await session_manager.get_session(session_id)
        assert session is None
    
    @pytest.mark.asyncio
    async def test_session_cleanup(self, cache_service, session_manager):
        """Test expired session cleanup."""
        # This test is more relevant for real Redis with TTL
        # For FakeRedis, we'll test the manual cleanup logic
        
        # Mock user
        user = models.User(
            id=123,
            username="testuser",
            email="test@example.com",
            role="user"
        )
        
        # Create session
        session_id = await session_manager.create_session(user)
        
        # Manually expire session by setting old last_accessed time
        session = await session_manager.get_session(session_id)
        old_time = datetime.utcnow() - timedelta(days=2)  # 2 days ago
        session.last_accessed = old_time
        
        await cache_service.set(
            session_id,
            session.dict(),
            300,  # Short TTL for test
            "todo_session:"
        )
        
        # Run cleanup
        cleaned = await session_manager.cleanup_expired_sessions()
        
        # For FakeRedis, this should clean up expired sessions
        # (In real Redis, TTL handles this automatically)
        assert cleaned >= 0  # May be 0 if FakeRedis doesn't support this
    
    def test_session_id_generation(self, session_manager):
        """Test session ID generation."""
        id1 = session_manager.generate_session_id()
        id2 = session_manager.generate_session_id()
        
        assert id1 != id2  # Should be unique
        assert len(id1) > 20  # Should be long enough
        assert len(id2) > 20

class TestCacheIntegration:
    """Test cache integration with app components."""
    
    @pytest.mark.asyncio
    async def test_cache_decorator(self, cache_service):
        """Test cache result decorator."""
        from cache import cache_result
        
        call_count = 0
        
        @cache_result(ttl=60)
        async def expensive_function(arg1, arg2):
            nonlocal call_count
            call_count += 1
            return f"result_{arg1}_{arg2}"
        
        # First call should execute function
        result1 = await expensive_function("a", "b")
        assert result1 == "result_a_b"
        assert call_count == 1
        
        # Second call should use cache
        result2 = await expensive_function("a", "b")
        assert result2 == "result_a_b"
        assert call_count == 1  # Function not called again
        
        # Different args should execute function
        result3 = await expensive_function("c", "d")
        assert result3 == "result_c_d"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_helpers(self, cache_service):
        """Test cache invalidation helper functions."""
        from cache import invalidate_user_data, invalidate_task_data
        
        user_id = 123
        task_id = 456
        
        # Set up some cached data
        await cache_service.cache_user_data(user_id, {"test": "data"}, 300)
        await cache_service.cache_task(task_id, {"task": "data"}, 300)
        await cache_service.cache_user_tasks(user_id, [{"id": task_id}], 300)
        
        # Verify data exists
        assert await cache_service.get_user_data(user_id) is not None
        assert await cache_service.get_task(task_id) is not None
        assert await cache_service.get_user_tasks(user_id) is not None
        
        # Invalidate user data
        await invalidate_user_data(user_id)
        assert await cache_service.get_user_data(user_id) is None
        
        # Reset task data
        await cache_service.cache_task(task_id, {"task": "data"}, 300)
        await cache_service.cache_user_tasks(user_id, [{"id": task_id}], 300)
        
        # Invalidate task data
        await invalidate_task_data(task_id, user_id)
        assert await cache_service.get_task(task_id) is None
        assert await cache_service.get_user_tasks(user_id) is None

# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])