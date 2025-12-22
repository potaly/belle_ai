"""Pytest configuration for test suite."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to Python path
# This ensures 'app' module can be imported in tests
project_root = Path(__file__).parent.parent.resolve()
project_root_str = str(project_root)

# Add to sys.path if not already there
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

# Also set PYTHONPATH environment variable for subprocesses
os.environ.setdefault("PYTHONPATH", project_root_str)

