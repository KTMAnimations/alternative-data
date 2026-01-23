"""Database models for earthquake and seismic data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, BigInteger,
    Index, ForeignKey, Boolean
)

from src.models.database import Base


class EarthquakeEvent(Base):
    """Earthquake event data from USGS.

    Real-time seismic events for insurance, supply chain,
    and economic impact analysis.
    """
    __tablename__ = "earthquake_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(String(50), nullable=False, unique=True, index=True)

    # Event timing
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    updated = Column(DateTime(timezone=True))

    # Location
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    depth_km = Column(Float)  # Depth in kilometers
    place_description = Column(String(500))  # Human-readable location

    # Magnitude
    magnitude = Column(Float, index=True)
    magnitude_type = Column(String(10))  # ml, mb, mw, etc.

    # Impact indicators
    felt_reports = Column(BigInteger)  # Number of DYFI reports
    cdi = Column(Float)  # Community Determined Intensity (max reported)
    mmi = Column(Float)  # Modified Mercalli Intensity (estimated)
    alert_level = Column(String(10))  # green, yellow, orange, red
    tsunami_flag = Column(Boolean, default=False)

    # Data quality
    status = Column(String(20))  # automatic, reviewed, deleted
    net = Column(String(10))  # Contributing network (us, nc, ci, etc.)
    nst = Column(BigInteger)  # Number of seismic stations
    dmin = Column(Float)  # Distance to nearest station (degrees)
    rms = Column(Float)  # Root mean square travel time residual
    gap = Column(Float)  # Azimuthal gap (degrees)

    # URLs for additional info
    detail_url = Column(String(500))

    # Lineage
    raw_data_id = Column(BigInteger, ForeignKey("raw_data_catalog.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_earthquake_timestamp", "timestamp"),
        Index("ix_earthquake_mag_time", "magnitude", "timestamp"),
        Index("ix_earthquake_location", "latitude", "longitude"),
    )


class SeismicZone(Base):
    """Geographic seismic zones for risk analysis."""
    __tablename__ = "seismic_zones"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    zone_id = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)

    # Bounding box
    min_latitude = Column(Float)
    max_latitude = Column(Float)
    min_longitude = Column(Float)
    max_longitude = Column(Float)

    # Risk classification
    risk_level = Column(String(20))  # low, moderate, high, very_high
    historical_max_magnitude = Column(Float)

    # Related tickers (JSON list of affected tickers)
    affected_sectors = Column(String(500))  # comma-separated

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
