#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Automatically start server and verify all endpoints."""
import subprocess
import time
import httpx
import json
import sys
import signal
import os

BASE_URL = "http://127.0.0.1:8000"
process = None

def cleanup():
    """Cleanup on exit."""
    global process
    if process:
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            try:
                process.kill()
            except:
                pass

def signal_handler(sig, frame):
    """Handle Ctrl+C."""
    print("\n\nStopping server...")
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

print("=" * 70)
print("Auto Start and Verify Service")
print("=" * 70)

# Step 1: Test imports
print("\n[1/4] Testing imports...")
try:
    from app.main import app
    print(f"✓ App imported: {app.title} v{app.version}")
    print(f"✓ Routes: {len(app.routes)}")
except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 2: Start server
print("\n[2/4] Starting server...")
try:
    process = subprocess.Popen(
        ["python", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    print("✓ Server process started (PID: {})".format(process.pid))
except Exception as e:
    print(f"✗ Failed to start server: {e}")
    sys.exit(1)

# Step 3: Wait for server to be ready
print("\n[3/4] Waiting for server to start...")
for i in range(20):
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            print(f"✓ Server is ready! (attempt {i+1})")
            break
    except:
        time.sleep(1)
        if i < 19:
            print(f"  Waiting... ({i+1}/20)")
else:
    print("✗ Server did not start in time")
    cleanup()
    sys.exit(1)

# Step 4: Test all endpoints
print("\n[4/4] Testing endpoints...")
print("=" * 70)

endpoints = [
    ("/", "Root Endpoint"),
    ("/health", "Health Check"),
    ("/api/v1/", "API v1 Root"),
    ("/api/v1/ping", "Ping Endpoint"),
]

all_ok = True
for path, name in endpoints:
    try:
        response = httpx.get(f"{BASE_URL}{path}", timeout=5)
        if response.status_code == 200:
            print(f"\n✓ {name:20} {path:20}")
            try:
                data = response.json()
                print(f"  {json.dumps(data, ensure_ascii=False, indent=2)}")
            except:
                print(f"  {response.text[:100]}")
        else:
            print(f"\n✗ {name:20} {path:20} - Status: {response.status_code}")
            all_ok = False
    except Exception as e:
        print(f"\n✗ {name:20} {path:20} - Error: {e}")
        all_ok = False

print("\n" + "=" * 70)
if all_ok:
    print("✓ All endpoints working correctly!")
    print(f"\nService is running at: {BASE_URL}")
    print(f"API Documentation: {BASE_URL}/docs")
    print("\nServer is running in background.")
    print("Press Ctrl+C to stop.")
    
    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping server...")
        cleanup()
else:
    print("✗ Some endpoints failed")
    cleanup()
    sys.exit(1)

