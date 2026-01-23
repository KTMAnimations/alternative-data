"""Database models for Cloudflare Radar data."""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, BigInteger,
    Index, ForeignKey, JSON
)

from src.models.database import Base


class CloudflareRadarMetrics(Base):
    """Cloudflare Radar internet health metrics.

    Traffic patterns, attack trends, and outage detection.
    """
    __tablename__ = "cloudflare_radar_metrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Region (global, country, ASN)
    region_type = Column(String(20))  # global, country, asn
    region_code = Column(String(50))  # ISO country code or ASN number

    # Traffic metrics
    traffic_index = Column(Float)  # Normalized traffic level (baseline = 100)
    traffic_change_pct = Column(Float)  # Percentage change from baseline

    # Protocol breakdown
    http_share = Column(Float)
    https_share = Column(Float)
    http3_share = Column(Float)

    # Security metrics
    attack_volume_index = Column(Float)  # DDoS and other attacks
    bot_traffic_share = Column(Float)
    threat_score = Column(Float)  # 0-100

    # Outage indicators
    is_outage_detected = Column(String(5))  # Yes/No
    outage_severity = Column(String(20))  # minor, moderate, major

    # Additional metrics stored as JSON
    extra_metrics = Column(JSON)

    # Lineage
    raw_data_id = Column(BigInteger, ForeignKey("raw_data_catalog.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_cloudflare_timestamp_region", "timestamp", "region_type", "region_code"),
    )
