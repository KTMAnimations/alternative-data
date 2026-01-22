"""Database models for OpenAQ air quality data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, Integer, BigInteger,
    Boolean, Index, JSON
)

from src.models.database import Base


class AirQualityLocation(Base):
    """Air quality monitoring locations."""
    __tablename__ = "air_quality_locations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    location_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255))
    city = Column(String(100), index=True)
    country = Column(String(100), index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    is_mobile = Column(Boolean, default=False)
    entity = Column(String(100))  # government, research, community
    sensor_type = Column(String(100))  # reference grade, low-cost sensor
    first_updated = Column(DateTime(timezone=True))
    last_updated = Column(DateTime(timezone=True))
    parameters = Column(JSON)  # List of measured parameters

    __table_args__ = (
        Index("ix_aq_location_city", "city"),
        Index("ix_aq_location_country", "country"),
        Index("ix_aq_location_coords", "latitude", "longitude"),
    )


class AirQualityMeasurement(Base):
    """Air quality measurements."""
    __tablename__ = "air_quality_measurements"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    location_id = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    parameter = Column(String(20), nullable=False, index=True)  # pm25, pm10, no2, so2, o3, co
    value = Column(Float, nullable=False)
    unit = Column(String(20))  # ug/m3, ppm, ppb
    averaging_period = Column(String(20))  # hour, day
    raw_data_id = Column(BigInteger)

    __table_args__ = (
        Index("ix_aq_measure_loc_time", "location_id", "timestamp"),
        Index("ix_aq_measure_param", "parameter"),
        Index("ix_aq_measure_time", "timestamp"),
    )


class AirQualityDaily(Base):
    """Daily aggregated air quality data."""
    __tablename__ = "air_quality_daily"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    location_id = Column(String(50), nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False)
    parameter = Column(String(20), nullable=False)
    avg_value = Column(Float)
    min_value = Column(Float)
    max_value = Column(Float)
    measurement_count = Column(Integer)
    unit = Column(String(20))

    __table_args__ = (
        Index("ix_aq_daily_loc_date", "location_id", "date"),
        Index("ix_aq_daily_param", "parameter"),
    )


class IndustrialZone(Base):
    """Industrial zones for air quality correlation."""
    __tablename__ = "industrial_zones"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    zone_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255))
    city = Column(String(100))
    state = Column(String(50))
    country = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)
    radius_km = Column(Float, default=10.0)
    zone_type = Column(String(50))  # manufacturing, refinery, port
    associated_companies = Column(JSON)  # List of entity IDs

    __table_args__ = (
        Index("ix_ind_zone_location", "latitude", "longitude"),
    )
