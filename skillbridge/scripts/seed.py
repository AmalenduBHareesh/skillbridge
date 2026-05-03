#!/usr/bin/env python3
# scripts/seed.py
#
# PURPOSE: Populate the database with realistic test data.
# Run this ONCE after the app creates the tables.
#
# Usage:
#   cd skillbridge
#   python scripts/seed.py
#
# What it creates:
#   - 2 institutions
#   - 1 programme manager
#   - 1 monitoring officer
#   - 4 trainers (2 per institution)
#   - 15 students
#   - 3 batches
#   - 8 sessions with attendance records
#   - Batch-trainer and batch-student assignments

import sys
import os

# Add the project root to Python's module search path so "from src..." imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone

from src.db.database import SessionLocal, Base, engine
from src.models.models import (
    User, Institution, Batch, BatchTrainer, BatchStudent,
    BatchInvite, Session, Attendance
)
from src.core.security import hash_password

# Create all tables (idempotent — safe to run multiple times)
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # -----------------------------------------------------------------------
    # Clear existing data (so seed is idempotent)
    # Order matters: delete children before parents (FK constraints)
    # -----------------------------------------------------------------------
    db.query(Attendance).delete()
    db.query(Session).delete()
    db.query(BatchInvite).delete()
    db.query(BatchStudent).delete()
    db.query(BatchTrainer).delete()
    db.query(Batch).delete()
    db.query(User).delete()
    db.query(Institution).delete()
    db.commit()
    print("Cleared existing data.")

    # -----------------------------------------------------------------------
    # INSTITUTIONS
    # -----------------------------------------------------------------------
    inst1 = Institution(name="Government ITI Kozhikode")
    inst2 = Institution(name="KASE Skill Centre Thrissur")
    db.add_all([inst1, inst2])
    db.commit()
    db.refresh(inst1)
    db.refresh(inst2)
    print(f"Created institutions: {inst1.id}, {inst2.id}")

    # -----------------------------------------------------------------------
    # PROGRAMME MANAGER (not tied to an institution)
    # -----------------------------------------------------------------------
    pm = User(
        name="Priya Menon",
        email="pm@skillbridge.test",
        hashed_password=hash_password("pm_pass123"),
        role="programme_manager",
    )
    db.add(pm)

    # -----------------------------------------------------------------------
    # MONITORING OFFICER
    # -----------------------------------------------------------------------
    mo = User(
        name="Rahul Monitor",
        email="monitor@skillbridge.test",
        hashed_password=hash_password("monitor_pass123"),
        role="monitoring_officer",
    )
    db.add(mo)

    # -----------------------------------------------------------------------
    # INSTITUTION ADMIN USERS
    # -----------------------------------------------------------------------
    inst1_admin = User(
        name="Admin Kozhikode",
        email="admin_kzd@skillbridge.test",
        hashed_password=hash_password("admin_pass123"),
        role="institution",
        institution_id=inst1.id,
    )
    inst2_admin = User(
        name="Admin Thrissur",
        email="admin_tsr@skillbridge.test",
        hashed_password=hash_password("admin_pass123"),
        role="institution",
        institution_id=inst2.id,
    )
    db.add_all([inst1_admin, inst2_admin])

    db.commit()

    # -----------------------------------------------------------------------
    # TRAINERS (4 total: 2 per institution)
    # -----------------------------------------------------------------------
    trainer_data = [
        ("Arun Kumar", "trainer1@skillbridge.test", inst1.id),
        ("Deepa Nair", "trainer2@skillbridge.test", inst1.id),
        ("Sajan Thomas", "trainer3@skillbridge.test", inst2.id),
        ("Lakshmi Pillai","trainer4@skillbridge.test", inst2.id),
    ]
    trainers = []
    for name, email, iid in trainer_data:
        t = User(
            name=name,
            email=email,
            hashed_password=hash_password("trainer_pass123"),
            role="trainer",
            institution_id=iid,
        )
        db.add(t)
        trainers.append(t)
    db.commit()
    for t in trainers:
        db.refresh(t)
    print(f"Created trainers: {[t.id for t in trainers]}")

    # -----------------------------------------------------------------------
    # STUDENTS (15 total)
    # -----------------------------------------------------------------------
    student_names = [
        "Alice A", "Bob B", "Carol C", "David D", "Eve E",
        "Frank F", "Grace G", "Heidi H", "Ivan I", "Judy J",
        "Karl K", "Laura L", "Mallory M", "Niaj N", "Olivia O",
    ]
    students = []
    for i, name in enumerate(student_names):
        s = User(
            name=name,
            email=f"student{i+1}@skillbridge.test",
            hashed_password=hash_password("student_pass123"),
            role="student",
        )
        db.add(s)
        students.append(s)
    db.commit()
    for s in students:
        db.refresh(s)
    print(f"Created students: {[s.id for s in students]}")

    # -----------------------------------------------------------------------
    # BATCHES (3 total)
    # -----------------------------------------------------------------------
    batch1 = Batch(name="Batch A — Web Dev", institution_id=inst1.id)
    batch2 = Batch(name="Batch B — Data Entry", institution_id=inst1.id)
    batch3 = Batch(name="Batch C — Electronics", institution_id=inst2.id)
    db.add_all([batch1, batch2, batch3])
    db.commit()
    db.refresh(batch1); db.refresh(batch2); db.refresh(batch3)
    print(f"Created batches: {batch1.id}, {batch2.id}, {batch3.id}")

    # -----------------------------------------------------------------------
    # BATCH-TRAINER ASSIGNMENTS
    # -----------------------------------------------------------------------
    db.add_all([
        BatchTrainer(batch_id=batch1.id, trainer_id=trainers[0].id),
        BatchTrainer(batch_id=batch2.id, trainer_id=trainers[1].id),
        BatchTrainer(batch_id=batch3.id, trainer_id=trainers[2].id),
        BatchTrainer(batch_id=batch3.id, trainer_id=trainers[3].id),  # batch3 has 2 trainers
    ])
    db.commit()

    # -----------------------------------------------------------------------
    # BATCH-STUDENT ASSIGNMENTS
    # batch1: students 0-5  (6 students)
    # batch2: students 5-10 (6 students, student 5 in both)
    # batch3: students 10-14 (5 students)
    # -----------------------------------------------------------------------
    for s in students[0:6]:
        db.add(BatchStudent(batch_id=batch1.id, student_id=s.id))
    for s in students[5:11]:
        db.add(BatchStudent(batch_id=batch2.id, student_id=s.id))
    for s in students[10:15]:
        db.add(BatchStudent(batch_id=batch3.id, student_id=s.id))
    db.commit()

    # -----------------------------------------------------------------------
    # SESSIONS (8 total: 3 for batch1, 3 for batch2, 2 for batch3)
    # -----------------------------------------------------------------------
    today = datetime.now(timezone.utc).date()
    sessions_data = [
        # batch1 sessions
        (batch1.id, trainers[0].id, "Intro to HTML", str(today - timedelta(days=6)), "09:00", "11:00"),
        (batch1.id, trainers[0].id, "CSS Basics", str(today - timedelta(days=4)), "09:00", "11:00"),
        (batch1.id, trainers[0].id, "JavaScript Fundamentals", str(today - timedelta(days=2)), "09:00", "11:00"),
        # batch2 sessions
        (batch2.id, trainers[1].id, "MS Word Basics", str(today - timedelta(days=5)), "14:00", "16:00"),
        (batch2.id, trainers[1].id, "Excel Introduction", str(today - timedelta(days=3)), "14:00", "16:00"),
        (batch2.id, trainers[1].id, "Data Entry Practice", str(today - timedelta(days=1)), "14:00", "16:00"),
        # batch3 sessions
        (batch3.id, trainers[2].id, "Circuit Basics", str(today - timedelta(days=7)), "10:00", "12:00"),
        (batch3.id, trainers[2].id, "Soldering Techniques", str(today - timedelta(days=3)), "10:00", "12:00"),
    ]
    sess_objects = []
    for batch_id, trainer_id, title, date, st, et in sessions_data:
        s = Session(
            batch_id=batch_id, trainer_id=trainer_id,
            title=title, date=date, start_time=st, end_time=et,
        )
        db.add(s)
        sess_objects.append(s)
    db.commit()
    for s in sess_objects:
        db.refresh(s)
    print(f"Created sessions: {[s.id for s in sess_objects]}")

    # -----------------------------------------------------------------------
    # ATTENDANCE RECORDS
    # For batch1 sessions: mark attendance for students 0-5
    # Mix of present/absent/late to make summaries interesting
    # -----------------------------------------------------------------------
    import random
    random.seed(42)   # deterministic so tests can rely on known data

    statuses = ["present", "present", "present", "late", "absent"]  # weighted distribution

    batch1_sessions = sess_objects[0:3]
    batch1_students = students[0:6]
    batch2_sessions = sess_objects[3:6]
    batch2_students = students[5:11]
    batch3_sessions = sess_objects[6:8]
    batch3_students = students[10:15]

    attendance_records = []
    for session_group, student_group in [
        (batch1_sessions, batch1_students),
        (batch2_sessions, batch2_students),
        (batch3_sessions, batch3_students),
    ]:
        for sess in session_group:
            for student in student_group:
                status = random.choice(statuses)
                attendance_records.append(Attendance(
                    session_id=sess.id,
                    student_id=student.id,
                    status=status,
                ))
    db.add_all(attendance_records)
    db.commit()
    print(f"Created {len(attendance_records)} attendance records.")

    # -----------------------------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------------------------
    print("\n" + "="*60)
    print("SEED COMPLETE — Test accounts:")
    print("="*60)
    print("Role               | Email                              | Password")
    print("-"*60)
    print(f"student            | student1@skillbridge.test          | student_pass123")
    print(f"trainer            | trainer1@skillbridge.test          | trainer_pass123")
    print(f"institution        | admin_kzd@skillbridge.test         | admin_pass123")
    print(f"programme_manager  | pm@skillbridge.test                | pm_pass123")
    print(f"monitoring_officer | monitor@skillbridge.test           | monitor_pass123")
    print("="*60)

except Exception as e:
    db.rollback()
    print(f"Seed failed: {e}")
    raise
finally:
    db.close()
