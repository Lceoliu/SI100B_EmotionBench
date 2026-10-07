from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.env import DATABASE_URL


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema() -> None:
    """Add columns introduced after a database was first created (SQLite has no migrations here)."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(users)")).mappings().all()
        column_names = {row["name"] for row in rows}
        if rows and "group_name" not in column_names:
            conn.execute(text("ALTER TABLE users ADD COLUMN group_name VARCHAR(120) DEFAULT '' NOT NULL"))
        if rows and "disabled" not in column_names:
            conn.execute(text("ALTER TABLE users ADD COLUMN disabled BOOLEAN DEFAULT 0 NOT NULL"))
        if rows and "submit_disabled" not in column_names:
            conn.execute(text("ALTER TABLE users ADD COLUMN submit_disabled BOOLEAN DEFAULT 0 NOT NULL"))
        if rows and "leaderboard_hidden" not in column_names:
            conn.execute(text("ALTER TABLE users ADD COLUMN leaderboard_hidden BOOLEAN DEFAULT 0 NOT NULL"))
        if rows and "quota_reset_at" not in column_names:
            conn.execute(text("ALTER TABLE users ADD COLUMN quota_reset_at DATETIME"))
        rows = conn.execute(text("PRAGMA table_info(submissions)")).mappings().all()
        submission_columns = {row["name"] for row in rows}
        if rows and "mode" not in submission_columns:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN mode VARCHAR(24) DEFAULT 'public' NOT NULL"))
        if rows and "model_format" not in submission_columns:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN model_format VARCHAR(24) DEFAULT 'onnx' NOT NULL"))
        if rows and "input_size" not in submission_columns:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN input_size INTEGER DEFAULT 224 NOT NULL"))
        if rows and "input_channels" not in submission_columns:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN input_channels INTEGER DEFAULT 3 NOT NULL"))
        if rows and "onnx_input_name" not in submission_columns:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN onnx_input_name VARCHAR(255) DEFAULT '' NOT NULL"))
        if rows and "onnx_opset" not in submission_columns:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN onnx_opset INTEGER DEFAULT 0 NOT NULL"))
        if rows and "model_metadata_json" not in submission_columns:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN model_metadata_json TEXT DEFAULT '{}' NOT NULL"))
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS settings ("
                "key VARCHAR(120) PRIMARY KEY, "
                "value TEXT DEFAULT '' NOT NULL, "
                "updated_at DATETIME"
                ")"
            )
        )
