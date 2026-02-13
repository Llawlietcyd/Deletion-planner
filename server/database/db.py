from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import os

from database.models import Base

# Database configuration — defaults to SQLite, can switch to MySQL via env var
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///deletion_planner.db"
)

engine = create_engine(
    DATABASE_URL,
    echo=False,
    # SQLite needs check_same_thread=False for Flask's threaded mode
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db():
    """Context manager that yields a database session and handles cleanup."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
