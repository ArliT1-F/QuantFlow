"""
Alert model for notifications and alerts
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON
from sqlalchemy.sql import func
from app.core.database import Base

class Alert(Base):
    """Alert model for notifications"""
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String(50), nullable=False)  # TRADE, PRICE, PORTFOLIO, etc.
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    symbol = Column(String(10), nullable=True, index=True)
    price = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)
    status = Column(String(20), default="PENDING")  # PENDING, SENT, FAILED
    priority = Column(String(10), default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sent_at = Column(DateTime(timezone=True), nullable=True)
    metadata = Column(JSON, nullable=True)
    
class AlertRule(Base):
    """Alert rule model for automated alerts"""
    __tablename__ = "alert_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    alert_type = Column(String(50), nullable=False)
    symbol = Column(String(10), nullable=True)
    condition = Column(String(100), nullable=False)  # price > 100, volume > 1000000
    threshold = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())