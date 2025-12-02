import sys
print("Testing imports...", flush=True)

try:
    print("1. Importing config...", flush=True)
    from app.core.config import get_settings
    settings = get_settings()
    print(f"   OK - App: {settings.app_name}", flush=True)
except Exception as e:
    print(f"   FAILED: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("2. Importing database...", flush=True)
    from app.core.database import engine, get_db
    print("   OK", flush=True)
except Exception as e:
    print(f"   FAILED: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("3. Importing models...", flush=True)
    from app.models import Product, Guide, UserBehaviorLog, AITaskLog
    print("   OK", flush=True)
except Exception as e:
    print(f"   FAILED: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("4. Importing router...", flush=True)
    from app.api.v1.router import router
    print(f"   OK - Prefix: {router.prefix}", flush=True)
except Exception as e:
    print(f"   FAILED: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("5. Importing main app...", flush=True)
    from app.main import app
    print(f"   OK - Title: {app.title}", flush=True)
    print(f"   Routes: {len(app.routes)}", flush=True)
except Exception as e:
    print(f"   FAILED: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nAll imports successful! Starting server...", flush=True)
print("Server will be available at http://127.0.0.1:8000", flush=True)

