# src/core/security.py
#
# PURPOSE: All cryptographic operations live here.
# Keeping this in one place means the rest of the app never touches
# raw JWT or bcrypt calls — easier to audit and easier to swap out.

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt               # bcrypt directly — more reliable than passlib wrapper
from jose import JWTError, jwt           # python-jose: JWT encode/decode

from src.core.config import settings

# ---------------------------------------------------------------------------
# PASSWORD HASHING
# ---------------------------------------------------------------------------
# We use bcrypt directly to avoid passlib version compatibility issues.
# bcrypt.hashpw requires bytes input; we encode/decode as needed.

def hash_password(plain_password: str) -> str:
    """Hash a plain-text password with bcrypt. Call this at signup."""
    # gensalt() generates a random salt with default work factor 12
    hashed = _bcrypt.hashpw(plain_password.encode("utf-8"), _bcrypt.gensalt())
    return hashed.decode("utf-8")   # store as string in DB


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plain-text password against a stored bcrypt hash. Call this at login."""
    return _bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# ---------------------------------------------------------------------------
# JWT HELPERS
# ---------------------------------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Mint a signed JWT.

    Parameters
    ----------
    data : dict
        The claims to embed. At minimum should include {"sub": user_id, "role": role}.
    expires_delta : timedelta, optional
        How long until the token expires. Defaults to settings.ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns
    -------
    str
        A signed JWT string like "eyJhbGc..."

    JWT payload structure (standard + custom claims):
        {
            "sub":   "42",              # subject = user id (string, per JWT spec)
            "role":  "trainer",         # our custom claim
            "iat":   1714000000,        # issued-at (added by jose automatically via exp calc)
            "exp":   1714086400,        # expiry timestamp
            "type":  "access"           # optional: "access" | "monitoring" — lets us distinguish
        }
    """
    to_encode = data.copy()

    # Decide expiry
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    # "exp" is a reserved JWT claim — jose will enforce it automatically on decode
    to_encode.update({"exp": expire})

    # jose.jwt.encode signs the payload with our secret key
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_monitoring_token(user_id: int) -> str:
    """
    Mint a short-lived, scoped token for the Monitoring Officer.
    This is the SECOND token the monitoring officer gets after presenting their API key.
    It lives only 1 hour and carries type="monitoring" so we can reject it on non-monitoring routes.
    """
    expires_delta = timedelta(minutes=settings.MONITORING_TOKEN_EXPIRE_MINUTES)
    data = {
        "sub": str(user_id),
        "role": "monitoring_officer",
        "type": "monitoring",   # scoped — only valid for /monitoring/* endpoints
    }
    return create_access_token(data, expires_delta=expires_delta)


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT. Raises JWTError if invalid or expired.
    The caller is responsible for catching JWTError and returning 401.
    """
    # jose verifies the signature AND the exp claim in one call
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    return payload
