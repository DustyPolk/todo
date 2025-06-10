#!/usr/bin/env python3
import requests
import json

# Test login
login_data = {
    "username": "admin",
    "password": "Admin123!@#$"
}

response = requests.post(
    "http://localhost:8000/api/auth/login",
    json=login_data
)

print(f"Status Code: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

if response.status_code == 200:
    tokens = response.json()
    print(f"\nAccess Token: {tokens['access_token'][:50]}...")
    print(f"Refresh Token: {tokens['refresh_token']}")
    
    # Test authenticated endpoint
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me_response = requests.get("http://localhost:8000/api/auth/me", headers=headers)
    print(f"\nCurrent User: {json.dumps(me_response.json(), indent=2)}")