"""Database models for US Power Grid ISO data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, Integer, BigInteger,
    Boolean, Index, JSON, Enum as SQLEnum
)
import enum

from src.models.database import Base


class ISORegion(str, enum.Enum):
    """US Independent System Operator regions."""
    CAISO = "CAISO"  # California
    ERCOT = "ERCOT"  # Texas
    PJM = "PJM"      # Mid-Atlantic/Midwest
    MISO = "MISO"    # Midwest
    NYISO = "NYISO"  # New York
    ISONE = "ISONE"  # New England
    SPP = "SPP"      # Southwest Power Pool


class GridLoad(Base):
    """Real-time and historical grid load data."""
    __tablename__ = "grid_load"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    iso_region = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    load_mw = Column(Float, nullable=False)  # Current load in MW
    forecast_mw = Column(Float)  # Forecasted load
    capacity_mw = Column(Float)  # Available capacity
    load_forecast_delta = Column(Float)  # Actual - Forecast
    load_pct_of_capacity = Column(Float)  # Load as % of capacity
    raw_data_id = Column(BigInteger)

    __table_args__ = (
        Index("ix_grid_load_iso_time", "iso_region", "timestamp"),
        Index("ix_grid_load_time", "timestamp"),
    )


class GridPrice(Base):
    """Locational Marginal Prices (LMP) and wholesale prices."""
    __tablename__ = "grid_prices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    iso_region = Column(String(20), nullable=False, index=True)
    node_id = Column(String(50), index=True)  # Pricing node
    node_name = Column(String(255))
    timestamp = Column(DateTime(timezone=True), nullable=False)
    lmp_total = Column(Float)  # Total LMP $/MWh
    lmp_energy = Column(Float)  # Energy component
    lmp_congestion = Column(Float)  # Congestion component
    lmp_loss = Column(Float)  # Loss component
    raw_data_id = Column(BigInteger)

    __table_args__ = (
        Index("ix_grid_price_iso_node_time", "iso_region", "node_id", "timestamp"),
        Index("ix_grid_price_time", "timestamp"),
    )


class GenerationMix(Base):
    """Generation by fuel type."""
    __tablename__ = "generation_mix"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    iso_region = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    total_generation_mw = Column(Float)
    natural_gas_mw = Column(Float)
    coal_mw = Column(Float)
    nuclear_mw = Column(Float)
    hydro_mw = Column(Float)
    wind_mw = Column(Float)
    solar_mw = Column(Float)
    other_mw = Column(Float)
    imports_mw = Column(Float)
    renewable_pct = Column(Float)  # (wind + solar + hydro) / total
    raw_data_id = Column(BigInteger)

    __table_args__ = (
        Index("ix_gen_mix_iso_time", "iso_region", "timestamp"),
    )


class GridOutage(Base):
    """Planned and unplanned outages."""
    __tablename__ = "grid_outages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    iso_region = Column(String(20), nullable=False, index=True)
    outage_id = Column(String(50), unique=True)
    facility_name = Column(String(255))
    facility_type = Column(String(50))  # generator, transmission
    outage_type = Column(String(50))  # planned, forced, maintenance
    capacity_mw = Column(Float)
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    reason = Column(String(500))
    status = Column(String(50))  # active, completed, cancelled
    raw_data_id = Column(BigInteger)

    __table_args__ = (
        Index("ix_outage_iso_time", "iso_region", "start_time"),
        Index("ix_outage_status", "status"),
    )


class GridForecast(Base):
    """Load and generation forecasts."""
    __tablename__ = "grid_forecasts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    iso_region = Column(String(20), nullable=False, index=True)
    forecast_timestamp = Column(DateTime(timezone=True), nullable=False)  # When forecast was made
    target_timestamp = Column(DateTime(timezone=True), nullable=False)  # What time is forecasted
    forecast_type = Column(String(50))  # load, wind, solar
    forecast_mw = Column(Float)
    confidence_low = Column(Float)
    confidence_high = Column(Float)
    raw_data_id = Column(BigInteger)

    __table_args__ = (
        Index("ix_forecast_iso_target", "iso_region", "target_timestamp"),
        Index("ix_forecast_type", "forecast_type"),
    )
