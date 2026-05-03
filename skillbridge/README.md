# SkillBridge Attendance API

A REST API backend for a fictional state-level skilling programme called **SkillBridge**. Built with FastAPI, PostgreSQL (Neon), JWT authentication, and role-based access control across 5 user roles.

---

## Live API

```
https://skillbridge-api-iuc9.onrender.com
```

Swagger UI (test all endpoints in browser):
```
https://skillbridge-api-iuc9.onrender.com/docs
```

---

## Local Setup (from scratch)

Assumes Python and pip are installed. Nothing else needed.

```bash
# 1. Clone the repo
git clone https://github.com/AmalenduBHareesh/skillbridge.git
cd skillbridge

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env:
#   DATABASE_URL → your PostgreSQL connection string (use postgresql+pg8000:// prefix)
#   SECRET_KEY   → run: python -c "import secrets; print(secrets.token_hex(32))"

# 5. Seed the database
python scripts/seed.py

# 6. Run the server
uvicorn src.main:app --reload
# or on Windows: python -m uvicorn src.main:app --reload

# API runs at   → http://localhost:8000
# Swagger UI at → http://localhost:8000/docs
```

> **Note on DATABASE_URL:** This project uses `pg8000` (pure Python PostgreSQL driver).
> Your connection string must start with `postgresql+pg8000://` not `postgresql://`

---

## Test Accounts

All five roles are created by `scripts/seed.py`:

| Role | Email | Password |
|---|---|---|
| student | student1@skillbridge.test | student_pass123 |
| trainer | trainer1@skillbridge.test | trainer_pass123 |
| institution | admin_kzd@skillbridge.test | admin_pass123 |
| programme_manager | pm@skillbridge.test | pm_pass123 |
| monitoring_officer | monitor@skillbridge.test | monitor_pass123 |

---

## Running Tests

```bash
python -m pytest tests/ -v
```

Expected: **7 passed**. Tests use SQLite in memory — no external database needed.

| # | Test | Covers |
|---|---|---|
| 1 | test_student_signup_and_login_returns_valid_jwt | Signup + login + JWT claims verified |
| 2 | test_trainer_creates_session | Session creation with RBAC check |
| 3 | test_student_marks_own_attendance | Attendance marking + enrollment check |
| 4 | test_post_to_monitoring_attendance_returns_405 | 405 on non-GET verb |
| 5 | test_protected_endpoint_without_token_returns_401 | 401 with missing token |
| 6 | test_student_cannot_create_session | Wrong role → 403 |
| 7 | test_student_cannot_mark_attendance_for_unenrolled_session | Unenrolled student → 403 |

---

## API Endpoints

| Method | Path | Role Required |
|---|---|---|
| POST | /auth/signup | All |
| POST | /auth/login | All |
| POST | /auth/monitoring-token | monitoring_officer |
| POST | /batches | trainer / institution |
| POST | /batches/{id}/invite | trainer |
| POST | /batches/join | student |
| POST | /sessions | trainer |
| POST | /attendance/mark | student |
| GET | /sessions/{id}/attendance | trainer |
| GET | /batches/{id}/summary | institution |
| GET | /institutions/{id}/summary | programme_manager |
| GET | /programme/summary | programme_manager |
| GET | /monitoring/attendance | monitoring_officer (scoped token) |

---

## Sample curl Commands

> On Windows PowerShell use `Invoke-RestMethod` instead of curl (see examples below)

### Login and get token

```bash
# Linux/Mac
curl -X POST https://skillbridge-api-iuc9.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"student1@skillbridge.test","password":"student_pass123"}'
```

```powershell
# Windows PowerShell
Invoke-RestMethod -Method POST -Uri "https://skillbridge-api-iuc9.onrender.com/auth/login" -ContentType "application/json" -Body '{"email":"student1@skillbridge.test","password":"student_pass123"}'
```

### Signup
```bash
curl -X POST https://skillbridge-api-iuc9.onrender.com/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"test@example.com","password":"pass123","role":"student"}'
```

### Monitoring Officer — two-step token flow

```bash
# Step 1: Login as monitoring officer → get standard token
curl -X POST https://skillbridge-api-iuc9.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"monitor@skillbridge.test","password":"monitor_pass123"}'

# Step 2: Exchange standard token + API key → get scoped monitoring token
curl -X POST https://skillbridge-api-iuc9.onrender.com/auth/monitoring-token \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer STANDARD_TOKEN_FROM_STEP_1" \
  -d '{"key":"monitoring-secret-api-key-2024"}'

# Step 3: Use scoped token on monitoring endpoint
curl https://skillbridge-api-iuc9.onrender.com/monitoring/attendance \
  -H "Authorization: Bearer SCOPED_TOKEN_FROM_STEP_2"
```

### Create a batch (trainer)
```bash
curl -X POST https://skillbridge-api-iuc9.onrender.com/batches \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TRAINER_TOKEN" \
  -d '{"name":"New Batch","institution_id":1}'
```

### Generate invite (trainer)
```bash
curl -X POST https://skillbridge-api-iuc9.onrender.com/batches/1/invite \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TRAINER_TOKEN" \
  -d '{"expires_at":"2025-12-31T23:59:59Z"}'
```

### Student joins batch
```bash
curl -X POST https://skillbridge-api-iuc9.onrender.com/batches/join \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_STUDENT_TOKEN" \
  -d '{"token":"INVITE_TOKEN"}'
```

### Create session (trainer)
```bash
curl -X POST https://skillbridge-api-iuc9.onrender.com/sessions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TRAINER_TOKEN" \
  -d '{"batch_id":1,"title":"Python Basics","date":"2025-06-01","start_time":"09:00","end_time":"11:00"}'
```

### Mark attendance (student)
```bash
curl -X POST https://skillbridge-api-iuc9.onrender.com/attendance/mark \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_STUDENT_TOKEN" \
  -d '{"session_id":1,"status":"present"}'
```

### Get session attendance (trainer)
```bash
curl https://skillbridge-api-iuc9.onrender.com/sessions/1/attendance \
  -H "Authorization: Bearer YOUR_TRAINER_TOKEN"
```

### Batch summary (institution)
```bash
curl https://skillbridge-api-iuc9.onrender.com/batches/1/summary \
  -H "Authorization: Bearer YOUR_INSTITUTION_TOKEN"
```

### Institution summary (programme manager)
```bash
curl https://skillbridge-api-iuc9.onrender.com/institutions/1/summary \
  -H "Authorization: Bearer YOUR_PM_TOKEN"
```

### Programme-wide summary (programme manager)
```bash
curl https://skillbridge-api-iuc9.onrender.com/programme/summary \
  -H "Authorization: Bearer YOUR_PM_TOKEN"
```

---

## JWT Payload Structure

### Standard access token (all roles, 24h expiry)
```json
{
  "sub": "42",
  "role": "trainer",
  "exp": 1714086400
}
```

### Monitoring-scoped token (monitoring_officer only, 1h expiry)
```json
{
  "sub": "7",
  "role": "monitoring_officer",
  "type": "monitoring",
  "exp": 1714003600
}
```

The `"type": "monitoring"` claim is what separates it from a standard token. The `/monitoring/attendance` dependency explicitly rejects any token missing this claim — so even a valid 24h login token from a monitoring officer cannot access this endpoint. They must always go through the `/auth/monitoring-token` exchange first.

### Token rotation and revocation in production
Currently tokens cannot be revoked before expiry (standard JWT tradeoff). In production: add a `jti` (JWT ID) claim, maintain a Redis denylist, and check it on every request. Rotating the `MONITORING_API_KEY` immediately blocks new scoped tokens from being minted.

### One known security issue
The `MONITORING_API_KEY` is a static string in `.env`. If it leaks, anyone with a monitoring officer account can mint unlimited scoped tokens. Fix with more time: move to a secrets manager (AWS Secrets Manager / Vault) with rotation support and add `jti`-based revocation.

---

## Schema Decisions

### `batch_trainers` (many-to-many join table)
A batch can have multiple trainers and a trainer can teach multiple batches. A join table captures this without duplication. The composite primary key `(batch_id, trainer_id)` prevents duplicate assignments at the database level.

### `batch_invites`
Each invite is a UUID token with three properties:
- **Single-use** — `used` boolean flips to `True` after one student joins, preventing link sharing
- **Time-limited** — `expires_at` set by the trainer; expired tokens are rejected before any DB write
- **Traceable** — `created_by` stores the trainer's user ID for audit purposes

### Dual-token for Monitoring Officer
The monitoring officer has read-only but very wide access — every attendance record across all institutions. Two layers of defence:
1. **Standard JWT (24h)** — proves identity via email/password
2. **Scoped monitoring token (1h)** — proves possession of a separate API key; carries `type=monitoring`

A stolen standard JWT cannot access monitoring endpoints without the API key.

### Why `pg8000` instead of `psycopg2`
`pg8000` is a pure-Python PostgreSQL driver — no C compilation needed. This makes it install cleanly on Python 3.14 (local) and Render's build environment without needing system-level dependencies.

---

## What Is Working / Partial / Skipped

### Fully working
- All 13 endpoints with correct HTTP status codes
- RBAC enforced server-side on every protected endpoint
- JWT auth for all 5 roles (signup, login, token validation)
- Dual-token flow for Monitoring Officer
- Batch creation, UUID invite generation, student join via token (single-use + expiry check)
- Session creation with trainer-to-batch assignment verification
- Attendance marking with enrollment check (403 if not in batch)
- Batch, institution, and programme-wide summary endpoints
- 405 on POST/PUT/PATCH/DELETE to `/monitoring/attendance`
- Seed script: 2 institutions, 4 trainers, 15 students, 3 batches, 8 sessions, full attendance records
- 7 passing pytest tests (5 required + 2 bonus)
- Deployed live on Render with Neon PostgreSQL

### Partially done
- **Schema migrations:** tables created via `create_all()` at startup. Works for a prototype; production needs Alembic versioned migrations.
- **Pagination:** summary endpoints return all records. Large programmes need `limit`/`offset`.

### Skipped
- Email verification on signup
- Rate limiting on `/auth/login` (brute force protection)
- Refresh tokens (current JWTs non-revocable until expiry)

---

## One Thing I'd Do Differently

Add **Alembic migrations from day one**. Using `Base.metadata.create_all()` at startup is convenient but makes schema changes destructive in production. Alembic gives versioned, reversible migrations that run safely on a live database with zero downtime.

---

## Project Structure

```
skillbridge/
├── CONTACT.txt
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── render.yaml
├── scripts/
│   └── seed.py
├── src/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── dependencies.py
│   ├── db/
│   │   └── database.py
│   ├── models/
│   │   └── models.py
│   ├── schemas/
│   │   └── schemas.py
│   └── routers/
│       ├── auth.py
│       ├── batches.py
│       ├── sessions.py
│       ├── attendance.py
│       └── summaries.py
└── tests/
    ├── conftest.py
    └── test_api.py
```

---

## Stack

| Layer | Choice | Reason |
|---|---|---|
| Framework | FastAPI | Auto OpenAPI docs, type-safe, fast to build |
| ORM | SQLAlchemy 2.x | Explicit FK validation, clean relationship API |
| Auth | python-jose + bcrypt | Industry-standard JWT + secure password hashing |
| DB Driver | pg8000 | Pure Python — no C build needed, works on Python 3.14 |
| Database | Neon (PostgreSQL) | Free managed tier, serverless |
| Deployment | Render | Free tier, GitHub auto-deploy |
| Tests | pytest + SQLite | Real DB logic, no external service required for CI |