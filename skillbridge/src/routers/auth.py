# src/routers/auth.py
#
# PURPOSE: Authentication endpoints — signup, login, and monitoring token exchange.
# All three are public (no auth required to hit them).

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.security import (
    hash_password, verify_password,
    create_access_token, create_monitoring_token
)
from src.core.dependencies import get_current_user
from src.db.database import get_db
from src.models.models import User
from src.schemas.schemas import (
    SignupRequest, LoginRequest,
    TokenResponse, MonitoringTokenRequest
)

# APIRouter is like a mini-app. We register it in main.py with a prefix.
router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# POST /auth/signup
# ---------------------------------------------------------------------------
@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    """
    Create a new user account and return a JWT.

    Steps:
      1. Check the email is not already taken (409 Conflict if it is)
      2. Hash the password (NEVER store plain text)
      3. Insert the user row
      4. Return a signed JWT so the client is immediately logged in
    """
    # Step 1: duplicate email check
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    # Step 2: hash password
    hashed = hash_password(body.password)

    # Step 3: create ORM object and insert
    new_user = User(
        name=body.name,
        email=body.email,
        hashed_password=hashed,
        role=body.role,
        institution_id=body.institution_id,
    )
    db.add(new_user)
    db.commit()          # writes to DB and assigns new_user.id
    db.refresh(new_user) # re-reads the row so new_user.id is populated

    # Step 4: mint JWT
    # "sub" (subject) must be a string per JWT spec
    token = create_access_token({"sub": str(new_user.id), "role": new_user.role})

    return TokenResponse(access_token=token)


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Validate credentials and return a JWT.

    Security note: we use the same error message for "email not found" and
    "wrong password" intentionally — this prevents user enumeration attacks
    where an attacker could discover which emails are registered.
    """
    user = db.query(User).filter(User.email == body.email).first()

    # Deliberately vague error message (user enumeration prevention)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(access_token=token)


# ---------------------------------------------------------------------------
# POST /auth/monitoring-token
# ---------------------------------------------------------------------------
@router.post("/monitoring-token", response_model=TokenResponse)
def get_monitoring_token(
    body: MonitoringTokenRequest,
    current_user: User = Depends(get_current_user),  # must be logged in first
    db: Session = Depends(get_db),
):
    """
    Second-factor token exchange for Monitoring Officers.

    Flow:
      1. Client logs in normally → gets standard JWT (24h)
      2. Client sends that JWT + the API key to this endpoint
      3. Server verifies role == monitoring_officer AND key matches .env
      4. Returns a short-lived (1h) monitoring-scoped token

    Why two tokens?
      The standard JWT is long-lived (24h) and could be stolen.
      The monitoring-scoped token is short-lived (1h), scoped to read-only endpoints,
      and requires an extra secret to obtain. Defense in depth.
    """
    # Must be a monitoring officer — other roles get 403
    if current_user.role != "monitoring_officer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only monitoring officers can obtain a monitoring token.",
        )

    # Validate the API key
    if body.key != settings.MONITORING_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    # Mint the scoped token
    scoped_token = create_monitoring_token(current_user.id)
    return TokenResponse(access_token=scoped_token)
