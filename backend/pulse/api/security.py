"""Lightweight deployment-boundary security controls for PULSE REST API."""
from __future__ import annotations

import secrets
from fastapi import HTTPException, Request

from pulse.config import get_settings


def require_control_api_key(request: Request) -> None:
    """Enforce X-PULSE-API-Key / Bearer token on mutating control endpoints when configured.

    When Settings.control_api_key is empty (default local research workstation mode),
    requests pass through without friction. When set (e.g., controlled shared demo),
    control routes reject unauthenticated callers with HTTP 401.
    """
    expected = (get_settings().control_api_key or "").strip()
    if not expected:
        return

    provided = request.headers.get("X-PULSE-API-Key", "").strip()
    if not provided:
        auth = request.headers.get("Authorization", "").strip()
        if auth.lower().startswith("bearer "):
            provided = auth[7:].strip()

    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Unauthorized: valid PULSE control API key required")
