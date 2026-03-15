from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import json
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
    _migrate_legacy_single_user_data()


def _ensure_sqlite_compat_schema():
    """Patch SQLite schema for newly added columns/indexes in local dev.

    This keeps local DB usable even if alembic migrations were not run.
    """
    if "sqlite" not in DATABASE_URL:
        return

    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS users ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "username VARCHAR(80) NOT NULL UNIQUE, "
            "password VARCHAR(128) NOT NULL, "
            "created_at DATETIME)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS user_sessions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user_id INTEGER NOT NULL, "
            "token VARCHAR(128) NOT NULL UNIQUE, "
            "created_at DATETIME, "
            "last_seen_at DATETIME)"
        )
        cols = conn.exec_driver_sql("PRAGMA table_info(tasks)").fetchall()
        col_names = {row[1] for row in cols}

        if "user_id" not in col_names:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN user_id INTEGER DEFAULT 1")
        if "source" not in col_names:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN source VARCHAR(20) DEFAULT 'manual'")
        if "task_kind" not in col_names:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN task_kind VARCHAR(20) DEFAULT 'temporary'")
        if "recurrence_weekday" not in col_names:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN recurrence_weekday INTEGER")
        if "decision_reason" not in col_names:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN decision_reason TEXT DEFAULT ''")
        if "completed_at" not in col_names:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN completed_at DATETIME")
        if "deleted_at" not in col_names:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN deleted_at DATETIME")
        if "sort_order" not in col_names:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN sort_order INTEGER DEFAULT 0")
        if "due_date" not in col_names:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN due_date VARCHAR(10)")

        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(token)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_tasks_sort_order ON tasks(sort_order)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_daily_plans_date ON daily_plans(date)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_task_history_date ON task_history(date)")

        # ── User table new columns ──
        user_cols = conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
        user_col_names = {row[1] for row in user_cols}
        if "birthday" not in user_col_names:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN birthday VARCHAR(10)")
        if "gender" not in user_col_names:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN gender VARCHAR(20)")

        # ── New tables ──
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS mood_entries ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user_id INTEGER NOT NULL, "
            "date VARCHAR(10) NOT NULL, "
            "mood_level INTEGER NOT NULL, "
            "note TEXT DEFAULT '', "
            "created_at DATETIME)"
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_mood_entries_user_date ON mood_entries(user_id, date)")

        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS daily_fortunes ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user_id INTEGER NOT NULL, "
            "date VARCHAR(10) NOT NULL, "
            "fortune_data TEXT DEFAULT '{}', "
            "created_at DATETIME)"
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_daily_fortunes_user_date ON daily_fortunes(user_id, date)")

        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS focus_sessions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user_id INTEGER NOT NULL, "
            "task_id INTEGER, "
            "date VARCHAR(10) NOT NULL, "
            "duration_minutes INTEGER NOT NULL, "
            "session_type VARCHAR(10) DEFAULT 'work', "
            "created_at DATETIME)"
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_focus_sessions_user_date ON focus_sessions(user_id, date)")


def _migrate_legacy_single_user_data():
    if "sqlite" not in DATABASE_URL:
        return

    with engine.begin() as conn:
        rows = conn.exec_driver_sql(
            "SELECT key, value FROM app_settings WHERE key IN ('prototype_onboarding', 'prototype_session')"
        ).fetchall()
        raw = {key: value for key, value in rows}
        legacy_onboarding = None
        legacy_session = None
        try:
            legacy_onboarding = json.loads(raw.get("prototype_onboarding", "")) if raw.get("prototype_onboarding") else None
        except json.JSONDecodeError:
            legacy_onboarding = None
        try:
            legacy_session = json.loads(raw.get("prototype_session", "")) if raw.get("prototype_session") else None
        except json.JSONDecodeError:
            legacy_session = None

        legacy_name = ""
        legacy_password = "changeme"
        if isinstance(legacy_session, dict) and legacy_session.get("display_name") and legacy_session.get("password"):
            legacy_name = str(legacy_session["display_name"]).strip()
            legacy_password = str(legacy_session["password"]).strip() or legacy_password
        elif isinstance(legacy_onboarding, dict):
            summary = str(legacy_onboarding.get("profile_summary", "")).strip()
            if " imported " in summary:
                legacy_name = summary.split(" imported ", 1)[0].strip()
        if not legacy_name:
            legacy_name = "legacy"

        user_row = conn.exec_driver_sql(
            "SELECT id, username FROM users WHERE username = ? LIMIT 1",
            (legacy_name,),
        ).fetchone()
        if user_row:
            legacy_user_id = int(user_row[0])
        else:
            conn.exec_driver_sql(
                "INSERT INTO users(username, password, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (legacy_name, legacy_password),
            )
            legacy_user_id = int(
                conn.exec_driver_sql("SELECT id FROM users WHERE username = ?", (legacy_name,)).fetchone()[0]
            )

        unnamed_plans = conn.exec_driver_sql(
            "SELECT id, date FROM daily_plans WHERE instr(date, ':') = 0"
        ).fetchall()
        if unnamed_plans:
            conn.exec_driver_sql(
                "UPDATE tasks SET user_id = ? WHERE user_id = 1",
                (legacy_user_id,),
            )
            for plan_id, plan_date in unnamed_plans:
                conn.exec_driver_sql(
                    "UPDATE daily_plans SET date = ? WHERE id = ?",
                    (f"{legacy_user_id}:{plan_date}", int(plan_id)),
                )

        if isinstance(legacy_onboarding, dict):
            onboarding_key = f"prototype_onboarding:{legacy_user_id}"
            existing = conn.exec_driver_sql(
                "SELECT value FROM app_settings WHERE key = ? LIMIT 1",
                (onboarding_key,),
            ).fetchone()
            if not existing:
                conn.exec_driver_sql(
                    "INSERT INTO app_settings(key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (onboarding_key, json.dumps(legacy_onboarding, ensure_ascii=False)),
                )


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
