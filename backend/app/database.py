"""Database engine and session setup.

Reads the connection string from the DATABASE_URL environment variable so the
same code works locally and inside Docker Compose. Defaults to a SQLite file if
the variable is not set. (Docker Compose points this at a file on a persisted
volume; the no-Docker local run uses a relative `sqlite:///./local.db`.)
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:////data/uptime.db",
)

# SQLite needs check_same_thread=False so the background scheduler thread can
# share the engine. The arg only applies to SQLite; other engines are unaffected.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# pool_pre_ping avoids stale connections after the DB container restarts.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
