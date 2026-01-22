"""Database models for the Alternative Data Platform."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, Float, DateTime, Integer, BigInteger, 
    Boolean, Text, ForeignKey, Index, JSON, ARRAY
)
from sqlalchemy.orm import relationship

from src.models.database import Base


class RawDataCatalog(Base):
    """Catalog of raw data files stored in the data lake.
    
    Every piece of raw data fetched from external sources is
    recorded here with metadata for lineage tracking.
    """
    __tablename__ = "raw_data_catalog"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False, index=True)
    file_path = Column(Text, nullable=False)
    fetch_timestamp = Column(DateTime(timezone=True), nullable=False)
    data_timestamp = Column(DateTime(timezone=True))
    checksum = Column(String(64), nullable=False)
    record_count = Column(Integer)
    file_size_bytes = Column(BigInteger)
    extra_data = Column(JSON)

    __table_args__ = (
        Index("ix_raw_data_source_timestamp", "source", "fetch_timestamp"),
    )


class Entity(Base):
    """Company/security entity for factor mapping.
    
    Provides unified entity identification across different
    identifier systems (ticker, CIK, LEI, etc.)
    """
    __tablename__ = "entities"
    
    id = Column(String(50), primary_key=True)
    entity_type = Column(String(20), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    ticker = Column(String(20), index=True)
    cik = Column(String(20), index=True)
    lei = Column(String(20))
    isin = Column(String(20))
    exchange = Column(String(20))
    sector = Column(String(100))
    industry = Column(String(100))
    aliases = Column(JSON)
    extra_data = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_entity_ticker_type", "ticker", "entity_type"),
    )


class Factor(Base):
    """Computed factor values.
    
    Stores calculated factor values with full point-in-time
    tracking and source data lineage.
    """
    __tablename__ = "factors"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    factor_name = Column(String(100), nullable=False, index=True)
    entity_id = Column(String(50), nullable=False, index=True)
    entity_type = Column(String(20), nullable=False)
    value = Column(Float)
    effective_date = Column(DateTime, nullable=False)
    computed_at = Column(DateTime(timezone=True), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    source_data_ids = Column(ARRAY(BigInteger))
    extra_data = Column(JSON)

    __table_args__ = (
        Index("ix_factor_name_entity_date", "factor_name", "entity_id", "effective_date"),
        Index("ix_factor_entity_date", "entity_id", "effective_date"),
    )


class FactorDefinition(Base):
    """Factor metadata and configuration.
    
    Stores information about available factors including
    descriptions, computation parameters, and version history.
    """
    __tablename__ = "factor_definitions"
    
    id = Column(String(100), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    category = Column(String(50), index=True)
    entity_type = Column(String(20), nullable=False)
    frequency = Column(String(20))  # daily, weekly, monthly
    lookback_days = Column(Integer)
    dependencies = Column(JSON)  # List of dependent factors/data sources
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class SECForm4Transaction(Base):
    """Parsed SEC Form 4 insider transactions.
    
    Each row represents a single transaction from a Form 4 filing.
    """
    __tablename__ = "sec_form4_transactions"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Filing identifiers
    accession_number = Column(String(30), nullable=False, unique=True)
    cik = Column(String(20), nullable=False, index=True)
    
    # Issuer info
    issuer_cik = Column(String(20), nullable=False, index=True)
    issuer_name = Column(String(255))
    ticker = Column(String(20), index=True)
    
    # Insider info
    insider_cik = Column(String(20))
    insider_name = Column(String(255))
    insider_title = Column(String(100))
    is_director = Column(Boolean)
    is_officer = Column(Boolean)
    is_ten_percent_owner = Column(Boolean)
    
    # Transaction details
    transaction_type = Column(String(10))  # P=Purchase, S=Sale, A=Award, etc.
    transaction_code = Column(String(5))
    shares = Column(Float)
    price_per_share = Column(Float)
    total_value = Column(Float)
    shares_owned_after = Column(Float)
    ownership_type = Column(String(1))  # D=Direct, I=Indirect
    
    # Dates
    transaction_date = Column(DateTime)
    filed_date = Column(DateTime, index=True)
    
    # Lineage
    raw_data_id = Column(BigInteger, ForeignKey("raw_data_catalog.id"))
    extra_data = Column(JSON)

    __table_args__ = (
        Index("ix_form4_ticker_date", "ticker", "transaction_date"),
        Index("ix_form4_insider_date", "insider_cik", "transaction_date"),
    )


class SECFiling(Base):
    """SEC EDGAR filing metadata.
    
    Tracks all SEC filings (10-K, 10-Q, 8-K, etc.)
    """
    __tablename__ = "sec_filings"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    accession_number = Column(String(30), nullable=False, unique=True)
    cik = Column(String(20), nullable=False, index=True)
    ticker = Column(String(20), index=True)
    company_name = Column(String(255))
    form_type = Column(String(20), nullable=False, index=True)
    filed_date = Column(DateTime, nullable=False, index=True)
    period_date = Column(DateTime)
    accepted_datetime = Column(DateTime)
    document_url = Column(Text)
    
    # NLP-derived fields
    sentiment_score = Column(Float)
    risk_score = Column(Float)
    
    raw_data_id = Column(BigInteger, ForeignKey("raw_data_catalog.id"))
    extra_data = Column(JSON)

    __table_args__ = (
        Index("ix_filing_type_date", "form_type", "filed_date"),
    )


class FREDSeries(Base):
    """FRED economic data series values.
    
    Stores time series data from Federal Reserve Economic Data.
    """
    __tablename__ = "fred_series"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    series_id = Column(String(50), nullable=False, index=True)
    observation_date = Column(DateTime, nullable=False)
    value = Column(Float)
    realtime_start = Column(DateTime)
    realtime_end = Column(DateTime)
    
    raw_data_id = Column(BigInteger, ForeignKey("raw_data_catalog.id"))
    
    __table_args__ = (
        Index("ix_fred_series_date", "series_id", "observation_date", unique=True),
    )


class APIKey(Base):
    """API keys for client authentication."""
    __tablename__ = "api_keys"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    permissions = Column(JSON)  # List of allowed operations
    rate_limit = Column(Integer, default=1000)  # requests per hour
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True))
    last_used_at = Column(DateTime(timezone=True))
