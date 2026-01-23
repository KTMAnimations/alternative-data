"""Earthquake-derived factor computations.

Factors derived from USGS seismic data for insurance,
real estate, and supply chain risk analysis.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from math import radians, sin, cos, sqrt, atan2

from sqlalchemy import func, and_

from src.models.database import SessionLocal
from src.models.earthquake import EarthquakeEvent
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


# Insurance companies with earthquake exposure
INSURANCE_TICKERS = ["ALL", "TRV", "CB", "PGR", "MET", "AIG", "HIG", "BRK.B"]

# Real estate with regional exposure
REITS_BY_REGION = {
    "california": ["AVB", "EQR", "ESS", "INVH", "AMH"],
    "pacific_northwest": ["AVB", "EQR"],
    "japan": ["SONY", "TM", "HMC"],  # Japanese companies
}

# Semiconductor fabs with earthquake risk
SEMICONDUCTOR_EXPOSURE = {
    "taiwan": ["TSM", "NVDA", "AMD", "INTC", "QCOM"],  # TSMC fab exposure
    "japan": ["NVDA", "AMD", "INTC"],  # Japan supplier exposure
}

# Key seismic zones with bounding boxes
SEISMIC_ZONES = {
    "california": {"min_lat": 32.5, "max_lat": 42.0, "min_lon": -125.0, "max_lon": -114.0},
    "pacific_northwest": {"min_lat": 42.0, "max_lat": 49.0, "min_lon": -125.0, "max_lon": -116.0},
    "alaska": {"min_lat": 51.0, "max_lat": 72.0, "min_lon": -180.0, "max_lon": -129.0},
    "taiwan": {"min_lat": 21.5, "max_lat": 26.5, "min_lon": 119.0, "max_lon": 123.0},
    "japan": {"min_lat": 30.0, "max_lat": 46.0, "min_lon": 129.0, "max_lon": 146.0},
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers."""
    R = 6371  # Earth's radius in km

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def calc_regional_seismic_activity(
    zone_name: str,
    target_date: date,
    lookback_days: int = 30,
    min_magnitude: float = 3.0,
) -> Optional[Dict]:
    """Calculate seismic activity metrics for a zone.

    Args:
        zone_name: Name of seismic zone
        target_date: Reference date
        lookback_days: Analysis window
        min_magnitude: Minimum magnitude to include

    Returns:
        Dict with event_count, max_magnitude, avg_magnitude
    """
    zone = SEISMIC_ZONES.get(zone_name)
    if not zone:
        return None

    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        metrics = (
            session.query(
                func.count(EarthquakeEvent.id),
                func.max(EarthquakeEvent.magnitude),
                func.avg(EarthquakeEvent.magnitude),
            )
            .filter(
                EarthquakeEvent.timestamp >= datetime.combine(start_date, datetime.min.time()),
                EarthquakeEvent.timestamp <= datetime.combine(target_date, datetime.max.time()),
                EarthquakeEvent.magnitude >= min_magnitude,
                EarthquakeEvent.latitude >= zone["min_lat"],
                EarthquakeEvent.latitude <= zone["max_lat"],
                EarthquakeEvent.longitude >= zone["min_lon"],
                EarthquakeEvent.longitude <= zone["max_lon"],
            )
            .first()
        )

        if not metrics or metrics[0] == 0:
            return {"event_count": 0, "max_magnitude": None, "avg_magnitude": None}

        return {
            "event_count": int(metrics[0]),
            "max_magnitude": float(metrics[1]) if metrics[1] else None,
            "avg_magnitude": float(metrics[2]) if metrics[2] else None,
        }

    finally:
        session.close()


def calc_seismic_risk_index(
    target_date: date,
    lookback_days: int = 30,
) -> Optional[float]:
    """Calculate global seismic risk index.

    Weighted sum of significant events globally.
    Higher values indicate increased seismic activity.

    Args:
        target_date: Reference date
        lookback_days: Analysis window

    Returns:
        Risk index (0-100)
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        # Get all significant events
        events = (
            session.query(EarthquakeEvent.magnitude, EarthquakeEvent.felt_reports)
            .filter(
                EarthquakeEvent.timestamp >= datetime.combine(start_date, datetime.min.time()),
                EarthquakeEvent.timestamp <= datetime.combine(target_date, datetime.max.time()),
                EarthquakeEvent.magnitude >= 4.0,
            )
            .all()
        )

        if not events:
            return 0.0

        # Calculate weighted index
        # Weight by magnitude (exponential) and felt reports
        total_weight = 0
        for mag, felt in events:
            if mag:
                # Magnitude contribution (exponential scale)
                mag_weight = 10 ** (mag - 4)  # M4=1, M5=10, M6=100, M7=1000
                # Felt reports contribution
                felt_weight = 1 + (felt or 0) / 100
                total_weight += mag_weight * felt_weight

        # Normalize to 0-100 scale
        # Assume typical monthly activity is ~50 weighted points
        return min(100, total_weight / 5)

    finally:
        session.close()


def calc_major_event_alert(
    target_date: date,
    lookback_hours: int = 24,
    magnitude_threshold: float = 6.0,
) -> Optional[float]:
    """Check for major earthquake events in recent period.

    Args:
        target_date: Reference date
        lookback_hours: Hours to look back
        magnitude_threshold: Minimum magnitude for alert

    Returns:
        Maximum magnitude in period, or 0 if no major events
    """
    session = SessionLocal()
    try:
        target_datetime = datetime.combine(target_date, datetime.max.time())
        start_datetime = target_datetime - timedelta(hours=lookback_hours)

        max_mag = (
            session.query(func.max(EarthquakeEvent.magnitude))
            .filter(
                EarthquakeEvent.timestamp >= start_datetime,
                EarthquakeEvent.timestamp <= target_datetime,
                EarthquakeEvent.magnitude >= magnitude_threshold,
            )
            .scalar()
        )

        return float(max_mag) if max_mag else 0.0

    finally:
        session.close()


def calc_insurance_exposure_score(
    target_date: date,
    lookback_days: int = 7,
) -> Optional[float]:
    """Calculate insurance sector earthquake exposure score.

    Based on US seismic activity affecting property/casualty insurers.

    Args:
        target_date: Reference date
        lookback_days: Analysis window

    Returns:
        Exposure score (0-100)
    """
    # Focus on US zones
    us_zones = ["california", "pacific_northwest", "alaska"]
    total_exposure = 0

    for zone_name in us_zones:
        metrics = calc_regional_seismic_activity(
            zone_name, target_date, lookback_days, min_magnitude=4.0
        )
        if metrics and metrics["max_magnitude"]:
            # California has highest population density/property values
            zone_weight = 3.0 if zone_name == "california" else 1.0

            # Calculate zone exposure
            zone_exposure = (
                metrics["event_count"] * 2
                + (10 ** (metrics["max_magnitude"] - 4)) * zone_weight
            )
            total_exposure += zone_exposure

    # Normalize to 0-100
    return min(100, total_exposure)


def calc_supply_chain_disruption_risk(
    target_date: date,
    lookback_days: int = 7,
) -> Optional[Dict[str, float]]:
    """Calculate supply chain disruption risk by region.

    Focuses on semiconductor manufacturing regions (Taiwan, Japan).

    Args:
        target_date: Reference date
        lookback_days: Analysis window

    Returns:
        Dict with risk scores by region
    """
    risk_scores = {}

    for zone_name in ["taiwan", "japan"]:
        metrics = calc_regional_seismic_activity(
            zone_name, target_date, lookback_days, min_magnitude=4.0
        )
        if metrics and metrics["event_count"] > 0:
            # Calculate risk based on activity
            risk = (
                metrics["event_count"] * 5
                + (10 ** (metrics["max_magnitude"] - 4) if metrics["max_magnitude"] else 0) * 2
            )
            risk_scores[zone_name] = min(100, risk)
        else:
            risk_scores[zone_name] = 0.0

    return risk_scores


@FactorRegistry.register
class SeismicRiskIndex(BaseFactor):
    """Global Seismic Risk Index Factor.

    Measures overall global seismic activity level.
    Higher values indicate elevated seismic risk.

    Target: Insurance stocks (ALL, TRV, CB)
    """

    FACTOR_NAME = "seismic_risk_index"
    FACTOR_DESCRIPTION = "Global seismic activity index (0-100)"
    CATEGORY = "natural_disaster"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 30,
    ) -> Optional[float]:
        """Compute seismic risk index."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_seismic_risk_index(target_date, lookback_days)


@FactorRegistry.register
class MajorEarthquakeAlert(BaseFactor):
    """Major Earthquake Alert Factor.

    Flags major earthquake events in past 24-48 hours.
    Non-zero values indicate significant seismic event.

    Target: Insurance, reinsurance, affected regional stocks
    """

    FACTOR_NAME = "major_earthquake_alert"
    FACTOR_DESCRIPTION = "Maximum magnitude of M6+ events in past 24h"
    CATEGORY = "natural_disaster"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_hours: int = 24,
    ) -> Optional[float]:
        """Compute major earthquake alert."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_major_event_alert(target_date, lookback_hours)


@FactorRegistry.register
class InsuranceEarthquakeExposure(BaseFactor):
    """Insurance Earthquake Exposure Factor.

    US seismic activity affecting P&C insurers.
    Higher values indicate increased claims risk.

    Target: ALL, TRV, CB, PGR, BRK.B
    """

    FACTOR_NAME = "insurance_earthquake_exposure"
    FACTOR_DESCRIPTION = "US earthquake exposure score for insurers (0-100)"
    CATEGORY = "natural_disaster"
    ENTITY_TYPE = "company"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute insurance earthquake exposure."""
        if entity_id not in INSURANCE_TICKERS:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_insurance_exposure_score(target_date, lookback_days)


@FactorRegistry.register
class TaiwanSeismicRisk(BaseFactor):
    """Taiwan Seismic Risk Factor.

    Seismic activity in Taiwan semiconductor region.
    Affects TSMC and related semiconductor supply chain.

    Target: TSM, NVDA, AMD, INTC, QCOM
    """

    FACTOR_NAME = "taiwan_seismic_risk"
    FACTOR_DESCRIPTION = "Taiwan seismic activity risk score (0-100)"
    CATEGORY = "natural_disaster"
    ENTITY_TYPE = "company"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute Taiwan seismic risk."""
        taiwan_exposed = SEMICONDUCTOR_EXPOSURE.get("taiwan", [])
        if entity_id not in taiwan_exposed:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        risk_scores = calc_supply_chain_disruption_risk(target_date, lookback_days)
        return risk_scores.get("taiwan", 0.0)


@FactorRegistry.register
class CaliforniaSeismicActivity(BaseFactor):
    """California Seismic Activity Factor.

    Earthquake activity in California region.
    Affects California-based companies and real estate.

    Target: California REITs, insurers
    """

    FACTOR_NAME = "california_seismic_activity"
    FACTOR_DESCRIPTION = "California seismic event count (M4+)"
    CATEGORY = "natural_disaster"
    ENTITY_TYPE = "region"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 30,
    ) -> Optional[float]:
        """Compute California seismic activity."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        metrics = calc_regional_seismic_activity("california", target_date, lookback_days)

        if metrics:
            return float(metrics["event_count"])
        return 0.0
