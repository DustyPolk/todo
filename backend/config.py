from decouple import config
from datetime import timedelta

# JWT Configuration
SECRET_KEY = config("SECRET_KEY", default="your-super-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Security Configuration
BCRYPT_ROUNDS = 12
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30

# Token expiration settings
ACCESS_TOKEN_EXPIRE_DELTA = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
REFRESH_TOKEN_EXPIRE_DELTA = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
LOCKOUT_DURATION_DELTA = timedelta(minutes=LOCKOUT_DURATION_MINUTES)

# CORS settings
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:80",
    "http://127.0.0.1:80"
]

# Database settings
DATABASE_URL = config("DATABASE_URL", default="sqlite:///./todos.db")

# API Security settings
API_KEY_PREFIX = "todo_"
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
CSRF_SECRET_KEY = config("CSRF_SECRET_KEY", default="csrf-secret-key-change-in-production")

# Rate limiting settings (requests per time period)
RATE_LIMIT_AUTH = "5/minute"  # Authentication endpoints
RATE_LIMIT_API = "100/minute"  # General API endpoints  
RATE_LIMIT_PUBLIC = "1000/hour"  # Public endpoints

# Security monitoring
SECURITY_EVENT_RETENTION_HOURS = 168  # 7 days
MAX_FAILED_ATTEMPTS_PER_IP = 10
IP_BLOCK_DURATION_MINUTES = 60

# OAuth2 Configuration
GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", default="")
GITHUB_CLIENT_ID = config("GITHUB_CLIENT_ID", default="")
GITHUB_CLIENT_SECRET = config("GITHUB_CLIENT_SECRET", default="")

# OAuth2 URLs
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid_configuration"
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

# OAuth2 Redirect URIs (adjust for your domain)
BASE_URL = config("BASE_URL", default="http://localhost:8000")
GOOGLE_REDIRECT_URI = f"{BASE_URL}/api/auth/oauth/google/callback"
GITHUB_REDIRECT_URI = f"{BASE_URL}/api/auth/oauth/github/callback"

# OAuth2 State signing key
OAUTH_STATE_SECRET = config("OAUTH_STATE_SECRET", default="oauth-state-secret-change-in-production")

# Redis Configuration
REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")
REDIS_HOST = config("REDIS_HOST", default="localhost")
REDIS_PORT = int(config("REDIS_PORT", default="6379"))
REDIS_DB = int(config("REDIS_DB", default="0"))
REDIS_PASSWORD = config("REDIS_PASSWORD", default=None)
REDIS_SSL = config("REDIS_SSL", default="false").lower() == "true"

# Cache Configuration
CACHE_DEFAULT_TTL = int(config("CACHE_DEFAULT_TTL", default="300"))  # 5 minutes
CACHE_LONG_TTL = int(config("CACHE_LONG_TTL", default="3600"))  # 1 hour
CACHE_SHORT_TTL = int(config("CACHE_SHORT_TTL", default="60"))  # 1 minute

# Session Configuration
SESSION_TTL = int(config("SESSION_TTL", default="86400"))  # 24 hours
SESSION_CLEANUP_INTERVAL = int(config("SESSION_CLEANUP_INTERVAL", default="3600"))  # 1 hour

# Rate Limiting Storage
RATE_LIMIT_STORAGE_URL = config("RATE_LIMIT_STORAGE_URL", default=REDIS_URL)

# Cache Keys Prefixes
CACHE_PREFIX = "todo_cache:"
SESSION_PREFIX = "todo_session:"
RATE_LIMIT_PREFIX = "todo_ratelimit:"
USER_CACHE_PREFIX = "todo_user:"
TASK_CACHE_PREFIX = "todo_task:"