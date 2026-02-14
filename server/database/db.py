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
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_compat_schema()


def _ensure_sqlite_compat_schema():
    """Patch SQLite schema for newly added columns/indexes in local dev.

    This keeps local DB usable even if alembic migrations were not run.
    """
    if "sqlite" not in DATABASE_URL:
        return

    with engine.begin() as conn:
        cols = conn.exec_driver_sql("PRAGMA table_info(tasks)").fetchall()
        col_names = {row[1] for row in cols}

        if "source" not in col_names:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN source VARCHAR(20) DEFAULT 'manual'")
        if "decision_reason" not in col_names:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN decision_reason TEXT DEFAULT ''")
        if "completed_at" not in col_names:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN completed_at DATETIME")
        if "deleted_at" not in col_names:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN deleted_at DATETIME")
        if "sort_order" not in col_names:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN sort_order INTEGER DEFAULT 0")

        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_tasks_sort_order ON tasks(sort_order)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_daily_plans_date ON daily_plans(date)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_task_history_date ON task_history(date)")


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
