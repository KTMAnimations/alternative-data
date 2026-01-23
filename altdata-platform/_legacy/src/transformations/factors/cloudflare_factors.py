"""Cloudflare Radar-derived factor computations.

Factors derived from internet traffic and security data
for technology and cybersecurity analysis.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.cloudflare_radar import CloudflareRadarMetrics
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


# Entity mapping for Cloudflare factors
CYBERSECURITY_TICKERS = ["CRWD", "PANW", "ZS", "FTNT", "NET", "S"]
CLOUD_PROVIDERS = ["AMZN", "MSFT", "GOOGL", "ORCL", "IBM"]
CDN_PROVIDERS = ["NET", "AKAM", "FSLY"]


def calc_traffic_anomaly_index(
    target_date: date,
    lookback_hours: int = 24,
) -> Optional[float]:
    """Calculate traffic anomaly index.

    Measures deviation from baseline traffic levels.

    Args:
        target_date: Reference date
        lookback_hours: Analysis window

    Returns:
        Anomaly index (100 = normal, >100 = above normal)
    """
    session = SessionLocal()
    try:
        target_datetime = datetime.combine(target_date, datetime.max.time())
        start_datetime = target_datetime - timedelta(hours=lookback_hours)

        avg_traffic = (
            session.query(func.avg(CloudflareRadarMetrics.traffic_index))
            .filter(
                CloudflareRadarMetrics.timestamp >= start_datetime,
                CloudflareRadarMetrics.timestamp <= target_datetime,
                CloudflareRadarMetrics.region_type == "global",
            )
            .scalar()
        )

        if avg_traffic:
            return float(avg_traffic)
        return None

    finally:
        session.close()


def calc_attack_volume_index(
    target_date: date,
    lookback_hours: int = 24,
) -> Optional[float]:
    """Calculate attack volume index.

    Measures DDoS and other attack activity.

    Args:
        target_date: Reference date
        lookback_hours: Analysis window

    Returns:
        Attack volume index (100 = baseline)
    """
    session = SessionLocal()
    try:
        target_datetime = datetime.combine(target_date, datetime.max.time())
        start_datetime = target_datetime - timedelta(hours=lookback_hours)

        avg_attacks = (
            session.query(func.avg(CloudflareRadarMetrics.attack_volume_index))
            .filter(
                CloudflareRadarMetrics.timestamp >= start_datetime,
                CloudflareRadarMetrics.timestamp <= target_datetime,
                CloudflareRadarMetrics.region_type == "global",
            )
            .scalar()
        )

        if avg_attacks:
            return float(avg_attacks)
        return None

    finally:
        session.close()


def calc_traffic_volatility(
    target_date: date,
    lookback_hours: int = 48,
) -> Optional[float]:
    """Calculate traffic volatility.

    Standard deviation of traffic index.

    Args:
        target_date: Reference date
        lookback_hours: Analysis window

    Returns:
        Traffic volatility
    """
    session = SessionLocal()
    try:
        target_datetime = datetime.combine(target_date, datetime.max.time())
        start_datetime = target_datetime - timedelta(hours=lookback_hours)

        std_dev = (
            session.query(func.stddev(CloudflareRadarMetrics.traffic_index))
            .filter(
                CloudflareRadarMetrics.timestamp >= start_datetime,
                CloudflareRadarMetrics.timestamp <= target_datetime,
                CloudflareRadarMetrics.region_type == "global",
            )
            .scalar()
        )

        if std_dev:
            return float(std_dev)
        return None

    finally:
        session.close()


def calc_security_threat_level(
    target_date: date,
    lookback_hours: int = 24,
) -> Optional[float]:
    """Calculate overall security threat level.

    Composite score based on attack volume and threat metrics.

    Args:
        target_date: Reference date
        lookback_hours: Analysis window

    Returns:
        Threat level (0-100)
    """
    session = SessionLocal()
    try:
        target_datetime = datetime.combine(target_date, datetime.max.time())
        start_datetime = target_datetime - timedelta(hours=lookback_hours)

        metrics = (
            session.query(
                func.avg(CloudflareRadarMetrics.attack_volume_index),
                func.avg(CloudflareRadarMetrics.threat_score),
            )
            .filter(
                CloudflareRadarMetrics.timestamp >= start_datetime,
                CloudflareRadarMetrics.timestamp <= target_datetime,
                CloudflareRadarMetrics.region_type == "global",
            )
            .first()
        )

        if not metrics:
            return None

        attack_avg = float(metrics[0]) if metrics[0] else 0
        threat_avg = float(metrics[1]) if metrics[1] else 0

        # Composite score (weighted average)
        return (attack_avg * 0.6 + threat_avg * 0.4)

    finally:
        session.close()


def calc_outage_count(
    target_date: date,
    lookback_hours: int = 24,
) -> Optional[int]:
    """Count detected outages in period.

    Args:
        target_date: Reference date
        lookback_hours: Analysis window

    Returns:
        Number of detected outages
    """
    session = SessionLocal()
    try:
        target_datetime = datetime.combine(target_date, datetime.max.time())
        start_datetime = target_datetime - timedelta(hours=lookback_hours)

        count = (
            session.query(func.count(CloudflareRadarMetrics.id))
            .filter(
                CloudflareRadarMetrics.timestamp >= start_datetime,
                CloudflareRadarMetrics.timestamp <= target_datetime,
                CloudflareRadarMetrics.is_outage_detected == "Yes",
            )
            .scalar()
        )

        return int(count) if count else 0

    finally:
        session.close()


@FactorRegistry.register
class TrafficAnomalyIndex(BaseFactor):
    """Traffic Anomaly Index Factor.

    Measures internet traffic deviation from baseline.
    High values may indicate major events or disruptions.

    Target: CDN providers, cloud companies
    """

    FACTOR_NAME = "traffic_anomaly_index"
    FACTOR_DESCRIPTION = "Internet traffic anomaly index (100 = normal)"
    CATEGORY = "internet"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_hours: int = 24,
    ) -> Optional[float]:
        """Compute traffic anomaly index."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_traffic_anomaly_index(target_date, lookback_hours)


@FactorRegistry.register
class SecurityThreatLevel(BaseFactor):
    """Security Threat Level Factor.

    Overall cybersecurity threat level.
    Higher values indicate increased attack activity.

    Target: CRWD, PANW, ZS, FTNT, NET
    """

    FACTOR_NAME = "security_threat_level"
    FACTOR_DESCRIPTION = "Cybersecurity threat level (0-100)"
    CATEGORY = "internet"
    ENTITY_TYPE = "company"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute security threat level."""
        if entity_id not in CYBERSECURITY_TICKERS:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_security_threat_level(target_date)


@FactorRegistry.register
class AttackVolumeIndex(BaseFactor):
    """Attack Volume Index Factor.

    DDoS and cyber attack activity level.
    Bullish for cybersecurity stocks when elevated.

    Target: Cybersecurity companies
    """

    FACTOR_NAME = "attack_volume_index"
    FACTOR_DESCRIPTION = "DDoS attack volume index (100 = baseline)"
    CATEGORY = "internet"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute attack volume index."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_attack_volume_index(target_date)


@FactorRegistry.register
class InternetOutageCount(BaseFactor):
    """Internet Outage Count Factor.

    Number of detected internet outages.
    High counts may indicate infrastructure issues.

    Target: Cloud providers, CDN companies
    """

    FACTOR_NAME = "internet_outage_count"
    FACTOR_DESCRIPTION = "Number of detected internet outages (24h)"
    CATEGORY = "internet"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute outage count."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return float(calc_outage_count(target_date))


@FactorRegistry.register
class TrafficVolatility(BaseFactor):
    """Traffic Volatility Factor.

    Volatility in internet traffic patterns.
    High volatility may indicate instability.

    Target: Infrastructure companies
    """

    FACTOR_NAME = "traffic_volatility"
    FACTOR_DESCRIPTION = "Internet traffic volatility (48h)"
    CATEGORY = "internet"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 2

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute traffic volatility."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_traffic_volatility(target_date)
