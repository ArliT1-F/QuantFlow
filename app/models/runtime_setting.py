"""
Runtime setting model for persisted mutable configuration.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func

from app.core.database import Base


class RuntimeSetting(Base):
    """Simple key/value store for runtime configuration."""

    __tablename__ = "runtime_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Float, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
