"""
Input validation utility.
"""

import re


def validate_safe_id(value: str, param_name: str = "id") -> str:
    """Validate that an ID parameter is safe (no path traversal).
    Returns the validated value or raises ValueError."""
    if not value or not isinstance(value, str):
        raise ValueError(f"Invalid {param_name}: must be a non-empty string")
    if ".." in value or "/" in value or "\\" in value:
        raise ValueError(f"Invalid {param_name}: contains illegal characters")
    if not re.match(r'^[a-zA-Z0-9_-]+$', value):
        raise ValueError(f"Invalid {param_name}: must contain only alphanumeric, dash, or underscore")
    if len(value) > 100:
        raise ValueError(f"Invalid {param_name}: too long")
    return value
