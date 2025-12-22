"""JSON utilities for stable serialization."""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any


def stable_json_dumps(obj: Any, **kwargs: Any) -> str:
    """
    Stable JSON serialization with deterministic ordering.
    
    Rules:
    - Dictionary keys are sorted
    - List items are deduplicated and sorted (if comparable)
    - Decimal/float are converted to string (to avoid float precision issues)
    - None values are preserved
    
    Args:
        obj: Object to serialize
        **kwargs: Additional arguments passed to json.dumps
        
    Returns:
        JSON string with stable ordering
    """
    normalized = _normalize_for_json(obj)
    return json.dumps(normalized, ensure_ascii=False, **kwargs)


def _normalize_for_json(obj: Any) -> Any:
    """
    Normalize object for stable JSON serialization.
    
    Args:
        obj: Object to normalize
        
    Returns:
        Normalized object
    """
    if obj is None:
        return None
    
    # Handle Decimal: convert to string to avoid float precision issues
    if isinstance(obj, Decimal):
        return str(obj)
    
    # Handle float: convert to string (per requirement: 禁 float)
    if isinstance(obj, float):
        return str(obj)
    
    # Handle Mapping (dict): sort keys
    if isinstance(obj, Mapping):
        return {
            str(k): _normalize_for_json(v)
            for k, v in sorted(obj.items(), key=lambda x: str(x[0]))
        }
    
    # Handle Sequence (list, tuple): deduplicate and sort if comparable
    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
        normalized_list = [_normalize_for_json(item) for item in obj]
        
        # Deduplicate: remove duplicates while preserving order for non-hashable items
        seen = set()
        deduplicated = []
        for item in normalized_list:
            # For hashable items, use set for deduplication
            if isinstance(item, (str, int, float, bool, type(None))):
                if item not in seen:
                    seen.add(item)
                    deduplicated.append(item)
            else:
                # For non-hashable items (dict, list), use string representation
                item_str = json.dumps(item, sort_keys=True, ensure_ascii=False)
                if item_str not in seen:
                    seen.add(item_str)
                    deduplicated.append(item)
        
        # Sort if all items are comparable
        try:
            return sorted(deduplicated, key=lambda x: (
                str(x) if not isinstance(x, (str, int, float, bool, type(None))) else x
            ))
        except TypeError:
            # If sorting fails (mixed types), return deduplicated list as-is
            return deduplicated
    
    # Handle other types: return as-is
    return obj

