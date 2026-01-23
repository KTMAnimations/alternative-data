"""Database models for shipping and AIS data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, Integer, BigInteger,
    Index, JSON, Text, Date, Boolean
)

from src.models.database import Base


class Vessel(Base):
    """Vessel master data."""
    __tablename__ = "vessels"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    mmsi = Column(String(20), nullable=False, unique=True, index=True)
    imo = Column(String(20), index=True)
    name = Column(String(255), index=True)
    callsign = Column(String(20))

    # Vessel characteristics
    vessel_type = Column(String(50), index=True)  # Cargo, Tanker, Container, etc.
    vessel_type_code = Column(Integer)
    flag = Column(String(10), index=True)  # Country code
    gross_tonnage = Column(Integer)
    deadweight = Column(Integer)
    length_m = Column(Float)
    width_m = Column(Float)
    draught_m = Column(Float)
    year_built = Column(Integer)

    # Owner/operator info
    owner = Column(String(255))
    manager = Column(String(255))

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_vessel_type", "vessel_type"),
        Index("ix_vessel_flag", "flag"),
    )


class VesselPosition(Base):
    """AIS vessel position data."""
    __tablename__ = "vessel_positions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    mmsi = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Position
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Movement
    speed_knots = Column(Float)
    course = Column(Float)  # Degrees
    heading = Column(Float)  # Degrees
    nav_status = Column(String(50))  # At anchor, Under way, etc.

    # Destination
    destination = Column(String(255))
    eta = Column(DateTime(timezone=True))

    # Source info
    source = Column(String(50))  # terrestrial, satellite
    fetched_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_vessel_pos_mmsi_time", "mmsi", "timestamp"),
        Index("ix_vessel_pos_time", "timestamp"),
    )


class Port(Base):
    """Port master data."""
    __tablename__ = "ports"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    port_id = Column(String(20), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    country = Column(String(10), nullable=False, index=True)
    region = Column(String(100))

    latitude = Column(Float)
    longitude = Column(Float)

    # Port characteristics
    port_type = Column(String(50))  # Seaport, River port, etc.
    max_vessel_size = Column(String(50))
    is_major = Column(Boolean, default=False)

    # Trade info
    primary_cargo_types = Column(JSON)  # List of cargo types
    annual_teu_capacity = Column(Integer)  # Container capacity

    __table_args__ = (
        Index("ix_port_country", "country"),
    )


class PortCall(Base):
    """Vessel port calls (arrivals/departures)."""
    __tablename__ = "port_calls"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    mmsi = Column(String(20), nullable=False, index=True)
    port_id = Column(String(20), nullable=False, index=True)
    call_type = Column(String(20), nullable=False)  # arrival, departure

    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    duration_hours = Column(Float)  # For departures, time spent in port

    # Cargo info
    cargo_type = Column(String(100))
    cargo_volume = Column(Float)

    detected_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_port_call_port_time", "port_id", "timestamp"),
        Index("ix_port_call_mmsi", "mmsi"),
    )


class ShippingRoute(Base):
    """Major shipping routes and their traffic."""
    __tablename__ = "shipping_routes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    route_id = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(255))
    origin_port = Column(String(20), index=True)
    destination_port = Column(String(20), index=True)
    waypoints = Column(JSON)  # List of {lat, lon} waypoints

    # Route characteristics
    typical_duration_days = Column(Float)
    distance_nm = Column(Float)  # Nautical miles
    is_major_lane = Column(Boolean, default=False)

    __table_args__ = (
        Index("ix_route_origin", "origin_port"),
        Index("ix_route_dest", "destination_port"),
    )


class PortCongestion(Base):
    """Port congestion metrics."""
    __tablename__ = "port_congestion"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    port_id = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)

    # Congestion metrics
    vessels_at_anchor = Column(Integer)
    vessels_in_port = Column(Integer)
    avg_wait_time_hours = Column(Float)
    vessels_arriving_24h = Column(Integer)
    vessels_departing_24h = Column(Integer)

    # By vessel type
    container_vessels = Column(Integer)
    tankers = Column(Integer)
    bulk_carriers = Column(Integer)

    computed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_port_cong_port_date", "port_id", "date"),
    )


class GlobalShippingIndex(Base):
    """Global shipping activity indices."""
    __tablename__ = "global_shipping_indices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)

    # Activity indices
    global_activity_index = Column(Float)  # Overall shipping activity
    container_activity_index = Column(Float)
    tanker_activity_index = Column(Float)
    bulk_activity_index = Column(Float)

    # Regional indices
    asia_pacific_index = Column(Float)
    europe_index = Column(Float)
    americas_index = Column(Float)

    # Congestion indices
    global_congestion_index = Column(Float)
    china_congestion_index = Column(Float)
    us_congestion_index = Column(Float)

    computed_at = Column(DateTime(timezone=True), default=datetime.utcnow)
