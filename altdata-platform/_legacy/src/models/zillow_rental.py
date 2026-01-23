"""Database models for Zillow rental data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, BigInteger,
    Index, ForeignKey, Date
)

from src.models.database import Base


class ZillowRentalIndex(Base):
    """Zillow Observed Rent Index (ZORI) data.

    Monthly rental price indices by metro area and property type.
    """
    __tablename__ = "zillow_rental_index"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    period = Column(Date, nullable=False, index=True)

    # Geography
    region_type = Column(String(20))  # national, state, metro, county, zip
    region_id = Column(String(20))  # Zillow region ID
    region_name = Column(String(200))
    state_code = Column(String(10))

    # Property type
    property_type = Column(String(50))  # all_homes, sfr, condo_coop, multifamily

    # ZORI metrics
    zori_value = Column(Float)  # Monthly rent index value
    mom_change = Column(Float)  # Month-over-month change
    yoy_change = Column(Float)  # Year-over-year change

    # Additional metrics
    median_listing_price = Column(Float)
    inventory_count = Column(Float)

    # Lineage
    raw_data_id = Column(BigInteger, ForeignKey("raw_data_catalog.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_zillow_period_region", "period", "region_type", "region_id"),
        Index("ix_zillow_property", "property_type"),
    )
