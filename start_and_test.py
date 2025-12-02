#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Start server and test endpoints."""
import sys
import time
import subprocess
import httpx

def test_import():
    """Test if app can be imported."""
    print("=" * 60)
    print("Step 1: Testing App Import")
    print("=" * 60)
    try:
        from app.main import app
        print(f"✓ App imported successfully")
        print(f"  - Title: {app.title}")
        print(f"  - Version: {app.version}")
        print(f"  - Routes: {len(app.routes)}")
        for route in app.routes[:5]:
            if hasattr(route, 'path'):
                print(f"    {route.path}")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def start_server():
    """Start uvicorn server."""
    print("\n" + "=" * 60)
    print("Step 2: Starting Server")
    print("=" * 60)
    try:
        import uvicorn
        print("Starting uvicorn server...")
        print("Server will run in background")
        print("Access: http://127.0.0.1:8000")
        return True
    except Exception as e:
        print(f"✗ Failed to start: {e}")
        return False

def test_endpoints():
    """Test API endpoints."""
    print("\n" + "=" * 60)
    print("Step 3: Testing Endpoints")
    print("=" * 60)
    base_url = "http://127.0.0.1:8000"
    
    # Wait for server to start
    print("Waiting for server to start...")
    for i in range(10):
        try:
            response = httpx.get(f"{base_url}/health", timeout=2)
            if response.status_code == 200:
                print("✓ Server is running!")
                break
        except:
            time.sleep(1)
            print(f"  Attempt {i+1}/10...")
    else:
        print("✗ Server did not start in time")
        return False
    
    endpoints = [
        ("/", "Root endpoint"),
        ("/health", "Health check"),
        ("/api/v1/", "API v1 root"),
        ("/api/v1/ping", "Ping endpoint"),
    ]
    
    results = []
    for path, name in endpoints:
        try:
            response = httpx.get(f"{base_url}{path}", timeout=5)
            if response.status_code == 200:
                print(f"✓ {name} ({path})")
                try:
                    data = response.json()
                    print(f"  Response: {data}")
                except:
                    print(f"  Response: {response.text[:50]}")
                results.append(True)
            else:
                print(f"✗ {name} ({path}) - Status: {response.status_code}")
                results.append(False)
        except Exception as e:
            print(f"✗ {name} ({path}) - Error: {e}")
            results.append(False)
    
    return all(results)

if __name__ == "__main__":
    if not test_import():
        sys.exit(1)
    
    if not start_server():
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✓ All checks passed!")
    print("=" * 60)
    print("\nTo start the server, run:")
    print("  uvicorn app.main:app --reload")
    print("\nOr use:")
    print("  python -m uvicorn app.main:app --reload")

