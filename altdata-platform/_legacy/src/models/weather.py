"""Database models for weather data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, Integer, BigInteger,
    Index, JSON, Text, Date
)

from src.models.database import Base


class WeatherObservation(Base):
    """Historical and current weather observations."""
    __tablename__ = "weather_observations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    location_id = Column(String(50), nullable=False, index=True)  # city_country
    city = Column(String(100), index=True)
    country = Column(String(10), index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Temperature
    temp_c = Column(Float)
    temp_feels_like_c = Column(Float)
    temp_min_c = Column(Float)
    temp_max_c = Column(Float)

    # Conditions
    humidity_pct = Column(Integer)
    pressure_hpa = Column(Integer)
    visibility_m = Column(Integer)
    cloud_cover_pct = Column(Integer)

    # Wind
    wind_speed_ms = Column(Float)
    wind_gust_ms = Column(Float)
    wind_direction_deg = Column(Integer)

    # Precipitation
    rain_1h_mm = Column(Float)
    rain_3h_mm = Column(Float)
    snow_1h_mm = Column(Float)
    snow_3h_mm = Column(Float)

    # Descriptors
    weather_main = Column(String(50))  # Clear, Clouds, Rain, Snow
    weather_description = Column(String(100))
    weather_icon = Column(String(10))

    raw_data_id = Column(BigInteger)

    __table_args__ = (
        Index("ix_weather_obs_loc_time", "location_id", "timestamp"),
        Index("ix_weather_obs_city", "city"),
    )


class WeatherForecast(Base):
    """Weather forecasts for planning signals."""
    __tablename__ = "weather_forecasts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    location_id = Column(String(50), nullable=False, index=True)
    city = Column(String(100))
    country = Column(String(10))
    latitude = Column(Float)
    longitude = Column(Float)

    forecast_timestamp = Column(DateTime(timezone=True), nullable=False)  # When forecast is for
    fetched_at = Column(DateTime(timezone=True), nullable=False)  # When we got it

    temp_c = Column(Float)
    temp_feels_like_c = Column(Float)
    humidity_pct = Column(Integer)
    cloud_cover_pct = Column(Integer)
    wind_speed_ms = Column(Float)
    pop = Column(Float)  # Probability of precipitation
    rain_mm = Column(Float)
    snow_mm = Column(Float)
    weather_main = Column(String(50))

    __table_args__ = (
        Index("ix_weather_fcst_loc_time", "location_id", "forecast_timestamp"),
    )


class WeatherAlert(Base):
    """Severe weather alerts."""
    __tablename__ = "weather_alerts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    location_id = Column(String(50), index=True)
    alert_id = Column(String(100), unique=True, index=True)
    sender = Column(String(255))
    event = Column(String(100), index=True)  # Hurricane, Tornado, Flood, etc.
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    description = Column(Text)
    severity = Column(String(20))  # Minor, Moderate, Severe, Extreme
    affected_zones = Column(JSON)

    __table_args__ = (
        Index("ix_weather_alert_event", "event"),
        Index("ix_weather_alert_time", "start_time", "end_time"),
    )


class WeatherDaily(Base):
    """Daily aggregated weather data."""
    __tablename__ = "weather_daily"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    location_id = Column(String(50), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)

    temp_avg_c = Column(Float)
    temp_min_c = Column(Float)
    temp_max_c = Column(Float)
    humidity_avg_pct = Column(Integer)
    precipitation_mm = Column(Float)
    snow_mm = Column(Float)
    wind_avg_ms = Column(Float)
    cloud_cover_avg_pct = Column(Integer)

    # Degree days
    heating_degree_days = Column(Float)  # base 18C
    cooling_degree_days = Column(Float)  # base 18C

    __table_args__ = (
        Index("ix_weather_daily_loc_date", "location_id", "date"),
    )
