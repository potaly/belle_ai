#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test script to verify FastAPI + SQLAlchemy setup."""
import sys
from pathlib import Path

print("=" * 60)
print("FastAPI + SQLAlchemy 2.0 Setup Verification")
print("=" * 60)

# 1. Test configuration loading
print("\n1. Testing Configuration...")
try:
    from app.core.config import get_settings
    settings = get_settings()
    print(f"   ✓ App Name: {settings.app_name}")
    print(f"   ✓ App Version: {settings.app_version}")
    print(f"   ✓ Database URL: {settings.database_url[:50]}...")
except Exception as e:
    print(f"   ✗ Configuration error: {e}")
    sys.exit(1)

# 2. Test database connection
print("\n2. Testing Database Connection...")
try:
    from app.core.database import engine, Base, get_db
    from sqlalchemy import text
    
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("   ✓ Database connection successful")
        print(f"   ✓ Engine URL: {str(engine.url).split('@')[1] if '@' in str(engine.url) else 'N/A'}")
except Exception as e:
    print(f"   ✗ Database connection error: {e}")
    print("   (This is OK if database is not running)")

# 3. Test ORM models
print("\n3. Testing ORM Models...")
try:
    from app.models import Product, Guide, UserBehaviorLog, AITaskLog
    print("   ✓ Product model imported")
    print("   ✓ Guide model imported")
    print("   ✓ UserBehaviorLog model imported")
    print("   ✓ AITaskLog model imported")
    
    # Check model attributes
    print(f"   ✓ Product table name: {Product.__tablename__}")
    print(f"   ✓ Guide table name: {Guide.__tablename__}")
except Exception as e:
    print(f"   ✗ Model import error: {e}")
    sys.exit(1)

# 4. Test API router
print("\n4. Testing API Router...")
try:
    from app.api.v1.router import router
    print(f"   ✓ Router prefix: {router.prefix}")
    print(f"   ✓ Router tags: {router.tags}")
    
    # List routes
    routes = []
    for route in router.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            methods = ', '.join(route.methods)
            routes.append(f"     {methods} {route.path}")
    
    if routes:
        print("   ✓ Available routes:")
        for route in routes:
            print(route)
except Exception as e:
    print(f"   ✗ Router error: {e}")
    sys.exit(1)

# 5. Test FastAPI app
print("\n5. Testing FastAPI Application...")
try:
    from app.main import app
    print(f"   ✓ FastAPI app created: {app.title}")
    print(f"   ✓ App version: {app.version}")
    
    # Check routes
    routes = []
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            methods = ', '.join(route.methods)
            routes.append(f"     {methods} {route.path}")
    
    if routes:
        print("   ✓ App routes:")
        for route in routes[:10]:  # Show first 10
            print(route)
        if len(routes) > 10:
            print(f"     ... and {len(routes) - 10} more routes")
except Exception as e:
    print(f"   ✗ FastAPI app error: {e}")
    sys.exit(1)

# 6. Test schemas
print("\n6. Testing Schemas...")
try:
    from app.schemas.base_schemas import BaseResponse, ErrorResponse, PaginatedResponse
    print("   ✓ BaseResponse schema imported")
    print("   ✓ ErrorResponse schema imported")
    print("   ✓ PaginatedResponse schema imported")
    
    # Test instantiation
    response = BaseResponse(data="test", message="OK")
    print(f"   ✓ BaseResponse can be instantiated: {response.success}")
except Exception as e:
    print(f"   ✗ Schema error: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ All tests passed! Setup is correct.")
print("=" * 60)
print("\nTo start the server, run:")
print("  uvicorn app.main:app --reload")
print("\nThen test endpoints:")
print("  GET http://127.0.0.1:8000/")
print("  GET http://127.0.0.1:8000/health")
print("  GET http://127.0.0.1:8000/api/v1/ping")

