# Redis Caching and Session Management Documentation

## Overview

The Todo API implements comprehensive Redis-based caching and session management to improve performance, reduce database load, and provide scalable session storage.

## Features

### Caching System
- **Redis Integration** with FakeRedis fallback for development/testing
- **Multi-layer Caching** for users, tasks, and general data
- **Automatic Cache Invalidation** on data updates
- **Configurable TTL** (Time To Live) for different data types
- **Pattern-based Operations** for bulk cache management
- **Cache Statistics** and health monitoring

### Session Management
- **Redis-based Session Storage** with configurable timeout
- **Session Middleware** for automatic session handling
- **Mixed Authentication** supporting both JWT and session-based auth
- **Session Data Management** with user-specific data storage
- **Automatic Session Cleanup** for expired sessions

### Performance Features
- **Async Operations** with executor-based compatibility
- **Connection Pooling** and failover mechanisms
- **Rate Limiting Support** using Redis counters
- **Cache-aside Pattern** implementation
- **Optimistic Caching** with database fallback

## Configuration

### Environment Variables

```bash
# Redis Connection
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=optional-password
REDIS_SSL=false

# Cache Settings
CACHE_DEFAULT_TTL=300      # 5 minutes
CACHE_LONG_TTL=3600        # 1 hour  
CACHE_SHORT_TTL=60         # 1 minute

# Session Settings
SESSION_TTL=86400          # 24 hours
SESSION_CLEANUP_INTERVAL=3600  # 1 hour
```

### Cache Key Prefixes

```python
CACHE_PREFIX = "todo_cache:"        # General cache
SESSION_PREFIX = "todo_session:"    # User sessions
RATE_LIMIT_PREFIX = "todo_ratelimit:"  # Rate limiting
USER_CACHE_PREFIX = "todo_user:"    # User-specific data
TASK_CACHE_PREFIX = "todo_task:"    # Task-specific data
```

## Cache Service API

### Basic Operations

```python
from cache import cache_service

# Set value with TTL
await cache_service.set("key", {"data": "value"}, ttl=300)

# Get value
data = await cache_service.get("key")

# Delete value
await cache_service.delete("key")

# Check if key exists
exists = await cache_service.exists("key")

# Delete keys by pattern
deleted_count = await cache_service.delete_pattern("user_*")
```

### User-Specific Caching

```python
# Cache user data
await cache_service.cache_user_data(user_id, user_data, ttl=3600)

# Get cached user data
user_data = await cache_service.get_user_data(user_id)

# Cache user's tasks
await cache_service.cache_user_tasks(user_id, tasks_list, ttl=300)

# Get cached user tasks
tasks = await cache_service.get_user_tasks(user_id)

# Invalidate all user cache
await cache_service.invalidate_user_cache(user_id)
```

### Task-Specific Caching

```python
# Cache individual task
await cache_service.cache_task(task_id, task_data, ttl=600)

# Get cached task
task_data = await cache_service.get_task(task_id)

# Invalidate task cache
await cache_service.invalidate_task_cache(task_id, user_id)
```

### Session Management

```python
from session import SessionManager

session_manager = SessionManager()

# Create session
session_id = await session_manager.create_session(user, {"theme": "dark"})

# Get session
session = await session_manager.get_session(session_id)

# Update session data
await session_manager.update_session(session_id, {"last_page": "/dashboard"})

# Delete session
await session_manager.delete_session(session_id)
```

## API Endpoints

### Cache Management (Admin Only)

#### Get Cache Statistics
```http
GET /api/cache/stats
Authorization: Bearer admin-jwt-token
```

Response:
```json
{
  "cache_stats": {
    "total_keys": 1250,
    "cache_keys": 45,
    "session_keys": 23,
    "user_cache_keys": 15,
    "task_cache_keys": 67,
    "redis_type": "Redis"
  },
  "health": true,
  "timestamp": "2024-12-10T22:50:00Z"
}
```

#### Clear Cache
```http
POST /api/cache/clear
Authorization: Bearer admin-jwt-token
Content-Type: application/json

{
  "cache_type": "users"  // "users", "tasks", "sessions", "all"
}
```

#### Invalidate User Cache
```http
POST /api/cache/invalidate/user/{user_id}
Authorization: Bearer admin-jwt-token
```

#### Invalidate Task Cache
```http
POST /api/cache/invalidate/task/{task_id}
Authorization: Bearer jwt-token
```

### Session Management

#### Get Session Info
```http
GET /api/cache/session/info
Authorization: Bearer jwt-token
```

Response:
```json
{
  "session_active": true,
  "authentication_method": "Session",
  "session_id": "abc123...",
  "user_id": 123,
  "username": "testuser",
  "role": "user",
  "created_at": "2024-12-10T10:00:00Z",
  "last_accessed": "2024-12-10T22:45:00Z",
  "session_data": {
    "theme": "dark",
    "language": "en"
  }
}
```

#### Update Session Data
```http
POST /api/cache/session/update
Authorization: Bearer jwt-token
Content-Type: application/json

{
  "theme": "light",
  "notifications": true
}
```

#### Delete Session (Logout)
```http
DELETE /api/cache/session
Authorization: Bearer jwt-token
```

## Caching Strategies

### Cache-Aside Pattern

The API implements cache-aside pattern where:

1. **Read Operations**: Check cache first, fallback to database
2. **Write Operations**: Update database, then invalidate cache
3. **Cache Misses**: Load from database and populate cache

```python
# Example implementation in get_tasks endpoint
async def get_tasks(user_id: int):
    # Try cache first
    cached_tasks = await cache_service.get_user_tasks(user_id)
    if cached_tasks:
        return cached_tasks
    
    # Cache miss - load from database
    tasks = db.query(Task).filter(Task.user_id == user_id).all()
    
    # Populate cache
    await cache_service.cache_user_tasks(user_id, tasks, ttl=300)
    
    return tasks
```

### Cache Invalidation Strategy

#### Automatic Invalidation
- **Task Creation**: Invalidates user's task list cache
- **Task Update**: Invalidates specific task and user's task list
- **Task Deletion**: Invalidates specific task and user's task list
- **User Update**: Invalidates user-specific cache

#### Manual Invalidation
- Admin endpoints for cache management
- User endpoints for self-cache invalidation
- Pattern-based bulk invalidation

### TTL Strategy

```python
# Different TTL for different data types
USER_PROFILE_TTL = 3600      # 1 hour (changes infrequently)
TASK_LIST_TTL = 300          # 5 minutes (changes frequently)
TASK_DETAIL_TTL = 600        # 10 minutes (moderate changes)
SEARCH_RESULTS_TTL = 60      # 1 minute (dynamic data)
RATE_LIMIT_TTL = 3600        # 1 hour (security data)
```

## Session Architecture

### Session Storage Model

```python
class SessionData:
    user_id: int                    # User identifier
    username: str                   # Username for quick access
    role: str                       # User role for authorization
    created_at: datetime           # Session creation time
    last_accessed: datetime        # Last activity timestamp
    data: Dict[str, Any]           # Custom session data
```

### Session Security

- **Secure Session IDs**: 32-byte URL-safe tokens
- **Session TTL**: Configurable timeout (default 24 hours)
- **Activity Tracking**: Last accessed time updated on each request
- **Cleanup Process**: Automatic removal of expired sessions

### Mixed Authentication

The system supports both JWT and session-based authentication:

```python
# JWT Authentication (stateless)
Authorization: Bearer eyJhbGciOiJIUzI1NiI...

# Session Authentication (stateful)
Authorization: Session abc123def456...
# OR
Cookie: session_id=abc123def456...
# OR
X-Session-ID: abc123def456...
```

## Performance Optimization

### Connection Management
- **Connection Pooling**: Reuse Redis connections
- **Async Operations**: Non-blocking cache operations
- **Failover**: Automatic fallback to FakeRedis
- **Health Checks**: Monitor Redis availability

### Cache Efficiency
- **Key Compression**: Efficient key naming
- **Data Serialization**: JSON with compression
- **Pattern Operations**: Bulk cache management
- **Memory Management**: TTL-based cleanup

### Monitoring Metrics
- Cache hit/miss ratios
- Redis memory usage
- Session count and activity
- Rate limiting effectiveness
- Cache operation latency

## Redis Setup

### Development (FakeRedis)
No Redis server required - automatic fallback to FakeRedis for testing.

### Production (Real Redis)

#### Installation
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install redis-server

# macOS
brew install redis

# Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

#### Configuration
```bash
# Update environment variables
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your-secure-password
```

#### High Availability Setup
```bash
# Redis Sentinel for failover
redis-sentinel /etc/redis/sentinel.conf

# Redis Cluster for scaling
redis-server /etc/redis/cluster.conf --cluster-enabled yes
```

## Testing

### Running Cache Tests
```bash
# Run cache tests
python -m pytest test_cache.py -v

# Run cache verification
python verify_cache.py
```

### Test Coverage
- ✅ Basic cache operations (set/get/delete)
- ✅ Complex data type caching
- ✅ Session creation and management
- ✅ User-specific caching
- ✅ Task-specific caching
- ✅ Cache invalidation
- ✅ Rate limiting support
- ✅ Health checks and statistics

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   ```
   Solution: Falls back to FakeRedis automatically
   Check: REDIS_URL configuration
   ```

2. **Cache Miss Rate High**
   ```
   Solution: Increase TTL values
   Check: Cache invalidation frequency
   ```

3. **Session Timeout Issues**
   ```
   Solution: Adjust SESSION_TTL
   Check: Session cleanup process
   ```

4. **Memory Usage High**
   ```
   Solution: Reduce TTL values
   Check: Cache cleanup and expiration
   ```

### Monitoring Commands

```bash
# Redis CLI monitoring
redis-cli monitor

# Memory usage
redis-cli info memory

# Key analysis
redis-cli --scan --pattern "todo_*"

# Performance stats
redis-cli info stats
```

## Best Practices

### Cache Design
- Use consistent key naming conventions
- Set appropriate TTL values for data types
- Implement cache warming for critical data
- Monitor cache hit ratios

### Session Management
- Use secure session ID generation
- Implement proper session cleanup
- Store minimal data in sessions
- Use database for persistent data

### Security
- Secure Redis with authentication
- Use SSL/TLS for Redis connections
- Implement proper session invalidation
- Monitor for suspicious cache activity

### Performance
- Batch cache operations when possible
- Use async operations for non-blocking I/O
- Implement circuit breakers for Redis failures
- Cache frequently accessed data with longer TTL

## Migration Guide

### From No Cache to Redis Cache

1. **Install Dependencies**
   ```bash
   pip install redis fakeredis
   ```

2. **Update Configuration**
   ```python
   # Add Redis settings to config.py
   REDIS_URL = "redis://localhost:6379/0"
   ```

3. **Enable Caching**
   ```python
   # Update cache_service to use real Redis
   cache_service = SimpleCacheService(use_fake_redis=False)
   ```

4. **Test Integration**
   ```bash
   python verify_cache.py
   ```

### From JWT-only to Mixed Auth

1. **Add Session Middleware**
   ```python
   app.add_middleware(SessionMiddleware)
   ```

2. **Update Authentication**
   ```python
   # Use mixed authentication
   current_user = Depends(mixed_auth)
   ```

3. **Test Session Flow**
   ```bash
   # Test session-based authentication
   curl -X POST /api/auth/login -H "X-Session-ID: session123"
   ```