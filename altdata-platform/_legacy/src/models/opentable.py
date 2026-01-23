"""Database models for OpenTable reservation data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, BigInteger,
    Index, ForeignKey, Date, UniqueConstraint
)

from src.models.database import Base


class OpenTableMetrics(Base):
    """OpenTable seated diners metrics.

    Weekly data comparing seated diners vs same period prior year.
    Sourced from OpenTable State of Industry reports.
    """
    __tablename__ = "opentable_metrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    week_ending = Column(Date, nullable=False, index=True)
    region = Column(String(100), nullable=False)  # US, UK, Germany, Australia, etc.
    city = Column(String(100))  # For city-level data if available

    # Metrics
    yoy_seated_diners_pct = Column(Float)  # e.g., +20 means 20% above last year

    # Lineage
    raw_data_id = Column(BigInteger, ForeignKey("raw_data_catalog.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_opentable_week_region", "week_ending", "region"),
        UniqueConstraint("week_ending", "region", "city", name="uq_opentable_week_region_city"),
    )
