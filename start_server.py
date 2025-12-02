#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Start the FastAPI server with error handling."""
import sys
import traceback

print("=" * 70)
print("Starting FastAPI Server")
print("=" * 70)

# Step 1: Test imports
print("\n[1/3] Testing imports...")
try:
    from app.main import app
    print(f"✓ App imported: {app.title} v{app.version}")
    print(f"✓ Routes registered: {len(app.routes)}")
except Exception as e:
    print(f"✗ Import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

# Step 2: Test database connection (optional)
print("\n[2/3] Testing database connection...")
try:
    from app.core.database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("✓ Database connection OK")
except Exception as e:
    print(f"⚠ Database connection failed (this is OK if DB is not running): {e}")

# Step 3: Start server
print("\n[3/3] Starting server...")
print("=" * 70)
print("Server starting at: http://127.0.0.1:8000")
print("API Documentation: http://127.0.0.1:8000/docs")
print("=" * 70)
print("\nPress Ctrl+C to stop the server\n")

try:
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
except KeyboardInterrupt:
    print("\n\nServer stopped by user")
except Exception as e:
    print(f"\n✗ Server failed to start: {e}")
    traceback.print_exc()
    sys.exit(1)

