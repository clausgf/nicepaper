"""
Authentication glue for running behind an authenticating reverse proxy
(e.g. Caddy with oauth2-proxy). The app itself does not authenticate;
it only reads the identity the proxy forwards in request headers.

This is deliberately a small seam: if a different mechanism is needed
later (API keys for displays, built-in login, ...), replace or extend
the functions here without touching the UI code.
"""
from typing import Optional
from fastapi import Request

from app.config import app_config


def get_username(request: Optional[Request]) -> Optional[str]:
    """
    The username forwarded by the reverse proxy, or None when no
    configured header is present (e.g. in local development).
    """
    if request is None:
        return None
    for header in app_config.auth_user_headers:
        value = request.headers.get(header)
        if value:
            return value
    return None


def get_logout_url() -> Optional[str]:
    """
    The URL that terminates the proxy session, or None if logout is not
    configured.
    """
    return app_config.auth_logout_url
