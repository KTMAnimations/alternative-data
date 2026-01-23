"""Database models for ADS-B aviation data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, Integer, BigInteger,
    Boolean, ForeignKey, Index, JSON
)
from sqlalchemy.orm import relationship

from src.models.database import Base


class Aircraft(Base):
    """Aircraft registration and ownership mapping."""
    __tablename__ = "aircraft"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    icao_hex = Column(String(10), unique=True, nullable=False, index=True)
    registration = Column(String(20), index=True)  # N-number
    aircraft_type = Column(String(20))  # GLF6, G650, etc.
    aircraft_model = Column(String(100))
    owner_name = Column(String(255))
    owner_type = Column(String(50))  # corporate, individual, charter
    company_entity_id = Column(String(50), index=True)  # Link to entities table
    is_corporate_jet = Column(Boolean, default=False)
    extra_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    landings = relationship("FlightLanding", back_populates="aircraft")

    __table_args__ = (
        Index("ix_aircraft_company", "company_entity_id"),
        Index("ix_aircraft_type_corporate", "aircraft_type", "is_corporate_jet"),
    )


class FlightPosition(Base):
    """Real-time and historical flight positions."""
    __tablename__ = "flight_positions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    icao_hex = Column(String(10), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    altitude_ft = Column(Integer)
    ground_speed_knots = Column(Integer)
    heading = Column(Integer)
    vertical_rate = Column(Integer)
    squawk = Column(String(10))
    on_ground = Column(Boolean)
    flight_id = Column(String(50))  # Callsign or flight number
    raw_data_id = Column(BigInteger, ForeignKey("raw_data_catalog.id"))

    __table_args__ = (
        Index("ix_flight_pos_icao_time", "icao_hex", "timestamp"),
        Index("ix_flight_pos_time", "timestamp"),
    )


class FlightLanding(Base):
    """Detected landings for analysis."""
    __tablename__ = "flight_landings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    icao_hex = Column(String(10), nullable=False, index=True)
    aircraft_id = Column(BigInteger, ForeignKey("aircraft.id"))
    landing_timestamp = Column(DateTime(timezone=True), nullable=False)
    airport_icao = Column(String(10), index=True)
    airport_name = Column(String(255))
    latitude = Column(Float)
    longitude = Column(Float)
    nearest_company_hq = Column(String(50))  # Entity ID if within 50km of HQ
    distance_to_hq_km = Column(Float)
    extra_data = Column(JSON)

    # Relationships
    aircraft = relationship("Aircraft", back_populates="landings")

    __table_args__ = (
        Index("ix_landing_airport_time", "airport_icao", "landing_timestamp"),
        Index("ix_landing_icao_time", "icao_hex", "landing_timestamp"),
    )


class Airport(Base):
    """Airport reference data."""
    __tablename__ = "airports"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    icao_code = Column(String(10), unique=True, nullable=False, index=True)
    iata_code = Column(String(10), index=True)
    name = Column(String(255), nullable=False)
    city = Column(String(100))
    country = Column(String(100))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    elevation_ft = Column(Integer)
    airport_type = Column(String(50))  # large, medium, small, heliport

    __table_args__ = (
        Index("ix_airport_location", "latitude", "longitude"),
    )


class CompanyHQ(Base):
    """Company headquarters locations for proximity analysis."""
    __tablename__ = "company_hq"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    entity_id = Column(String(50), nullable=False, unique=True, index=True)
    company_name = Column(String(255))
    address = Column(String(500))
    city = Column(String(100))
    state = Column(String(50))
    country = Column(String(100))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    nearest_airport_icao = Column(String(10))

    __table_args__ = (
        Index("ix_company_hq_location", "latitude", "longitude"),
    )
