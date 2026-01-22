"""Database models for Google Trends data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, Integer, BigInteger,
    Index, JSON, Text, Date, Boolean
)

from src.models.database import Base


class TrendKeyword(Base):
    """Tracked keywords and their metadata."""
    __tablename__ = "trend_keywords"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    keyword = Column(String(255), nullable=False, unique=True, index=True)
    category = Column(String(100), index=True)  # retail, energy, tech, etc.
    related_tickers = Column(JSON)  # List of related stock tickers
    related_sectors = Column(JSON)  # List of related sectors
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_fetched = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_trend_keyword_cat", "category"),
    )


class TrendInterest(Base):
    """Historical search interest data from Google Trends."""
    __tablename__ = "trend_interest"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    keyword = Column(String(255), nullable=False, index=True)
    geo = Column(String(10), default="US", index=True)  # Geographic region
    date = Column(Date, nullable=False, index=True)
    interest = Column(Integer)  # 0-100 normalized interest
    is_partial = Column(Boolean, default=False)  # Partial data for current period
    fetched_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_trend_interest_kw_date", "keyword", "date"),
        Index("ix_trend_interest_geo_date", "geo", "date"),
    )


class TrendRelatedQuery(Base):
    """Related queries for keywords."""
    __tablename__ = "trend_related_queries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    keyword = Column(String(255), nullable=False, index=True)
    geo = Column(String(10), default="US")
    related_query = Column(String(255), nullable=False)
    query_type = Column(String(20))  # 'top' or 'rising'
    value = Column(Integer)  # Interest value or % increase
    fetched_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_trend_related_kw", "keyword"),
    )


class TrendComparison(Base):
    """Comparative interest between multiple keywords."""
    __tablename__ = "trend_comparisons"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    keyword_group = Column(String(255), nullable=False, index=True)  # Comma-separated keywords
    geo = Column(String(10), default="US")
    date = Column(Date, nullable=False, index=True)
    keyword_values = Column(JSON)  # {keyword: interest_value}
    fetched_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_trend_comp_group_date", "keyword_group", "date"),
    )


class TrendBreakout(Base):
    """Detected breakout events in search interest."""
    __tablename__ = "trend_breakouts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    keyword = Column(String(255), nullable=False, index=True)
    geo = Column(String(10), default="US")
    breakout_date = Column(Date, nullable=False, index=True)
    interest_before = Column(Float)  # Avg interest before breakout
    interest_peak = Column(Integer)  # Peak interest during breakout
    percent_change = Column(Float)  # Percentage increase
    detected_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_trend_breakout_kw_date", "keyword", "breakout_date"),
    )
