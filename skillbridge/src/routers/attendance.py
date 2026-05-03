# src/routers/attendance.py
#
# PURPOSE: Student marks their own attendance for a session.

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.exc import IntegrityError

from src.core.dependencies import require_roles
from src.db.database import get_db
from src.models.models import Attendance, BatchStudent, Session, User
from src.schemas.schemas import AttendanceMarkRequest, AttendanceRecord

router = APIRouter(prefix="/attendance", tags=["attendance"])


# ---------------------------------------------------------------------------
# POST /attendance/mark
# ---------------------------------------------------------------------------
@router.post("/mark", response_model=AttendanceRecord, status_code=201)
def mark_attendance(
    body: AttendanceMarkRequest,
    current_user: User = Depends(require_roles("student")),
    db: DBSession = Depends(get_db),
):
    """
    Student marks their own attendance for a session.

    Validation chain:
      1. Session must exist (404)
      2. Student must be enrolled in the batch that owns this session (403)
      3. Student must not have already marked for this session (409)
         — the UniqueConstraint in the DB also catches this as a fallback

    Why check enrollment?
      Prevents a student from marking attendance for a session in a batch
      they were never part of. The assignment spec explicitly requires 403 here.
    """
    # 1. Find the session
    session = db.query(Session).filter(Session.id == body.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {body.session_id} not found.")

    # 2. Check enrollment: is this student in the batch that owns this session?
    enrollment = db.query(BatchStudent).filter(
        BatchStudent.batch_id == session.batch_id,
        BatchStudent.student_id == current_user.id,
    ).first()
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in the batch for this session.",
        )

    # 3. Check for duplicate marking
    existing = db.query(Attendance).filter(
        Attendance.session_id == body.session_id,
        Attendance.student_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already marked attendance for this session.",
        )

    # Create the attendance record
    record = Attendance(
        session_id=body.session_id,
        student_id=current_user.id,
        status=body.status,
    )
    db.add(record)

    try:
        db.commit()
    except IntegrityError:
        # The UniqueConstraint in the model catches a race condition
        # (two simultaneous mark requests from the same student).
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance already marked (concurrent request).",
        )

    db.refresh(record)
    return record
