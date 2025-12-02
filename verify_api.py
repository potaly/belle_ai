#!/usr/bin/env python3
"""Verify API endpoints are working."""
import httpx
import sys
import time

BASE_URL = "http://127.0.0.1:8000"

def test_endpoint(path, expected_status=200):
    """Test an API endpoint."""
    try:
        response = httpx.get(f"{BASE_URL}{path}", timeout=5)
        if response.status_code == expected_status:
            print(f"✓ {path} - Status: {response.status_code}")
            try:
                data = response.json()
                print(f"  Response: {data}")
            except:
                print(f"  Response: {response.text[:100]}")
            return True
        else:
            print(f"✗ {path} - Expected {expected_status}, got {response.status_code}")
            return False
    except httpx.ConnectError:
        print(f"✗ {path} - Cannot connect to server. Is it running?")
        return False
    except Exception as e:
        print(f"✗ {path} - Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("API Endpoint Verification")
    print("=" * 60)
    print(f"\nTesting endpoints on {BASE_URL}...\n")
    
    results = []
    results.append(("Root endpoint", test_endpoint("/")))
    results.append(("Health check", test_endpoint("/health")))
    results.append(("API v1 root", test_endpoint("/api/v1/")))
    results.append(("Ping endpoint", test_endpoint("/api/v1/ping")))
    
    print("\n" + "=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"Results: {passed}/{total} endpoints passed")
    
    if passed == total:
        print("✓ All endpoints are working!")
        sys.exit(0)
    else:
        print("✗ Some endpoints failed")
        sys.exit(1)

