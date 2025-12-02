#!/usr/bin/env python3
"""Test if service is running and all endpoints work."""
import httpx
import time
import json

BASE = "http://127.0.0.1:8000"

print("=" * 70)
print("Service Verification")
print("=" * 70)

# Wait for server
print("\nWaiting for server...")
for i in range(15):
    try:
        r = httpx.get(f"{BASE}/health", timeout=2)
        if r.status_code == 200:
            print(f"✓ Server is running! (attempt {i+1})")
            break
    except:
        time.sleep(1)
        if i < 14:
            print(f"  Attempt {i+1}/15...")
else:
    print("✗ Server did not start")
    exit(1)

# Test endpoints
print("\n" + "=" * 70)
print("Testing Endpoints")
print("=" * 70)

endpoints = [
    ("/", "Root"),
    ("/health", "Health"),
    ("/api/v1/", "API v1"),
    ("/api/v1/ping", "Ping"),
]

all_ok = True
for path, name in endpoints:
    try:
        r = httpx.get(f"{BASE}{path}", timeout=5)
        if r.status_code == 200:
            print(f"\n✓ {name} ({path})")
            data = r.json()
            print(f"  Response: {json.dumps(data, ensure_ascii=False, indent=2)}")
        else:
            print(f"\n✗ {name} ({path}) - Status: {r.status_code}")
            all_ok = False
    except Exception as e:
        print(f"\n✗ {name} ({path}) - Error: {e}")
        all_ok = False

print("\n" + "=" * 70)
if all_ok:
    print("✓ All endpoints working correctly!")
    print(f"\nService is ready at: {BASE}")
    print(f"API Docs: {BASE}/docs")
else:
    print("✗ Some endpoints failed")
    exit(1)

