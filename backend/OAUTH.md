# OAuth2 Integration Documentation

## Overview

The Todo API supports OAuth2 authentication with Google and GitHub providers, allowing users to sign in using their existing accounts from these platforms.

## Features

### OAuth2 Providers
- **Google OAuth2** - Sign in with Google accounts
- **GitHub OAuth2** - Sign in with GitHub accounts
- **Account Linking** - Link multiple OAuth accounts to a single user account
- **Fallback Authentication** - Users can still use traditional email/password authentication

### Security Features
- **State Parameter Validation** - Prevents CSRF attacks during OAuth flow
- **Token Encryption** - OAuth tokens are securely stored
- **Account Isolation** - Users can only access their own linked accounts
- **Secure Account Linking** - Temporary tokens for linking accounts
- **Account Lockout Prevention** - Users cannot unlink their last authentication method

## Setup Instructions

### 1. Google OAuth2 Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google+ API
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client IDs"
5. Set application type to "Web application"
6. Add authorized redirect URIs:
   - `http://localhost:8000/api/auth/oauth/google/callback` (development)
   - `https://yourdomain.com/api/auth/oauth/google/callback` (production)
7. Copy the Client ID and Client Secret

### 2. GitHub OAuth2 Setup

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click "New OAuth App"
3. Fill in the application details:
   - **Application name**: Your Todo App
   - **Homepage URL**: `http://localhost:8000` (development)
   - **Authorization callback URL**: `http://localhost:8000/api/auth/oauth/github/callback`
4. Register the application
5. Copy the Client ID and Client Secret

### 3. Environment Configuration

Update your `.env` file:

```bash
# Google OAuth2
GOOGLE_CLIENT_ID=your-google-client-id-here
GOOGLE_CLIENT_SECRET=your-google-client-secret-here

# GitHub OAuth2
GITHUB_CLIENT_ID=your-github-client-id-here
GITHUB_CLIENT_SECRET=your-github-client-secret-here

# Base URL for redirects
BASE_URL=http://localhost:8000

# OAuth security keys
OAUTH_STATE_SECRET=your-oauth-state-secret-key
```

## API Endpoints

### Get Available Providers
```http
GET /api/auth/oauth/providers
```

Response:
```json
{
  "providers": [
    {
      "name": "google",
      "display_name": "Google",
      "icon": "google",
      "configured": true
    },
    {
      "name": "github",
      "display_name": "GitHub", 
      "icon": "github",
      "configured": true
    }
  ]
}
```

### Start OAuth Flow
```http
POST /api/auth/oauth/authorize
Content-Type: application/json

{
  "provider": "google"
}
```

Response:
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/auth?...",
  "state": "encoded-state-parameter"
}
```

### OAuth Callback (Automatic)
```http
GET /api/auth/oauth/{provider}/callback?code=auth_code&state=state_param
```

Response:
```json
{
  "message": "OAuth authentication successful",
  "access_token": "jwt-access-token",
  "refresh_token": "jwt-refresh-token",
  "token_type": "bearer"
}
```

### Get Linked Accounts
```http
GET /api/auth/oauth/accounts
Authorization: Bearer your-jwt-token
```

Response:
```json
[
  {
    "provider": "google",
    "provider_user_id": "123456789",
    "email": "user@gmail.com",
    "username": "googleuser",
    "avatar_url": "https://...",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

### Generate Link Token
```http
POST /api/auth/oauth/link-token?provider=github
Authorization: Bearer your-jwt-token
```

Response:
```json
{
  "link_token": "temporary-link-token",
  "expires_in": 300
}
```

### Unlink OAuth Account
```http
DELETE /api/auth/oauth/accounts/{provider}
Authorization: Bearer your-jwt-token
```

Response:
```json
{
  "message": "GitHub account unlinked successfully"
}
```

### Get OAuth User Info
```http
GET /api/auth/oauth/user-info/{provider}
Authorization: Bearer your-jwt-token
```

Response:
```json
{
  "provider": "google",
  "user_info": {
    "id": "123456789",
    "email": "user@gmail.com",
    "name": "User Name",
    "avatar_url": "https://..."
  },
  "linked_at": "2024-01-01T00:00:00Z",
  "last_updated": "2024-01-01T00:00:00Z"
}
```

## Frontend Integration

### JavaScript Example

```javascript
// Start OAuth flow
async function loginWithGoogle() {
  const response = await fetch('/api/auth/oauth/authorize', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ provider: 'google' })
  });
  
  const data = await response.json();
  
  // Redirect user to OAuth provider
  window.location.href = data.authorization_url;
}

// Handle OAuth callback (in your callback page)
async function handleOAuthCallback() {
  const urlParams = new URLSearchParams(window.location.search);
  const code = urlParams.get('code');
  const state = urlParams.get('state');
  const provider = window.location.pathname.split('/').pop().replace('/callback', '');
  
  // The callback is handled server-side, tokens are returned
  // You can extract them from the response or redirect
}

// Link additional OAuth account
async function linkGitHubAccount() {
  // Generate link token
  const tokenResponse = await fetch('/api/auth/oauth/link-token?provider=github', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${yourJwtToken}`
    }
  });
  
  const tokenData = await tokenResponse.json();
  
  // Start OAuth flow with link token
  const authResponse = await fetch('/api/auth/oauth/authorize', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ 
      provider: 'github',
      link_token: tokenData.link_token
    })
  });
  
  const authData = await authResponse.json();
  window.location.href = authData.authorization_url;
}
```

### React Example

```jsx
import { useState, useEffect } from 'react';

function OAuthLogin() {
  const [providers, setProviders] = useState([]);
  const [linkedAccounts, setLinkedAccounts] = useState([]);

  useEffect(() => {
    // Load available providers
    fetch('/api/auth/oauth/providers')
      .then(res => res.json())
      .then(data => setProviders(data.providers));
  }, []);

  const handleOAuthLogin = async (provider) => {
    const response = await fetch('/api/auth/oauth/authorize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider })
    });
    
    const data = await response.json();
    window.location.href = data.authorization_url;
  };

  return (
    <div>
      <h3>Sign in with:</h3>
      {providers.map(provider => (
        <button 
          key={provider.name}
          onClick={() => handleOAuthLogin(provider.name)}
          disabled={!provider.configured}
        >
          Sign in with {provider.display_name}
        </button>
      ))}
    </div>
  );
}
```

## Database Schema

### Users Table Extensions
```sql
ALTER TABLE users ADD COLUMN oauth_provider VARCHAR(50);
ALTER TABLE users ADD COLUMN oauth_id VARCHAR(255);
ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500);
ALTER TABLE users ADD COLUMN provider_data JSON;
```

### OAuth Accounts Table
```sql
CREATE TABLE oauth_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    provider VARCHAR(50) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    username VARCHAR(255),
    avatar_url VARCHAR(500),
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at DATETIME,
    provider_data JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, provider_user_id)
);
```

## Security Considerations

### State Parameter Protection
- State parameters are cryptographically signed
- Include random nonce and timestamp
- Expire after 10 minutes
- Prevent CSRF attacks

### Token Security
- OAuth tokens are stored encrypted
- Access tokens are refreshed when possible
- Tokens are invalidated on account unlinking

### Account Linking Security
- Temporary link tokens expire in 5 minutes
- Link tokens are bound to specific users
- Cannot link already linked accounts
- Prevents account hijacking

### Account Protection
- Users cannot unlink their last authentication method
- Password-less OAuth users must link another account before unlinking
- Failed OAuth attempts are logged for monitoring

## Error Handling

### Common Error Responses

```json
{
  "detail": "OAuth provider not configured"
}
```

```json
{
  "detail": "Invalid or expired state parameter"
}
```

```json
{
  "detail": "Account already linked to Google"
}
```

```json
{
  "detail": "Cannot unlink last authentication method"
}
```

## Testing

### Running OAuth Tests
```bash
python -m pytest test_oauth.py -v
```

### Manual Testing
1. Configure OAuth providers in development
2. Test authorization URL generation
3. Test callback handling with mock responses
4. Test account linking and unlinking
5. Verify security protections

## Production Deployment

### HTTPS Requirements
- OAuth2 requires HTTPS in production
- Update redirect URIs to use HTTPS
- Configure SSL certificates

### Environment Variables
```bash
BASE_URL=https://yourdomain.com
GOOGLE_CLIENT_ID=prod-google-client-id
GOOGLE_CLIENT_SECRET=prod-google-client-secret
GITHUB_CLIENT_ID=prod-github-client-id
GITHUB_CLIENT_SECRET=prod-github-client-secret
```

### Monitoring
- Monitor OAuth login success/failure rates
- Alert on unusual OAuth activity
- Track account linking patterns
- Monitor token refresh rates

## Troubleshooting

### Common Issues

1. **"OAuth provider not configured"**
   - Check environment variables are set
   - Verify client ID and secret are correct

2. **"Invalid redirect URI"**
   - Ensure redirect URI matches exactly in provider settings
   - Check for trailing slashes or protocol mismatches

3. **"Invalid state parameter"**
   - Check system time synchronization
   - Verify state secret key is consistent
   - Ensure state hasn't expired (10 minutes)

4. **Token refresh failures**
   - Check if provider refresh tokens are enabled
   - Verify token storage and encryption
   - Monitor token expiration handling