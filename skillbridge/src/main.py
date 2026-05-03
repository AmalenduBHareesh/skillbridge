# src/main.py
#
# PURPOSE: Create the FastAPI app, configure middleware, register routers,
#          and create all database tables on startup.
#
# This is the file uvicorn runs: `uvicorn src.main:app --reload`

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import Base and engine so we can create tables
from src.db.database import Base, engine

# Import all models so SQLAlchemy knows about them when create_all() is called.
# If you don't import them here, the tables won't be created even if the models exist.
import src.models.models  # noqa: F401 — side-effect import

# Import all routers
from src.routers import auth, batches, sessions, attendance, summaries


# ---------------------------------------------------------------------------
# CREATE ALL TABLES
# ---------------------------------------------------------------------------
# This runs at import time (when uvicorn loads main.py).
# Base.metadata.create_all looks at every class that inherited Base and
# creates its table if it doesn't exist yet.
# For production you'd use Alembic migrations instead, but for a prototype
# this is simpler.
Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------------------
# APP INSTANCE
# ---------------------------------------------------------------------------
app = FastAPI(
    title="SkillBridge Attendance API",
    description=(
        "Backend API for a fictional state-level skilling programme. "
        "Supports 5 user roles with role-based access control and JWT auth."
    ),
    version="1.0.0",
    # FastAPI auto-generates OpenAPI docs at /docs (Swagger UI) and /redoc
)


# ---------------------------------------------------------------------------
# CORS MIDDLEWARE
# ---------------------------------------------------------------------------
# CORS (Cross-Origin Resource Sharing) lets browsers on different domains
# call this API. For a prototype we allow all origins.
# In production: restrict allow_origins to your frontend's domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # any origin — restrict in production
    allow_credentials=True,
    allow_methods=["*"],       # GET, POST, PUT, etc.
    allow_headers=["*"],       # Authorization header etc.
)


# ---------------------------------------------------------------------------
# REGISTER ROUTERS
# ---------------------------------------------------------------------------
# Each router has its own prefix so routes don't collide.
# Tags group routes in the Swagger docs.

app.include_router(auth.router)         # /auth/signup, /auth/login, /auth/monitoring-token
app.include_router(batches.router)      # /batches, /batches/{id}/invite, /batches/join
app.include_router(sessions.router)     # /sessions, /sessions/{id}/attendance
app.include_router(attendance.router)   # /attendance/mark
app.include_router(summaries.router)    # /batches/{id}/summary, /institutions/{id}/summary, etc.


# ---------------------------------------------------------------------------
# ROOT ENDPOINT
# ---------------------------------------------------------------------------
@app.get("/", tags=["health"])
def root():
    """Health check / welcome endpoint."""
    return {
        "message": "SkillBridge Attendance API is running.",
        "docs": "/docs",
        "redoc": "/redoc",
    }


# ---------------------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
def health():
    """Lightweight health check for deployment platforms."""
    return {"status": "ok"}
