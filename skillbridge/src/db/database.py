import ssl
import re

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from src.core.config import settings


def _build_engine():
    db_url = settings.DATABASE_URL

    # Strip ?sslmode=require — pg8000 rejects this URL parameter
    db_url = re.sub(r'[?&]sslmode=[^&]*', '', db_url).rstrip('?').rstrip('&')

    # Pass SSL via connect_args instead (required for Neon cloud Postgres)
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    return create_engine(
        db_url,
        pool_pre_ping=True,
        connect_args={"ssl_context": ssl_ctx},
    )


engine = _build_engine()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()