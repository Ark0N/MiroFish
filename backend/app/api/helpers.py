"""
Shared API helper functions for request validation and response formatting.
"""

from flask import jsonify

from ..config import Config
from ..utils.validation import validate_safe_id


def validate_id_param(value, param_name):
    """Validate an ID parameter (from path or JSON body).

    Checks that *value* is non-empty and passes ``validate_safe_id``.
    Returns a ``(response, status_code)`` error tuple on failure, or
    ``None`` when the value is valid.
    """
    if not value:
        return jsonify({"success": False, "error": f"请提供 {param_name}"}), 400
    try:
        validate_safe_id(value, param_name)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return None


def error_response(message, status_code=400):
    """Return a standardised JSON error response tuple."""
    return jsonify({"success": False, "error": message}), status_code


def success_response(data=None, message=None):
    """Return a standardised JSON success response.

    *data* and *message* are both optional; whichever is supplied will
    be included in the response body.
    """
    body = {"success": True}
    if data is not None:
        body["data"] = data
    if message is not None:
        body["message"] = message
    return jsonify(body)


def require_neo4j():
    """Check that ``NEO4J_URI`` is configured.

    Returns a 500 error response tuple when the setting is missing, or
    ``None`` when the configuration is present.
    """
    if not Config.NEO4J_URI:
        return error_response("NEO4J_URI未配置", 500)
    return None
