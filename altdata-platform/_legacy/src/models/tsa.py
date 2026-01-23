"""Database models for TSA checkpoint data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, Integer, BigInteger,
    Index, ForeignKey, Date, Boolean
)

from src.models.database import Base


class TSACheckpoint(Base):
    """TSA checkpoint throughput data.

    Daily passenger counts from TSA checkpoint screenings.
    Released by 9am next day, high correlation with airline enplanements.
    """
    __tablename__ = "tsa_checkpoints"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)

    # Throughput data
    current_year_throughput = Column(Integer)  # Total travelers screened
    prior_year_throughput = Column(Integer)  # Same day prior year
    yoy_change_pct = Column(Float)  # Year-over-year percentage change

    # Derived fields
    day_of_week = Column(Integer)  # 0=Monday, 6=Sunday
    is_holiday_period = Column(Boolean, default=False)

    # Lineage
    raw_data_id = Column(BigInteger, ForeignKey("raw_data_catalog.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_tsa_date", "date", unique=True),
        Index("ix_tsa_date_dow", "date", "day_of_week"),
    )
