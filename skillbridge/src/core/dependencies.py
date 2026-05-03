# src/core/dependencies.py
#
# PURPOSE: Reusable FastAPI dependencies for authentication and authorization.
#
# How FastAPI dependencies work:
#   - A dependency is just a function that a route declares with Depends(...)
#   - FastAPI calls it before the route handler, passes the result in
#   - If the dependency raises HTTPException, the route never runs
#
# This file provides:
#   get_current_user  — decodes the Bearer JWT, returns the User ORM object
#   require_roles     — factory that returns a dependency enforcing role(s)
#   get_monitoring_user — validates the scoped monitoring token specifically

from typing import List

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from src.core.security import decode_token
from src.db.database import get_db
from src.models.models import User

# HTTPBearer extracts the "Bearer <token>" header automatically.
# auto_error=True means it raises 403 if the header is missing entirely.
# We set auto_error=False so we can return 401 (more semantically correct).
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Core authentication dependency.

    1. Checks the Authorization: Bearer <token> header exists.
    2. Decodes and verifies the JWT (signature + expiry).
    3. Looks up the user in the database.
    4. Returns the User ORM object.

    Raises 401 on any failure so the route handler only runs for authenticated users.
    """
    # If no Authorization header was sent at all
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Include 'Authorization: Bearer <token>' header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = decode_token(token)
    except JWTError:
        # Covers: signature mismatch, expired token, malformed token
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # JWT "sub" (subject) holds the user id as a string (JWT spec)
    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(status_code=401, detail="Token missing subject claim.")

    user = db.query(User).filter(User.id == int(user_id_str)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found.")

    return user


def require_roles(*allowed_roles: str):
    """
    Factory function: returns a FastAPI dependency that enforces role(s).

    Usage in a route:
        @router.post("/sessions")
        def create_session(
            current_user: User = Depends(require_roles("trainer", "institution")),
            ...
        ):

    If the current user's role is not in allowed_roles, raises 403 Forbidden.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {list(allowed_roles)}. "
                       f"Your role: {current_user.role}",
            )
        return current_user

    return role_checker


def get_monitoring_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Special dependency for /monitoring/* endpoints.
    Validates the SHORT-LIVED SCOPED monitoring token (not the normal access token).

    Key differences from get_current_user:
      - Checks payload["type"] == "monitoring"
      - Checks payload["role"] == "monitoring_officer"
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Monitoring endpoint requires a scoped monitoring token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired monitoring token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # CRITICAL: reject if this is a normal access token (not the scoped one)
    if payload.get("type") != "monitoring":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This endpoint requires a monitoring-scoped token. "
                   "Use POST /auth/monitoring-token to obtain one.",
        )

    if payload.get("role") != "monitoring_officer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token was not issued for monitoring_officer role.",
        )

    user_id_str = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id_str)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found.")

    return user
