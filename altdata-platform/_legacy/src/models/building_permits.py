"""Database models for building permit data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, Integer, BigInteger,
    Index, ForeignKey, Date, Numeric
)

from src.models.database import Base


class BuildingPermit(Base):
    """Building permit data from US Census and FRED.

    Monthly building permit data as construction leading indicator.
    """
    __tablename__ = "building_permits"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    period = Column(Date, nullable=False, index=True)

    # Geography
    geography_level = Column(String(20))  # national, state, county, msa
    geography_code = Column(String(20))  # FIPS code or state abbrev
    geography_name = Column(String(200))

    # Permit type
    permit_type = Column(String(50))  # total, single_family, multi_family_2_4, multi_family_5_plus

    # Metrics
    units_authorized = Column(Integer)
    valuation = Column(Numeric(15, 2))  # Total construction value in dollars

    # Seasonal adjustment
    is_seasonally_adjusted = Column(String(10))  # SA or NSA

    # Lineage
    raw_data_id = Column(BigInteger, ForeignKey("raw_data_catalog.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_permits_period_geo", "period", "geography_level", "geography_code"),
        Index("ix_permits_type", "permit_type"),
    )
