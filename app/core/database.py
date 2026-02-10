"""
Database configuration and session management
"""
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
from typing import AsyncGenerator
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create database engine
if "sqlite" in settings.DATABASE_URL:
    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        echo=False
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

async def init_db():
    """Initialize database by validating Alembic revision state."""
    project_root = Path(__file__).resolve().parents[2]
    alembic_ini = project_root / "alembic.ini"
    alembic_dir = project_root / "alembic"

    if not alembic_ini.exists() or not alembic_dir.exists():
        raise RuntimeError("Alembic configuration is missing. Cannot initialize database safely.")

    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(alembic_dir))
    script = ScriptDirectory.from_config(alembic_cfg)
    heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError("Expected a single Alembic head revision.")
    expected_head = heads[0]

    current_revision = None
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
            current_revision = row[0] if row else None
    except SQLAlchemyError:
        current_revision = None

    if current_revision != expected_head:
        raise RuntimeError(
            f"Database revision mismatch. Current={current_revision}, Expected={expected_head}. "
            "Run `venv/bin/python -m alembic upgrade head` before starting the app."
        )
    logger.info("Database revision verified at head: %s", expected_head)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_async_db() -> AsyncGenerator:
    """Get database session for async endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
