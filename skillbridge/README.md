# SkillBridge Attendance API

Backend REST API for a fictional state-level skilling programme. Built with FastAPI, PostgreSQL (Neon), and deployed on Render/Railway.

---

## 1. Live API Base URL

```
https://YOUR-APP-NAME.onrender.com
```

> Replace this with your actual URL after deployment. All curl examples below use `$BASE` as a placeholder.

```bash
export BASE=https://YOUR-APP-NAME.onrender.com
```

---

## 2. Local Setup (from scratch)

Assumes Python 3.10+ and pip are installed.

```bash
# 1. Clone the repo
git clone https://github.com/YOUR-USERNAME/skillbridge.git
cd skillbridge

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and fill in .env
cp .env.example .env
# Edit .env — set DATABASE_URL to your Neon connection string
# and generate a SECRET_KEY:
python -c "import secrets; print(secrets.token_hex(32))"

# 5. Create tables + seed data
python scripts/seed.py

# 6. Run the server
uvicorn src.main:app --reload

# API is now at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

---

## 3. Test Accounts (all seeded by scripts/seed.py)

| Role               | Email                            | Password          |
|--------------------|----------------------------------|-------------------|
| student            | student1@skillbridge.test        | student_pass123   |
| trainer            | trainer1@skillbridge.test        | trainer_pass123   |
| institution        | admin_kzd@skillbridge.test       | admin_pass123     |
| programme_manager  | pm@skillbridge.test              | pm_pass123        |
| monitoring_officer | monitor@skillbridge.test         | monitor_pass123   |

---

## 4. Sample curl Commands

### Auth

```bash
# Signup
curl -X POST $BASE/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"new@test.com","password":"pass123","role":"student"}'

# Login (get TOKEN)
TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"student1@skillbridge.test","password":"student_pass123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Student token: $TOKEN"

# Get monitoring-scoped token (2-step)
# Step 1: Login as monitoring officer
MO_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"monitor@skillbridge.test","password":"monitor_pass123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Step 2: Exchange for scoped token
SCOPED=$(curl -s -X POST $BASE/auth/monitoring-token \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MO_TOKEN" \
  -d '{"key":"monitoring-secret-api-key-2024"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Monitoring scoped token: $SCOPED"
```

### Batches

```bash
# Create batch (trainer/institution)
TRAINER_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"trainer1@skillbridge.test","password":"trainer_pass123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X POST $BASE/batches \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -d '{"name":"New Batch","institution_id":1}'

# Create invite for batch 1
curl -X POST $BASE/batches/1/invite \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -d '{"expires_at":"2025-12-31T23:59:59Z"}'

# Student joins batch using token (replace TOKEN-HERE with invite token from above)
curl -X POST $BASE/batches/join \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -d '{"token":"TOKEN-HERE"}'
```

### Sessions

```bash
# Create session
curl -X POST $BASE/sessions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TRAINER_TOKEN" \
  -d '{"batch_id":1,"title":"Python Basics","date":"2025-06-01","start_time":"09:00","end_time":"11:00"}'

# Get attendance for session 1
curl $BASE/sessions/1/attendance \
  -H "Authorization: Bearer $TRAINER_TOKEN"
```

### Attendance

```bash
# Mark attendance (student)
curl -X POST $BASE/attendance/mark \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -d '{"session_id":1,"status":"present"}'
```

### Summaries

```bash
ADMIN_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin_kzd@skillbridge.test","password":"admin_pass123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

PM_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"pm@skillbridge.test","password":"pm_pass123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Batch summary (institution role)
curl $BASE/batches/1/summary -H "Authorization: Bearer $ADMIN_TOKEN"

# Institution summary (programme manager)
curl $BASE/institutions/1/summary -H "Authorization: Bearer $PM_TOKEN"

# Programme-wide summary
curl $BASE/programme/summary -H "Authorization: Bearer $PM_TOKEN"

# Monitoring endpoint (scoped token required)
curl $BASE/monitoring/attendance -H "Authorization: Bearer $SCOPED"
```

---

## 5. Schema Decisions

### batch_trainers (many-to-many)
A batch can have multiple trainers and a trainer can be in multiple batches. Using a join table (rather than a FK on `batches`) captures this without data duplication. The composite PK `(batch_id, trainer_id)` prevents duplicate assignments.

### batch_invites
Each invite is a UUID token that is single-use (`used` boolean) and time-limited (`expires_at`). Single-use prevents token sharing — each student must get their own invite. The trainer controls expiry, making short-lived invites possible for time-sensitive enrollment windows.

### Dual-token for Monitoring Officer
The monitoring officer has read-only but extremely broad access (all data, all institutions). To defend this, we require two factors:
1. Standard JWT (proves identity via email/password)  
2. Scoped monitoring token (proves possession of an API key + has 1-hour expiry vs 24 hours)

The scoped token carries `"type": "monitoring"` as a claim. The `GET /monitoring/attendance` dependency explicitly rejects any token without this claim, so a stolen standard JWT cannot access monitoring endpoints.

### Why SQLAlchemy ORM over raw SQL?
Explicit FK relationships let SQLAlchemy catch missing related objects before the DB does (we raise 404 rather than letting a FK violation bubble up as 500). It also makes the codebase more readable and testable.

---

## 6. What Is Working / Partial / Skipped

### Fully working
- All 5 auth flows (signup, login, monitoring token exchange)
- RBAC enforced on every protected endpoint
- Batch creation, invite generation, student join-via-token
- Session creation with trainer-batch assignment check
- Attendance marking with enrollment verification
- All summary endpoints (batch, institution, programme, monitoring)
- 405 on non-GET verbs to `/monitoring/attendance`
- Seed script (2 institutions, 4 trainers, 15 students, 3 batches, 8 sessions, full attendance)
- 7 passing pytest tests (5 required + 2 bonus)

### Partially done
- Alembic migrations: tables are created with `create_all()` on startup. Works fine for a prototype; for production you'd want versioned migrations.
- Pagination: summary endpoints return all data. A large programme would need `limit`/`offset`.

### Skipped
- Email verification on signup
- Rate limiting on login endpoint (brute force protection)
- Refresh tokens (current tokens are non-revocable until expiry)

---

## 7. One Thing I'd Do Differently With More Time

I'd add Alembic migrations from the start. Using `Base.metadata.create_all()` is fine for prototyping but makes schema changes destructive — you either drop all tables or run raw SQL by hand. Alembic gives you versioned, reversible schema migrations, which is how every production app manages schema evolution.

---

## JWT Payload Structure

### Standard access token (all roles)
```json
{
  "sub": "42",
  "role": "trainer",
  "exp": 1714086400,
  "iat": 1714000000
}
```

### Monitoring-scoped token (monitoring_officer only)
```json
{
  "sub": "7",
  "role": "monitoring_officer",
  "type": "monitoring",
  "exp": 1714003600
}
```

### Token rotation / revocation in production
In the current implementation, tokens cannot be revoked before expiry — this is the standard JWT tradeoff. To support revocation, I'd maintain a Redis set of revoked `jti` (JWT ID) claims and check it on every request. For the monitoring-scoped token, rotating the `MONITORING_API_KEY` immediately invalidates the ability to mint new scoped tokens (existing ones live out their 1-hour window).

### One security issue in the current implementation
The `MONITORING_API_KEY` is a static string stored in `.env`. If it leaks, an attacker with any monitoring officer account can mint unlimited scoped tokens. Fix: implement key rotation via a secrets manager (AWS Secrets Manager, HashiCorp Vault) so the key can be changed without redeployment, and add a `jti` claim with a Redis denylist to immediately invalidate outstanding tokens on rotation.

---

## Deployment Notes (Render)

1. Push code to GitHub (make sure `.env` is in `.gitignore`)
2. Create a new Web Service on [render.com](https://render.com)
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `uvicorn src.main:app --host 0.0.0.0 --port $PORT`
5. Add all env vars from `.env.example` in the Render dashboard under Environment
6. After first deploy, run the seed script via Render Shell: `python scripts/seed.py`

Neon PostgreSQL: create a free project at [neon.tech](https://neon.tech), copy the connection string, set it as `DATABASE_URL`.
