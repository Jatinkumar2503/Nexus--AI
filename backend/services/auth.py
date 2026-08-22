"""Environment-configured dispatcher authentication for protected operations."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from fastapi import Depends, Header, HTTPException


@dataclass(frozen=True)
class DispatcherIdentity:
    id: str
    role: str


def require_dispatcher(authorization: str | None = Header(default=None)) -> DispatcherIdentity:
    """Require a bearer token when NEXUS_AUTH_REQUIRED is enabled.

    Local development remains explicit in audit events as ``local-dispatcher``;
    production must set NEXUS_AUTH_REQUIRED=true and NEXUS_DISPATCHER_TOKEN.
    """
    if os.getenv("NEXUS_AUTH_REQUIRED", "false").lower() != "true":
        return DispatcherIdentity("local-dispatcher", "dispatcher")
    configured_token = os.getenv("NEXUS_DISPATCHER_TOKEN")
    if not configured_token:
        raise HTTPException(status_code=503, detail="Dispatcher authentication is not configured.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required.")
    if not secrets.compare_digest(authorization.removeprefix("Bearer "), configured_token):
        raise HTTPException(status_code=403, detail="Invalid dispatcher token.")
    return DispatcherIdentity(os.getenv("NEXUS_DISPATCHER_ID", "dispatcher"), "dispatcher")


def require_role(*roles: str):
    """Return a dependency that enforces an environment-backed operator role."""
    def dependency(identity: DispatcherIdentity = Depends(require_dispatcher)) -> DispatcherIdentity:
        configured_role = os.getenv("NEXUS_DISPATCHER_ROLE", identity.role)
        if configured_role not in roles:
            raise HTTPException(status_code=403, detail="Operator role is not authorized for this action.")
        return DispatcherIdentity(identity.id, configured_role)
    return dependency
