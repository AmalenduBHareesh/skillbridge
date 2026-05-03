# src/routers/sessions.py
#
# PURPOSE: Session management and per-session attendance retrieval.

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from src.core.dependencies import require_roles
from src.db.database import get_db
from src.models.models import Batch, Session, User, BatchTrainer
from src.schemas.schemas import SessionCreate, SessionResponse, AttendanceRecord

router = APIRouter(prefix="/sessions", tags=["sessions"])


# ---------------------------------------------------------------------------
# POST /sessions
# ---------------------------------------------------------------------------
@router.post("", response_model=SessionResponse, status_code=201)
def create_session(
    body: SessionCreate,
    current_user: User = Depends(require_roles("trainer")),
    db: DBSession = Depends(get_db),
):
    """
    Trainer creates a new session for a batch.

    Validation:
      - batch must exist (404)
      - trainer must be assigned to this batch (403)
        (we don't want Trainer A creating sessions for Trainer B's batch)
    """
    # Verify batch exists
    batch = db.query(Batch).filter(Batch.id == body.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {body.batch_id} not found.")

    # Verify this trainer is assigned to this batch
    assignment = db.query(BatchTrainer).filter(
        BatchTrainer.batch_id == body.batch_id,
        BatchTrainer.trainer_id == current_user.id,
    ).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this batch.",
        )

    new_session = Session(
        batch_id=body.batch_id,
        trainer_id=current_user.id,
        title=body.title,
        date=body.date,
        start_time=body.start_time,
        end_time=body.end_time,
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


# ---------------------------------------------------------------------------
# GET /sessions/{id}/attendance
# ---------------------------------------------------------------------------
@router.get("/{session_id}/attendance", response_model=list[AttendanceRecord])
def get_session_attendance(
    session_id: int,
    current_user: User = Depends(require_roles("trainer")),
    db: DBSession = Depends(get_db),
):
    """
    Trainer retrieves the full attendance list for a specific session.

    Returns a list of AttendanceRecord objects (one per student who marked).
    Students who haven't marked are simply absent from this list.
    """
    # Verify session exists
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")

    # Return all attendance records for this session
    from src.models.models import Attendance
    records = db.query(Attendance).filter(Attendance.session_id == session_id).all()
    return records
