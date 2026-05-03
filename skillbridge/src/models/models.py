# src/models/models.py
#
# PURPOSE: Define every database table as a Python class.
# SQLAlchemy ORM maps each class to a table. Column types are Python types
# that SQLAlchemy translates to the right SQL for your database.

from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Integer, String, Time, UniqueConstraint
)
from sqlalchemy.orm import relationship

from src.db.database import Base   # all models must inherit Base to be tracked


# ---------------------------------------------------------------------------
# ENUM TYPES
# We define Python Enum-style strings here and pass them to SQLAlchemy's
# Enum() column type. This enforces values at the DB level too.
# ---------------------------------------------------------------------------

ROLES = ("student", "trainer", "institution", "programme_manager", "monitoring_officer")
ATTENDANCE_STATUS = ("present", "absent", "late")


# ---------------------------------------------------------------------------
# USER
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # index=True on primary key is redundant but harmless; SQLAlchemy adds it anyway

    name = Column(String, nullable=False)

    email = Column(String, unique=True, nullable=False, index=True)
    # unique=True: no two users can share an email (enforced at DB level)
    # index=True: lookups by email (login) are fast

    hashed_password = Column(String, nullable=False)
    # We NEVER store plain-text passwords. bcrypt hash goes here.

    role = Column(Enum(*ROLES, name="role_enum"), nullable=False)
    # Enum at the DB level: inserting an invalid role raises a DB error

    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=True)
    # nullable=True: students and programme managers may not belong to an institution

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # timezone=True: stores UTC offset — prevents timezone bugs

    # Relationships (lazy-loaded by default; SQLAlchemy fetches related rows on access)
    institution = relationship("Institution", back_populates="users")
    sessions_created = relationship("Session", back_populates="trainer")
    attendance_records = relationship("Attendance", back_populates="student")


# ---------------------------------------------------------------------------
# INSTITUTION
# ---------------------------------------------------------------------------
class Institution(Base):
    __tablename__ = "institutions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    users = relationship("User", back_populates="institution")
    batches = relationship("Batch", back_populates="institution")


# ---------------------------------------------------------------------------
# BATCH
# ---------------------------------------------------------------------------
class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    institution = relationship("Institution", back_populates="batches")
    sessions = relationship("Session", back_populates="batch")

    # Many-to-many: a batch can have multiple trainers
    trainers = relationship("User", secondary="batch_trainers", overlaps="batches")
    # Many-to-many: a batch can have multiple students
    students = relationship("User", secondary="batch_students", overlaps="batches_as_student")
    invites = relationship("BatchInvite", back_populates="batch")


# ---------------------------------------------------------------------------
# BATCH_TRAINERS  (association table — many-to-many: batch <-> trainer)
# ---------------------------------------------------------------------------
class BatchTrainer(Base):
    __tablename__ = "batch_trainers"
    # No surrogate PK — the pair (batch_id, trainer_id) is the natural key
    batch_id = Column(Integer, ForeignKey("batches.id"), primary_key=True)
    trainer_id = Column(Integer, ForeignKey("users.id"), primary_key=True)


# ---------------------------------------------------------------------------
# BATCH_STUDENTS  (association table — many-to-many: batch <-> student)
# ---------------------------------------------------------------------------
class BatchStudent(Base):
    __tablename__ = "batch_students"
    batch_id = Column(Integer, ForeignKey("batches.id"), primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), primary_key=True)


# ---------------------------------------------------------------------------
# BATCH_INVITES
# ---------------------------------------------------------------------------
class BatchInvite(Base):
    __tablename__ = "batch_invites"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)

    token = Column(String, unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    # uuid4() generates a random UUID. We use it as the invite token.
    # unique=True: no two invites share a token

    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    # Which trainer created this invite

    expires_at = Column(DateTime(timezone=True), nullable=False)
    # Trainer sets expiry. We check this before allowing a student to join.

    used = Column(Boolean, default=False, nullable=False)
    # Once a student uses the token, we flip this to True.
    # Prevents reuse of the same invite link.

    batch = relationship("Batch", back_populates="invites")


# ---------------------------------------------------------------------------
# SESSION
# ---------------------------------------------------------------------------
class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)
    trainer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    date = Column(String, nullable=False)        # "YYYY-MM-DD" stored as string for simplicity
    start_time = Column(String, nullable=False)  # "HH:MM" 24h format
    end_time = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    batch = relationship("Batch", back_populates="sessions")
    trainer = relationship("User", back_populates="sessions_created")
    attendance_records = relationship("Attendance", back_populates="session")


# ---------------------------------------------------------------------------
# ATTENDANCE
# ---------------------------------------------------------------------------
class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(*ATTENDANCE_STATUS, name="attendance_status_enum"), nullable=False)
    marked_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # UniqueConstraint: a student can only have ONE attendance record per session.
    # Prevents double-marking. Enforced at DB level.
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),
    )

    session = relationship("Session", back_populates="attendance_records")
    student = relationship("User", back_populates="attendance_records")
