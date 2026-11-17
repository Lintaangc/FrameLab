"""Small helpers shared by routes and services."""
import json
import re


class ApiError(Exception):
    """An error that is safe to show to the user; converted to JSON by the app."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


_ID_RE = re.compile(r"^[a-f0-9]{32}$")


def require_id(value):
    """Ids are uuid4 hex strings. Validating them also blocks path traversal."""
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise ApiError("Missing or invalid id.", 400)
    return value


def parse_params(raw):
    """Accept a dict, a JSON string, or nothing; always return a dict."""
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        raise ApiError("Parameters must be valid JSON.", 400)
    if not isinstance(data, dict):
        raise ApiError("Parameters must be a JSON object.", 400)
    return data
