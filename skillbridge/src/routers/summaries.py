# src/routers/summaries.py
#
# PURPOSE: Read-only summary/reporting endpoints for Institution, Programme Manager,
#          and Monitoring Officer roles.

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DBSession

from src.core.dependencies import require_roles, get_monitoring_user
from src.db.database import get_db
from src.models.models import (
    Attendance, Batch, BatchStudent, Institution,
    Session, User
)
from src.schemas.schemas import (
    AttendanceSummaryItem, BatchSummaryResponse,
    InstitutionSummaryResponse, ProgrammeSummaryResponse,
    AttendanceRecord
)

router = APIRouter(tags=["summaries"])


# ---------------------------------------------------------------------------
# HELPER: build attendance summary for a list of (student, records) pairs
# ---------------------------------------------------------------------------
def _build_student_summaries(db: DBSession, batch_id: int) -> list[AttendanceSummaryItem]:
    """
    Given a batch_id, return a list of per-student attendance counts.
    This is reused by both the batch summary and institution summary endpoints.
    """
    # Get all students in this batch
    memberships = db.query(BatchStudent).filter(BatchStudent.batch_id == batch_id).all()
    student_ids = [m.student_id for m in memberships]

    summaries = []
    for sid in student_ids:
        student = db.query(User).filter(User.id == sid).first()
        if not student:
            continue

        # Get all sessions in this batch
        sessions = db.query(Session).filter(Session.batch_id == batch_id).all()
        session_ids = [s.id for s in sessions]

        # Count attendance by status
        records = db.query(Attendance).filter(
            Attendance.student_id == sid,
            Attendance.session_id.in_(session_ids),
        ).all()

        present = sum(1 for r in records if r.status == "present")
        absent = sum(1 for r in records if r.status == "absent")
        late = sum(1 for r in records if r.status == "late")

        summaries.append(AttendanceSummaryItem(
            student_id=sid,
            student_name=student.name,
            present=present,
            absent=absent,
            late=late,
            total=len(records),
        ))

    return summaries


# ---------------------------------------------------------------------------
# GET /batches/{id}/summary  — Institution role
# ---------------------------------------------------------------------------
@router.get("/batches/{batch_id}/summary", response_model=BatchSummaryResponse)
def batch_summary(
    batch_id: int,
    current_user: User = Depends(require_roles("institution", "programme_manager", "monitoring_officer")),
    db: DBSession = Depends(get_db),
):
    """
    Attendance summary for all students in a batch.
    Accessible by institution admins, programme managers, and monitoring officers.
    """
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found.")

    student_summaries = _build_student_summaries(db, batch_id)

    return BatchSummaryResponse(
        batch_id=batch_id,
        batch_name=batch.name,
        students=student_summaries,
    )


# ---------------------------------------------------------------------------
# GET /institutions/{id}/summary  — Programme Manager role
# ---------------------------------------------------------------------------
@router.get("/institutions/{institution_id}/summary", response_model=InstitutionSummaryResponse)
def institution_summary(
    institution_id: int,
    current_user: User = Depends(require_roles("programme_manager", "monitoring_officer")),
    db: DBSession = Depends(get_db),
):
    """
    Summary across all batches under one institution.
    """
    institution = db.query(Institution).filter(Institution.id == institution_id).first()
    if not institution:
        raise HTTPException(status_code=404, detail=f"Institution {institution_id} not found.")

    batches = db.query(Batch).filter(Batch.institution_id == institution_id).all()

    batch_summaries = []
    for batch in batches:
        student_summaries = _build_student_summaries(db, batch.id)
        batch_summaries.append(BatchSummaryResponse(
            batch_id=batch.id,
            batch_name=batch.name,
            students=student_summaries,
        ))

    return InstitutionSummaryResponse(
        institution_id=institution_id,
        institution_name=institution.name,
        batches=batch_summaries,
    )


# ---------------------------------------------------------------------------
# GET /programme/summary  — Programme Manager role
# ---------------------------------------------------------------------------
@router.get("/programme/summary", response_model=ProgrammeSummaryResponse)
def programme_summary(
    current_user: User = Depends(require_roles("programme_manager", "monitoring_officer")),
    db: DBSession = Depends(get_db),
):
    """
    Programme-wide summary: all institutions → all batches → all students.
    This can be a large response for a big programme; in production you'd paginate.
    """
    institutions = db.query(Institution).all()

    inst_summaries = []
    for institution in institutions:
        batches = db.query(Batch).filter(Batch.institution_id == institution.id).all()
        batch_summaries = []
        for batch in batches:
            student_summaries = _build_student_summaries(db, batch.id)
            batch_summaries.append(BatchSummaryResponse(
                batch_id=batch.id,
                batch_name=batch.name,
                students=student_summaries,
            ))
        inst_summaries.append(InstitutionSummaryResponse(
            institution_id=institution.id,
            institution_name=institution.name,
            batches=batch_summaries,
        ))

    return ProgrammeSummaryResponse(institutions=inst_summaries)


# ---------------------------------------------------------------------------
# GET /monitoring/attendance  — Monitoring Officer ONLY (scoped token)
# ---------------------------------------------------------------------------
@router.get("/monitoring/attendance", response_model=list[AttendanceRecord])
def monitoring_attendance(
    current_user: User = Depends(get_monitoring_user),  # scoped token validation
    db: DBSession = Depends(get_db),
):
    """
    Read-only view of ALL attendance records across the entire programme.
    Uses the SCOPED monitoring token (not the standard access token).

    The assignment requires 405 for any non-GET verb on this path.
    We handle that below with explicit route registrations.
    """
    records = db.query(Attendance).all()
    return records


# ---------------------------------------------------------------------------
# ALL OTHER METHODS on /monitoring/attendance → 405 Method Not Allowed
# ---------------------------------------------------------------------------
# We register the same path for POST/PUT/PATCH/DELETE and return 405.
# This satisfies the assignment requirement explicitly.

@router.post("/monitoring/attendance", status_code=405, include_in_schema=False)
@router.put("/monitoring/attendance", status_code=405, include_in_schema=False)
@router.patch("/monitoring/attendance", status_code=405, include_in_schema=False)
@router.delete("/monitoring/attendance", status_code=405, include_in_schema=False)
def monitoring_method_not_allowed():
    """Return 405 for all non-GET methods on /monitoring/attendance."""
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="The monitoring attendance endpoint is read-only. Only GET is allowed.",
    )
