#!/usr/bin/env python3
"""Test if app can be imported without errors."""
import sys

try:
    from app.main import app
    print("✓ App imported successfully")
    print(f"✓ Routes: {len(app.routes)}")
    
    # Check for copy endpoint
    routes = [r.path for r in app.routes if hasattr(r, 'path')]
    copy_routes = [r for r in routes if '/ai' in r or '/copy' in r]
    if copy_routes:
        print("✓ Copy routes found:")
        for r in copy_routes:
            print(f"    {r}")
    
    print("\n✓ All imports successful!")
    sys.exit(0)
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

