#!/usr/bin/env python3
"""Verify service is running and test all endpoints."""
import httpx
import time
import sys

BASE = "http://127.0.0.1:8000"

print("=" * 70)
print("Service Verification")
print("=" * 70)

# Wait for server
print("\nWaiting for server to start...")
for i in range(15):
    try:
        r = httpx.get(f"{BASE}/health", timeout=2)
        if r.status_code == 200:
            print(f"✓ Server is running! (attempt {i+1})")
            break
    except:
        time.sleep(1)
        if i < 14:
            print(f"  Waiting... ({i+1}/15)")
else:
    print("✗ Server did not start in time")
    print("\nPlease start the server manually:")
    print("  python start_server.py")
    print("  or")
    print("  uvicorn app.main:app --reload")
    sys.exit(1)

# Test endpoints
print("\n" + "=" * 70)
print("Testing Endpoints")
print("=" * 70)

endpoints = [
    ("/", "Root Endpoint"),
    ("/health", "Health Check"),
    ("/api/v1/", "API v1 Root"),
    ("/api/v1/ping", "Ping Endpoint"),
]

results = []
for path, name in endpoints:
    try:
        r = httpx.get(f"{BASE}{path}", timeout=5)
        status = "✓" if r.status_code == 200 else "✗"
        print(f"{status} {name:20} {path:20} [{r.status_code}]")
        try:
            data = r.json()
            if isinstance(data, dict) and len(str(data)) < 100:
                print(f"    {data}")
            else:
                print(f"    {str(data)[:80]}...")
        except:
            pass
        results.append(r.status_code == 200)
    except Exception as e:
        print(f"✗ {name:20} {path:20} Error: {e}")
        results.append(False)

print("\n" + "=" * 70)
passed = sum(results)
total = len(results)
print(f"Results: {passed}/{total} endpoints passed")

if passed == total:
    print("✓ All endpoints are working correctly!")
    print("\nService is ready to use!")
    print(f"  - API Docs: {BASE}/docs")
    print(f"  - Health: {BASE}/health")
    print(f"  - Ping: {BASE}/api/v1/ping")
else:
    print("✗ Some endpoints failed")
    sys.exit(1)

