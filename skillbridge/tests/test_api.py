# tests/test_api.py
#
# PURPOSE: The five required tests plus a few extras for confidence.
#
# Test 1: Successful student signup and login → valid JWT returned
# Test 2: Trainer creates a session with all required fields
# Test 3: Student marks own attendance successfully
# Test 4: POST to /monitoring/attendance → 405
# Test 5: Protected endpoint with no token → 401
#
# All tests use the real (SQLite) test database via conftest.py fixtures.

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from src.core.config import settings
from src.models.models import (
    Institution, Batch, BatchTrainer, BatchStudent, Session, User
)
from src.core.security import hash_password


# ============================================================================
# HELPERS — quickly insert seed data for a test
# ============================================================================

def create_user(db, name, email, password, role, institution_id=None):
    u = User(
        name=name,
        email=email,
        hashed_password=hash_password(password),
        role=role,
        institution_id=institution_id,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def create_institution(db, name="Test Institution"):
    i = Institution(name=name)
    db.add(i)
    db.commit()
    db.refresh(i)
    return i


def create_batch(db, institution_id, name="Test Batch"):
    b = Batch(name=name, institution_id=institution_id)
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def assign_trainer(db, batch_id, trainer_id):
    bt = BatchTrainer(batch_id=batch_id, trainer_id=trainer_id)
    db.add(bt)
    db.commit()


def enroll_student(db, batch_id, student_id):
    bs = BatchStudent(batch_id=batch_id, student_id=student_id)
    db.add(bs)
    db.commit()


def create_session_obj(db, batch_id, trainer_id):
    s = Session(
        batch_id=batch_id,
        trainer_id=trainer_id,
        title="Test Session",
        date="2024-01-15",
        start_time="09:00",
        end_time="11:00",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def get_token(client, email, password):
    """Helper: log in and return the access token string."""
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.json()}"
    return resp.json()["access_token"]


# ============================================================================
# TEST 1: Student signup and login — valid JWT returned
# ============================================================================

def test_student_signup_and_login_returns_valid_jwt(client):
    """
    REQUIREMENT: Successful student signup and login, asserting a valid JWT is returned.

    Steps:
      1. POST /auth/signup with student data
      2. Verify 201 response and access_token in body
      3. POST /auth/login with same credentials
      4. Verify 200 response and access_token in body
      5. Decode the JWT and verify claims: sub, role, exp all present
    """
    # Step 1: Signup
    signup_payload = {
        "name": "Test Student",
        "email": "teststudent@example.com",
        "password": "securepassword123",
        "role": "student",
    }
    signup_resp = client.post("/auth/signup", json=signup_payload)

    # Assert 201 Created
    assert signup_resp.status_code == 201, f"Signup failed: {signup_resp.json()}"

    signup_body = signup_resp.json()
    assert "access_token" in signup_body
    assert signup_body["token_type"] == "bearer"

    # Step 3: Login
    login_resp = client.post(
        "/auth/login",
        json={"email": "teststudent@example.com", "password": "securepassword123"},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.json()}"

    login_body = login_resp.json()
    token = login_body["access_token"]
    assert token is not None and len(token) > 0

    # Step 5: Decode JWT and verify claims
    # We decode WITHOUT verifying signature here to inspect claims
    # (in a real audit you'd verify the signature too — we do that implicitly
    #  by trusting that the API returned it)
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    assert "sub" in payload, "JWT missing 'sub' claim"
    assert "role" in payload, "JWT missing 'role' claim"
    assert "exp" in payload, "JWT missing 'exp' claim"
    assert payload["role"] == "student"

    print(f"\n[TEST 1 PASS] JWT payload: {payload}")


# ============================================================================
# TEST 2: Trainer creates a session with all required fields
# ============================================================================

def test_trainer_creates_session(client, db):
    """
    REQUIREMENT: A trainer creating a session with all required fields.

    Setup:
      - Create institution, batch, trainer
      - Assign trainer to batch
      - Log in as trainer
    Action:
      - POST /sessions with full payload
    Assert:
      - 201 Created
      - Response contains the session fields we sent
    """
    # Setup
    institution = create_institution(db)
    batch = create_batch(db, institution.id)
    trainer = create_user(db, "Test Trainer", "trainer@test.com", "pass123", "trainer", institution.id)
    assign_trainer(db, batch.id, trainer.id)

    token = get_token(client, "trainer@test.com", "pass123")

    # Action
    session_payload = {
        "batch_id": batch.id,
        "title": "Introduction to Python",
        "date": "2024-06-15",
        "start_time": "09:00",
        "end_time": "11:00",
    }
    resp = client.post(
        "/sessions",
        json=session_payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    # Assertions
    assert resp.status_code == 201, f"Create session failed: {resp.json()}"
    body = resp.json()
    assert body["batch_id"] == batch.id
    assert body["title"] == "Introduction to Python"
    assert body["date"] == "2024-06-15"
    assert body["trainer_id"] == trainer.id

    print(f"\n[TEST 2 PASS] Created session id={body['id']}")


# ============================================================================
# TEST 3: Student marks own attendance
# ============================================================================

def test_student_marks_own_attendance(client, db):
    """
    REQUIREMENT: A student successfully marking their own attendance.

    Setup:
      - Institution, batch, trainer, session
      - Student enrolled in the batch
    Action:
      - POST /attendance/mark as the student
    Assert:
      - 201 Created
      - status == "present"
    """
    # Setup
    institution = create_institution(db)
    batch = create_batch(db, institution.id)
    trainer = create_user(db, "Trainer", "trainer2@test.com", "pass123", "trainer", institution.id)
    assign_trainer(db, batch.id, trainer.id)
    student = create_user(db, "Student", "student2@test.com", "pass123", "student")
    enroll_student(db, batch.id, student.id)
    session = create_session_obj(db, batch.id, trainer.id)

    student_token = get_token(client, "student2@test.com", "pass123")

    # Action
    resp = client.post(
        "/attendance/mark",
        json={"session_id": session.id, "status": "present"},
        headers={"Authorization": f"Bearer {student_token}"},
    )

    # Assertions
    assert resp.status_code == 201, f"Mark attendance failed: {resp.json()}"
    body = resp.json()
    assert body["student_id"] == student.id
    assert body["session_id"] == session.id
    assert body["status"] == "present"

    print(f"\n[TEST 3 PASS] Attendance record id={body['id']}")


# ============================================================================
# TEST 4: POST /monitoring/attendance → 405 Method Not Allowed
# ============================================================================

def test_post_to_monitoring_attendance_returns_405(client):
    """
    REQUIREMENT: A POST to /monitoring/attendance returning 405.

    No auth needed — the method check happens before auth.
    """
    resp = client.post("/monitoring/attendance", json={})

    assert resp.status_code == 405, (
        f"Expected 405 Method Not Allowed, got {resp.status_code}: {resp.json()}"
    )

    print(f"\n[TEST 4 PASS] POST /monitoring/attendance → 405")


# ============================================================================
# TEST 5: Protected endpoint with no token → 401
# ============================================================================

def test_protected_endpoint_without_token_returns_401(client):
    """
    REQUIREMENT: A request to a protected endpoint with no token returning 401.

    We test /sessions (trainer-only) without any Authorization header.
    """
    resp = client.post(
        "/sessions",
        json={
            "batch_id": 1,
            "title": "No Auth Session",
            "date": "2024-01-01",
            "start_time": "10:00",
            "end_time": "12:00",
        }
        # No Authorization header
    )

    assert resp.status_code == 401, (
        f"Expected 401 Unauthorized, got {resp.status_code}: {resp.json()}"
    )

    print(f"\n[TEST 5 PASS] No token → 401")


# ============================================================================
# BONUS TEST 6: Wrong role → 403
# ============================================================================

def test_student_cannot_create_session(client, db):
    """
    A student attempting to create a session should get 403.
    This validates RBAC is enforced server-side, not just by convention.
    """
    student = create_user(db, "Student", "s@test.com", "pass", "student")
    token = get_token(client, "s@test.com", "pass")

    resp = client.post(
        "/sessions",
        json={"batch_id": 1, "title": "X", "date": "2024-01-01", "start_time": "09:00", "end_time": "10:00"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 403
    print(f"\n[BONUS TEST 6 PASS] Student cannot create session → 403")


# ============================================================================
# BONUS TEST 7: Student cannot mark attendance for unenrolled session → 403
# ============================================================================

def test_student_cannot_mark_attendance_for_unenrolled_session(client, db):
    """
    Assignment requirement: student not enrolled in a batch → 403 on mark attendance.
    """
    institution = create_institution(db)
    batch = create_batch(db, institution.id)
    trainer = create_user(db, "T", "t3@test.com", "pass", "trainer", institution.id)
    assign_trainer(db, batch.id, trainer.id)
    session = create_session_obj(db, batch.id, trainer.id)

    # Student is NOT enrolled in the batch
    student = create_user(db, "S", "s3@test.com", "pass", "student")
    student_token = get_token(client, "s3@test.com", "pass")

    resp = client.post(
        "/attendance/mark",
        json={"session_id": session.id, "status": "present"},
        headers={"Authorization": f"Bearer {student_token}"},
    )

    assert resp.status_code == 403
    print(f"\n[BONUS TEST 7 PASS] Unenrolled student → 403 on attendance mark")
