"""Data source models for all collectors."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SQLEnum,
    Float,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class DataSourceCategory(str, Enum):
    """Categories for data sources."""

    TRAVEL = "travel"
    REAL_ESTATE = "real_estate"
    ENERGY = "energy"
    GAMING = "gaming"
    GOVERNMENT = "government"
    INFRASTRUCTURE = "infrastructure"
    ENTERTAINMENT = "entertainment"
    INTERNET = "internet"


class UpdateFrequency(str, Enum):
    """Update frequency for data sources."""

    CONTINUOUS = "continuous"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class SaturationLevel(str, Enum):
    """Market saturation level."""

    NOVEL = "novel"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DataSource(Base, TimestampMixin):
    """Metadata about data sources."""

    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[DataSourceCategory] = mapped_column(
        SQLEnum(DataSourceCategory), nullable=False
    )
    update_frequency: Mapped[UpdateFrequency] = mapped_column(
        SQLEnum(UpdateFrequency), nullable=False
    )
    latency_hours: Mapped[float] = mapped_column(Float, nullable=False)
    is_real_time: Mapped[bool] = mapped_column(Boolean, default=False)
    saturation_level: Mapped[SaturationLevel] = mapped_column(
        SQLEnum(SaturationLevel), default=SaturationLevel.NOVEL
    )
    primary_entities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    geographic_coverage: Mapped[str] = mapped_column(String(200), nullable=True)
    date_range_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_range_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    api_documentation_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    archived_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class TSACheckpoint(Base, TimestampMixin):
    """TSA passenger throughput data."""

    __tablename__ = "tsa_checkpoints"
    __table_args__ = (
        UniqueConstraint("date", name="uq_tsa_date"),
        Index("ix_tsa_date_dow", "date", "day_of_week"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    current_year_throughput: Mapped[int] = mapped_column(Integer, nullable=False)
    prior_year_throughput: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    yoy_change_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday
    is_holiday_period: Mapped[bool] = mapped_column(Boolean, default=False)
    data_quality_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=1.0
    )
    revision_status: Mapped[str] = mapped_column(
        String(20), default="original"
    )  # original, revised


class OpenTableMetrics(Base, TimestampMixin):
    """OpenTable seated diners metrics."""

    __tablename__ = "opentable_metrics"
    __table_args__ = (
        UniqueConstraint("week_ending", "region", "city", name="uq_opentable_week_region_city"),
        Index("ix_opentable_week_region", "week_ending", "region"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    week_ending: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(50), nullable=False)  # US, UK, Germany, etc.
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    yoy_seated_diners_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    wow_change_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    data_quality_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=1.0)


class EarthquakeEvent(Base, TimestampMixin):
    """USGS earthquake event data."""

    __tablename__ = "earthquake_events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_earthquake_event_id"),
        Index("ix_earthquake_timestamp", "timestamp"),
        Index("ix_earthquake_magnitude", "magnitude"),
        Index("ix_earthquake_location", "latitude", "longitude"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    depth_km: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    magnitude: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    magnitude_type: Mapped[str] = mapped_column(String(10), nullable=False)  # ml, mb, mw, etc.
    place_description: Mapped[str] = mapped_column(String(500), nullable=False)
    felt_reports: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tsunami_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # green, yellow, orange, red
    estimated_population_exposure: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_economic_impact_usd: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True
    )


class CarbonIntensityReading(Base, TimestampMixin):
    """UK grid carbon intensity data."""

    __tablename__ = "carbon_intensity_readings"
    __table_args__ = (
        UniqueConstraint("timestamp", "region", name="uq_carbon_timestamp_region"),
        Index("ix_carbon_timestamp", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    region: Mapped[str] = mapped_column(String(50), nullable=False)  # national or region code
    intensity_forecast: Mapped[int] = mapped_column(Integer, nullable=False)  # gCO2/kWh
    intensity_actual: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    intensity_index: Mapped[str] = mapped_column(String(20), nullable=False)  # very low, low, moderate, high, very high
    generation_mix: Mapped[dict] = mapped_column(JSON, nullable=False)  # {fuel_type: percentage}
    renewable_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)


class BuildingPermitData(Base, TimestampMixin):
    """FRED building permit data."""

    __tablename__ = "building_permit_data"
    __table_args__ = (
        UniqueConstraint("period", "geography_level", "geography_code", "permit_type",
                        name="uq_permit_period_geo_type"),
        Index("ix_permit_period", "period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period: Mapped[date] = mapped_column(Date, nullable=False)  # First day of month
    geography_level: Mapped[str] = mapped_column(String(20), nullable=False)  # national, state, metro
    geography_code: Mapped[str] = mapped_column(String(20), nullable=False)
    geography_name: Mapped[str] = mapped_column(String(100), nullable=False)
    permit_type: Mapped[str] = mapped_column(String(50), nullable=False)  # total, single_family, multi_family
    units_authorized: Mapped[int] = mapped_column(Integer, nullable=False)
    valuation_thousands: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    mom_change_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    yoy_change_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    seasonally_adjusted: Mapped[bool] = mapped_column(Boolean, default=True)


class BoxOfficeDaily(Base, TimestampMixin):
    """Daily box office revenue data."""

    __tablename__ = "box_office_daily"
    __table_args__ = (
        UniqueConstraint("date", "movie_title", name="uq_boxoffice_date_movie"),
        Index("ix_boxoffice_date", "date"),
        Index("ix_boxoffice_distributor", "distributor_ticker"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    movie_title: Mapped[str] = mapped_column(String(300), nullable=False)
    distributor: Mapped[str] = mapped_column(String(100), nullable=False)
    distributor_ticker: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    daily_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    cumulative_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    theater_count: Mapped[int] = mapped_column(Integer, nullable=False)
    per_theater_avg: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    days_in_release: Mapped[int] = mapped_column(Integer, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    is_opening_weekend: Mapped[bool] = mapped_column(Boolean, default=False)


class CloudflareRadarMetrics(Base, TimestampMixin):
    """Cloudflare Radar internet metrics."""

    __tablename__ = "cloudflare_radar_metrics"
    __table_args__ = (
        UniqueConstraint("timestamp", "metric_type", "region", name="uq_cloudflare_timestamp_metric_region"),
        Index("ix_cloudflare_timestamp", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False)  # traffic, attacks, outages
    region: Mapped[str] = mapped_column(String(50), nullable=False)  # global or country code
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    baseline_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    deviation_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    extra_data: Mapped[dict] = mapped_column(JSON, nullable=True)


class ZillowRentalIndex(Base, TimestampMixin):
    """Zillow rental index data."""

    __tablename__ = "zillow_rental_index"
    __table_args__ = (
        UniqueConstraint("period", "geography_level", "geography_id", "property_type",
                        name="uq_zillow_period_geo_type"),
        Index("ix_zillow_period", "period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period: Mapped[date] = mapped_column(Date, nullable=False)  # First day of month
    geography_level: Mapped[str] = mapped_column(String(20), nullable=False)  # national, metro, zip
    geography_id: Mapped[str] = mapped_column(String(20), nullable=False)
    geography_name: Mapped[str] = mapped_column(String(200), nullable=False)
    property_type: Mapped[str] = mapped_column(String(50), nullable=False)  # all, single_family, multi_family
    zori_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)  # Zillow Observed Rent Index
    mom_change_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    yoy_change_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
