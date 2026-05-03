# src/db/database.py
#
# PURPOSE: Set up the SQLAlchemy database connection.
# Everything database-related (engine creation, session lifecycle) lives here.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from src.core.config import settings

# ---------------------------------------------------------------------------
# ENGINE
# ---------------------------------------------------------------------------
# create_engine builds the connection pool.
# pool_pre_ping=True: before using a connection from the pool, SQLAlchemy
# sends a lightweight "SELECT 1" to check the connection is still alive.
# This prevents "connection closed" errors after Neon or Railway idle-timeout.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args={
        "ssl_context":True
    }
)

# ---------------------------------------------------------------------------
# SESSION FACTORY
# ---------------------------------------------------------------------------
# SessionLocal is a *class* (a factory). Calling SessionLocal() creates a new
# database session. Sessions are NOT thread-safe, so we create one per request.
SessionLocal = sessionmaker(
    autocommit=False,   # we control when commits happen
    autoflush=False,    # don't auto-flush before queries (we flush manually)
    bind=engine,
)

# ---------------------------------------------------------------------------
# BASE CLASS
# ---------------------------------------------------------------------------
# All ORM models will inherit from Base.
# DeclarativeBase (SQLAlchemy 2.x style) auto-registers the model's table.
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# DEPENDENCY: get_db
# ---------------------------------------------------------------------------
def get_db():
    """
    FastAPI dependency that yields a database session for one request.

    Usage in a route:
        @router.get("/something")
        def my_route(db: Session = Depends(get_db)):
            ...

    The try/finally guarantees the session is closed even if the route raises
    an exception. Without this, connections would leak back to the pool in a
    broken state.
    """
    db = SessionLocal()
    try:
        yield db        # FastAPI injects this db into the route function
    finally:
        db.close()      # always runs, even on exception
