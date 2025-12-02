#!/usr/bin/env python3
"""Test all API endpoints."""
import httpx
import time
import sys

BASE = "http://127.0.0.1:8000"

def test(path, name):
    """Test a single endpoint."""
    try:
        r = httpx.get(f"{BASE}{path}", timeout=5)
        print(f"✓ {name:20} {path:20} Status: {r.status_code}")
        try:
            data = r.json()
            print(f"  Response: {data}")
        except:
            print(f"  Response: {r.text[:80]}")
        return r.status_code == 200
    except httpx.ConnectError:
        print(f"✗ {name:20} {path:20} Cannot connect (server not running?)")
        return False
    except Exception as e:
        print(f"✗ {name:20} {path:20} Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("Testing API Endpoints")
    print("=" * 70)
    print(f"Base URL: {BASE}\n")
    
    # Wait for server
    print("Waiting for server to start...")
    for i in range(10):
        try:
            httpx.get(f"{BASE}/health", timeout=2)
            print("Server is running!\n")
            break
        except:
            time.sleep(1)
    else:
        print("Server did not start. Please start it manually:")
        print("  uvicorn app.main:app --reload")
        sys.exit(1)
    
    # Test endpoints
    results = []
    results.append(test("/", "Root"))
    results.append(test("/health", "Health"))
    results.append(test("/api/v1/", "API v1 Root"))
    results.append(test("/api/v1/ping", "Ping"))
    
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} endpoints passed")
    
    if passed == total:
        print("✓ All endpoints working!")
    else:
        print("✗ Some endpoints failed")

