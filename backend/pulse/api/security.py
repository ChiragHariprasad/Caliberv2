"""Lightweight deployment-boundary security controls for PULSE REST API."""
from __future__ import annotations

import secrets
from fastapi import HTTPException, Request

from pulse.config import get_settings


def require_control_api_key(request: Request) -> None:
    """Enforce X-PULSE-API-Key / Bearer token on mutating control endpoints when configured.

    When authentication is required (non-local env, non-loopback host, or
    Settings.require_control_auth=True), requests fail closed unless a key is configured
    and matched. In default local loopback development mode with no key set, requests
    pass through without friction.
    """
    settings = get_settings()
    expected = (settings.control_api_key or "").strip()
    if not expected:
        if settings.requires_control_auth:
            raise HTTPException(
                status_code=503,
                detail="Control plane unavailable: authentication required but no control API key is configured",
            )
        return

    provided = request.headers.get("X-PULSE-API-Key", "").strip()
    if not provided:
        auth = request.headers.get("Authorization", "").strip()
        if auth.lower().startswith("bearer "):
            provided = auth[7:].strip()

    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Unauthorized: valid PULSE control API key required")
