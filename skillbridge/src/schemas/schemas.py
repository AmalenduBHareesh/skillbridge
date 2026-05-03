# src/schemas/schemas.py
#
# PURPOSE: Pydantic models for request validation and response serialization.
# FastAPI uses these to:
#   1. Validate incoming JSON (wrong types or missing fields → 422 automatically)
#   2. Serialize outgoing data (only expose fields we explicitly list)
#
# Pydantic v2 is used here (comes with FastAPI 0.111+).

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, validator


# ===========================================================================
# AUTH
# ===========================================================================

class SignupRequest(BaseModel):
    """Body for POST /auth/signup"""
    name: str
    email: EmailStr          # pydantic validates email format automatically
    password: str
    role: str                # one of: student/trainer/institution/programme_manager/monitoring_officer
    institution_id: Optional[int] = None  # required for trainers; optional for others

    @validator("role")
    @classmethod
    def role_must_be_valid(cls, v):
        """Reject signup if role is not one of the five allowed values."""
        valid = {"student", "trainer", "institution", "programme_manager", "monitoring_officer"}
        if v not in valid:
            raise ValueError(f"role must be one of {valid}")
        return v


class LoginRequest(BaseModel):
    """Body for POST /auth/login"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response body for any endpoint that returns a JWT."""
    access_token: str
    token_type: str = "bearer"   # OAuth2 convention — always "bearer"


class MonitoringTokenRequest(BaseModel):
    """Body for POST /auth/monitoring-token"""
    key: str   # the MONITORING_API_KEY from .env


# ===========================================================================
# BATCHES
# ===========================================================================

class BatchCreate(BaseModel):
    """Body for POST /batches"""
    name: str
    institution_id: int


class BatchResponse(BaseModel):
    """What we send back after creating/reading a batch."""
    id: int
    name: str
    institution_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
    # from_attributes=True (was orm_mode in pydantic v1):
    # allows pydantic to read data from SQLAlchemy ORM objects directly


class InviteCreate(BaseModel):
    """Body for POST /batches/{id}/invite"""
    expires_at: datetime   # trainer decides when the invite expires


class InviteResponse(BaseModel):
    """Response after creating an invite."""
    id: int
    batch_id: int
    token: str             # the UUID token the student will use
    expires_at: datetime
    used: bool

    model_config = {"from_attributes": True}


class JoinBatchRequest(BaseModel):
    """Body for POST /batches/join"""
    token: str   # the invite token the student received


# ===========================================================================
# SESSIONS
# ===========================================================================

class SessionCreate(BaseModel):
    """Body for POST /sessions"""
    batch_id: int
    title: str
    date: str        # "YYYY-MM-DD"
    start_time: str  # "HH:MM"
    end_time: str    # "HH:MM"


class SessionResponse(BaseModel):
    id: int
    batch_id: int
    trainer_id: int
    title: str
    date: str
    start_time: str
    end_time: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ===========================================================================
# ATTENDANCE
# ===========================================================================

class AttendanceMarkRequest(BaseModel):
    """Body for POST /attendance/mark"""
    session_id: int
    status: str   # present / absent / late

    @validator("status")
    @classmethod
    def status_must_be_valid(cls, v):
        if v not in {"present", "absent", "late"}:
            raise ValueError("status must be present, absent, or late")
        return v


class AttendanceRecord(BaseModel):
    """One row in an attendance list."""
    id: int
    session_id: int
    student_id: int
    status: str
    marked_at: datetime

    model_config = {"from_attributes": True}


# ===========================================================================
# SUMMARIES
# ===========================================================================

class AttendanceSummaryItem(BaseModel):
    """One student's attendance summary within a batch or session."""
    student_id: int
    student_name: str
    present: int
    absent: int
    late: int
    total: int


class BatchSummaryResponse(BaseModel):
    batch_id: int
    batch_name: str
    students: List[AttendanceSummaryItem]


class InstitutionSummaryResponse(BaseModel):
    institution_id: int
    institution_name: str
    batches: List[BatchSummaryResponse]


class ProgrammeSummaryResponse(BaseModel):
    institutions: List[InstitutionSummaryResponse]


# ===========================================================================
# USER (used in monitoring endpoint)
# ===========================================================================

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    institution_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}
