#!/usr/bin/env python3
"""Test the copy generation endpoint."""
import sys

print("Testing copy endpoint setup...")

try:
    from app.main import app
    print("✓ App imported")
    
    routes = [r.path for r in app.routes if hasattr(r, 'path')]
    print(f"✓ Total routes: {len(routes)}")
    
    copy_routes = [r for r in routes if '/ai' in r or '/copy' in r]
    if copy_routes:
        print("✓ Copy routes found:")
        for r in copy_routes:
            print(f"    {r}")
    else:
        print("✗ Copy routes not found")
        sys.exit(1)
        
    from app.api.v1.copy import router
    print("✓ Copy router imported")
    
    from app.services.copy_service import generate_copy_stream
    print("✓ Copy service imported")
    
    from app.services.streaming_generator import StreamingGenerator
    print("✓ Streaming generator imported")
    
    from app.repositories.product_repository import get_product_by_sku
    print("✓ Product repository imported")
    
    from app.services.log_service import log_ai_task
    print("✓ Log service imported")
    
    print("\n✓ All components loaded successfully!")
    print("\nEndpoint: POST /ai/generate/copy")
    print("Expected: StreamingResponse with SSE format")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

