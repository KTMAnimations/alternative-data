"""Database models for Sentinel-2 satellite imagery data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, Integer, BigInteger,
    Index, JSON, Text, Date, Boolean
)

from src.models.database import Base


class SatelliteLocation(Base):
    """Tracked satellite observation locations."""
    __tablename__ = "satellite_locations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    location_id = Column(String(100), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    location_type = Column(String(50), nullable=False, index=True)  # parking_lot, port, construction, agricultural

    # Coordinates (bounding box)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    bbox_north = Column(Float)
    bbox_south = Column(Float)
    bbox_east = Column(Float)
    bbox_west = Column(Float)

    # Associated entity
    company = Column(String(255))
    ticker = Column(String(10), index=True)
    sector = Column(String(100))

    # Tracking info
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_satellite_loc_type", "location_type"),
        Index("ix_satellite_loc_ticker", "ticker"),
    )


class SatelliteImage(Base):
    """Satellite image metadata and processing results."""
    __tablename__ = "satellite_images"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    image_id = Column(String(255), nullable=False, unique=True, index=True)
    location_id = Column(String(100), nullable=False, index=True)

    # Image metadata
    acquisition_date = Column(DateTime(timezone=True), nullable=False, index=True)
    platform = Column(String(50))  # Sentinel-2A, Sentinel-2B
    product_type = Column(String(50))  # S2MSI1C, S2MSI2A
    cloud_cover_pct = Column(Float)
    processing_level = Column(String(20))

    # Storage
    tile_id = Column(String(50))
    s3_path = Column(String(500))
    local_path = Column(String(500))

    # Processing status
    is_processed = Column(Boolean, default=False)
    processed_at = Column(DateTime(timezone=True))
    processing_error = Column(Text)

    fetched_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_satellite_img_loc_date", "location_id", "acquisition_date"),
    )


class ParkingLotMetrics(Base):
    """Parking lot occupancy derived from satellite imagery."""
    __tablename__ = "parking_lot_metrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    location_id = Column(String(100), nullable=False, index=True)
    image_id = Column(String(255), index=True)
    observation_date = Column(Date, nullable=False, index=True)

    # Occupancy metrics
    total_spaces = Column(Integer)
    occupied_spaces = Column(Integer)
    occupancy_rate = Column(Float)  # 0-1

    # Vehicle counts by segment (if detected)
    cars_detected = Column(Integer)
    trucks_detected = Column(Integer)

    # Quality metrics
    confidence_score = Column(Float)
    cloud_contamination = Column(Float)

    # Associated company
    ticker = Column(String(10), index=True)

    computed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_parking_loc_date", "location_id", "observation_date"),
        Index("ix_parking_ticker_date", "ticker", "observation_date"),
    )


class ConstructionMetrics(Base):
    """Construction activity metrics from satellite imagery."""
    __tablename__ = "construction_metrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    location_id = Column(String(100), nullable=False, index=True)
    image_id = Column(String(255), index=True)
    observation_date = Column(Date, nullable=False, index=True)

    # Activity metrics
    active_area_sqm = Column(Float)  # Square meters of active construction
    equipment_count = Column(Integer)  # Detected construction equipment
    change_from_prior = Column(Float)  # % change from prior observation

    # Progress indicators
    foundation_complete = Column(Boolean)
    structure_visible = Column(Boolean)
    estimated_completion_pct = Column(Float)

    # Quality metrics
    confidence_score = Column(Float)

    ticker = Column(String(10), index=True)

    computed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_construction_loc_date", "location_id", "observation_date"),
    )


class AgriculturalMetrics(Base):
    """Agricultural metrics from satellite imagery (NDVI, etc.)."""
    __tablename__ = "agricultural_metrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    location_id = Column(String(100), nullable=False, index=True)
    region = Column(String(100), index=True)
    crop_type = Column(String(50), index=True)
    image_id = Column(String(255), index=True)
    observation_date = Column(Date, nullable=False, index=True)

    # Vegetation indices
    ndvi_mean = Column(Float)  # Normalized Difference Vegetation Index
    ndvi_std = Column(Float)
    evi_mean = Column(Float)  # Enhanced Vegetation Index
    ndwi_mean = Column(Float)  # Normalized Difference Water Index

    # Health indicators
    crop_health_score = Column(Float)  # Derived score 0-100
    stress_indicator = Column(Float)  # Stress level 0-1
    growth_stage = Column(String(50))  # Vegetative, Reproductive, Maturity

    # Comparisons
    ndvi_vs_historical = Column(Float)  # % difference from historical avg
    ndvi_vs_prior_year = Column(Float)  # % difference from prior year

    # Quality
    confidence_score = Column(Float)
    cloud_cover_pct = Column(Float)

    computed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_agri_loc_date", "location_id", "observation_date"),
        Index("ix_agri_region_date", "region", "observation_date"),
    )


class PortActivityMetrics(Base):
    """Port container activity from satellite imagery."""
    __tablename__ = "port_activity_metrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    port_id = Column(String(20), nullable=False, index=True)
    image_id = Column(String(255), index=True)
    observation_date = Column(Date, nullable=False, index=True)

    # Container metrics
    container_area_sqm = Column(Float)
    estimated_teu = Column(Integer)  # Twenty-foot equivalent units
    container_density = Column(Float)  # Containers per area

    # Vessel detection
    vessels_detected = Column(Integer)
    large_vessels = Column(Integer)

    # Activity indicators
    activity_index = Column(Float)  # 0-100 activity score
    change_from_prior = Column(Float)

    confidence_score = Column(Float)

    computed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_port_activity_port_date", "port_id", "observation_date"),
    )
