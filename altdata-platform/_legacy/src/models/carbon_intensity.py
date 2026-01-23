"""Database models for carbon intensity data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, BigInteger,
    Index, ForeignKey, JSON
)

from src.models.database import Base


class CarbonIntensityReading(Base):
    """UK Carbon Intensity data.

    30-minute interval carbon intensity readings from UK National Grid.
    Useful for ESG signals and energy transition tracking.
    """
    __tablename__ = "carbon_intensity_readings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Region (UK national or regional codes)
    region = Column(String(50), default="national")

    # Intensity values
    intensity_forecast = Column(Float)  # gCO2/kWh (forecasted)
    intensity_actual = Column(Float)  # gCO2/kWh (actual)
    intensity_index = Column(String(20))  # very low, low, moderate, high, very high

    # Generation mix (percentage breakdown)
    generation_mix = Column(JSON)  # {"biomass": %, "coal": %, "gas": %, etc.}

    # Individual fuel percentages for faster querying
    pct_biomass = Column(Float)
    pct_coal = Column(Float)
    pct_gas = Column(Float)
    pct_hydro = Column(Float)
    pct_imports = Column(Float)
    pct_nuclear = Column(Float)
    pct_solar = Column(Float)
    pct_wind = Column(Float)
    pct_other = Column(Float)

    # Lineage
    raw_data_id = Column(BigInteger, ForeignKey("raw_data_catalog.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_carbon_timestamp_region", "timestamp", "region"),
    )
