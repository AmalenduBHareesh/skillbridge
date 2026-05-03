# src/routers/batches.py
#
# PURPOSE: Batch management — create batches, create invite tokens, join via token.

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.dependencies import require_roles
from src.db.database import get_db
from src.models.models import Batch, BatchInvite, BatchStudent, User
from src.schemas.schemas import (
    BatchCreate, BatchResponse,
    InviteCreate, InviteResponse,
    JoinBatchRequest
)

router = APIRouter(prefix="/batches", tags=["batches"])


# ---------------------------------------------------------------------------
# POST /batches
# ---------------------------------------------------------------------------
@router.post("", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
def create_batch(
    body: BatchCreate,
    current_user: User = Depends(require_roles("trainer", "institution")),
    db: Session = Depends(get_db),
):
    """
    Create a new batch.
    Trainers and Institution admins are allowed.

    We verify the institution_id exists before inserting; if not, return 404
    instead of letting the DB raise a foreign key violation (which would be 500).
    """
    from src.models.models import Institution

    # Verify institution exists (404 instead of FK violation 500)
    institution = db.query(Institution).filter(Institution.id == body.institution_id).first()
    if not institution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Institution with id {body.institution_id} not found.",
        )

    new_batch = Batch(name=body.name, institution_id=body.institution_id)
    db.add(new_batch)
    db.commit()
    db.refresh(new_batch)
    return new_batch


# ---------------------------------------------------------------------------
# POST /batches/{id}/invite
# ---------------------------------------------------------------------------
@router.post("/{batch_id}/invite", response_model=InviteResponse, status_code=201)
def create_invite(
    batch_id: int,
    body: InviteCreate,
    current_user: User = Depends(require_roles("trainer")),
    db: Session = Depends(get_db),
):
    """
    Generate a single-use invite token for a batch.
    Only trainers can create invites.

    The token is a UUID4 (generated in the model default).
    The trainer sets the expiry date. After expiry, students can't join.
    After one use, used=True and the token can't be reused.

    Why single-use?
      Prevents a student from sharing the link with 100 friends
      without the trainer knowing. If multi-use links are needed,
      that's a product decision, not a technical constraint.
    """
    # Verify batch exists
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found.")

    invite = BatchInvite(
        batch_id=batch_id,
        created_by=current_user.id,
        expires_at=body.expires_at,
        used=False,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


# ---------------------------------------------------------------------------
# POST /batches/join
# ---------------------------------------------------------------------------
@router.post("/join", status_code=200)
def join_batch(
    body: JoinBatchRequest,
    current_user: User = Depends(require_roles("student")),
    db: Session = Depends(get_db),
):
    """
    Student joins a batch by presenting an invite token.

    Validation chain:
      1. Token must exist
      2. Token must not be used
      3. Token must not be expired
      4. Student must not already be in the batch
    """
    # 1. Find the invite
    invite = db.query(BatchInvite).filter(BatchInvite.token == body.token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite token not found.")

    # 2. Already used?
    if invite.used:
        raise HTTPException(status_code=400, detail="This invite token has already been used.")

    # 3. Expired?
    now = datetime.now(timezone.utc)
    # Make invite.expires_at timezone-aware if it isn't (some DBs strip tz info)
    expires = invite.expires_at
    if expires.tzinfo is None:
        from datetime import timezone as tz
        expires = expires.replace(tzinfo=tz.utc)
    if now > expires:
        raise HTTPException(status_code=400, detail="This invite token has expired.")

    # 4. Already in batch?
    already = db.query(BatchStudent).filter(
        BatchStudent.batch_id == invite.batch_id,
        BatchStudent.student_id == current_user.id,
    ).first()
    if already:
        raise HTTPException(status_code=400, detail="You are already in this batch.")

    # Add student to batch
    membership = BatchStudent(batch_id=invite.batch_id, student_id=current_user.id)
    db.add(membership)

    # Mark invite as used
    invite.used = True
    db.commit()

    return {"message": f"Successfully joined batch {invite.batch_id}."}
