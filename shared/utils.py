"""Shared utilities for all agents."""

import json
import httpx
from typing import Any


def format_json_response(data: dict[str, Any]) -> str:
    """Format a dictionary as a JSON string for MCP tool responses."""
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def handle_api_error(e: Exception) -> str:
    """Consistent error formatting across all agents."""
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        error_map = {
            401: "Authentication failed. Check your API key.",
            403: "Permission denied. You don't have access to this resource.",
            404: "Resource not found. Check the identifier.",
            429: "Rate limit exceeded. Wait before retrying.",
        }
        message = error_map.get(status, f"API request failed with status {status}")
        return format_json_response({"error": message, "status_code": status})

    if isinstance(e, httpx.TimeoutException):
        return format_json_response({"error": "Request timed out. Try again."})

    if isinstance(e, httpx.ConnectError):
        return format_json_response({"error": "Could not connect to the API. Check network."})

    return format_json_response({"error": f"Unexpected error: {type(e).__name__}: {str(e)}"})
