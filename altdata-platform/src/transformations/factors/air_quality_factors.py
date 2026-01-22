"""Air quality-derived factor computations."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from haversine import haversine, Unit
from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.air_quality import (
    AirQualityLocation,
    AirQualityMeasurement,
    AirQualityDaily,
    IndustrialZone,
)
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


def calc_air_quality_anomaly(
    location_id: str,
    as_of_date: datetime,
    parameter: str = "pm25",
    lookback_days: int = 30,
) -> Optional[float]:
    """Calculate air quality anomaly vs historical baseline.

    Significant deviations may indicate industrial activity changes.

    Args:
        location_id: OpenAQ location ID
        as_of_date: Reference timestamp
        parameter: Air quality parameter (pm25, no2, etc.)
        lookback_days: Days for baseline calculation

    Returns:
        Z-score of current value vs baseline
    """
    session = SessionLocal()
    try:
        # Get baseline statistics
        baseline_start = as_of_date - timedelta(days=lookback_days)
        baseline_end = as_of_date - timedelta(days=1)

        baseline_stats = (
            session.query(
                func.avg(AirQualityMeasurement.value).label("avg"),
                func.stddev(AirQualityMeasurement.value).label("std"),
            )
            .filter(
                AirQualityMeasurement.location_id == location_id,
                AirQualityMeasurement.parameter == parameter,
                AirQualityMeasurement.timestamp >= baseline_start,
                AirQualityMeasurement.timestamp <= baseline_end,
            )
            .first()
        )

        if not baseline_stats or baseline_stats.avg is None:
            return None

        baseline_avg = float(baseline_stats.avg)
        baseline_std = float(baseline_stats.std) if baseline_stats.std else 1.0

        # Get current day average
        day_start = as_of_date.replace(hour=0, minute=0, second=0)
        day_end = as_of_date

        current_avg = (
            session.query(func.avg(AirQualityMeasurement.value))
            .filter(
                AirQualityMeasurement.location_id == location_id,
                AirQualityMeasurement.parameter == parameter,
                AirQualityMeasurement.timestamp >= day_start,
                AirQualityMeasurement.timestamp <= day_end,
            )
            .scalar()
        )

        if current_avg is None:
            return None

        # Calculate z-score
        if baseline_std == 0:
            return 0.0

        z_score = (float(current_avg) - baseline_avg) / baseline_std
        return z_score

    finally:
        session.close()


def calc_industrial_activity_proxy(
    zone_id: str,
    as_of_date: datetime,
    lookback_hours: int = 24,
) -> Optional[float]:
    """Calculate industrial activity proxy from nearby air quality.

    High pollution levels near industrial zones suggest activity.

    Args:
        zone_id: Industrial zone ID
        as_of_date: Reference timestamp
        lookback_hours: Hours of data to analyze

    Returns:
        Activity proxy score (average PM2.5 level)
    """
    session = SessionLocal()
    try:
        # Get industrial zone
        zone = session.query(IndustrialZone).filter_by(zone_id=zone_id).first()
        if not zone:
            return None

        zone_coords = (zone.latitude, zone.longitude)
        radius_km = zone.radius_km or 10.0

        # Find nearby monitoring locations
        locations = session.query(AirQualityLocation).all()
        nearby_location_ids = []

        for loc in locations:
            if loc.latitude and loc.longitude:
                loc_coords = (loc.latitude, loc.longitude)
                distance = haversine(zone_coords, loc_coords, unit=Unit.KILOMETERS)
                if distance <= radius_km:
                    nearby_location_ids.append(loc.location_id)

        if not nearby_location_ids:
            return None

        # Get average PM2.5 from nearby locations
        start_time = as_of_date - timedelta(hours=lookback_hours)

        avg_pm25 = (
            session.query(func.avg(AirQualityMeasurement.value))
            .filter(
                AirQualityMeasurement.location_id.in_(nearby_location_ids),
                AirQualityMeasurement.parameter == "pm25",
                AirQualityMeasurement.timestamp >= start_time,
                AirQualityMeasurement.timestamp <= as_of_date,
            )
            .scalar()
        )

        return float(avg_pm25) if avg_pm25 else None

    finally:
        session.close()


def calc_pollution_trend(
    location_id: str,
    as_of_date: datetime,
    parameter: str = "pm25",
    current_days: int = 7,
    baseline_days: int = 30,
) -> Optional[float]:
    """Calculate pollution trend vs baseline.

    Args:
        location_id: OpenAQ location ID
        as_of_date: Reference timestamp
        parameter: Air quality parameter
        current_days: Days for current period
        baseline_days: Days for baseline period

    Returns:
        Percentage change vs baseline
    """
    session = SessionLocal()
    try:
        # Current period average
        current_start = as_of_date - timedelta(days=current_days)
        current_avg = (
            session.query(func.avg(AirQualityMeasurement.value))
            .filter(
                AirQualityMeasurement.location_id == location_id,
                AirQualityMeasurement.parameter == parameter,
                AirQualityMeasurement.timestamp >= current_start,
                AirQualityMeasurement.timestamp <= as_of_date,
            )
            .scalar()
        )

        # Baseline period average
        baseline_start = current_start - timedelta(days=baseline_days)
        baseline_end = current_start - timedelta(days=1)
        baseline_avg = (
            session.query(func.avg(AirQualityMeasurement.value))
            .filter(
                AirQualityMeasurement.location_id == location_id,
                AirQualityMeasurement.parameter == parameter,
                AirQualityMeasurement.timestamp >= baseline_start,
                AirQualityMeasurement.timestamp <= baseline_end,
            )
            .scalar()
        )

        if not current_avg or not baseline_avg or baseline_avg == 0:
            return None

        return ((float(current_avg) - float(baseline_avg)) / float(baseline_avg)) * 100

    finally:
        session.close()


def calc_regional_aqi(
    city: str,
    as_of_date: datetime,
    lookback_hours: int = 24,
) -> Optional[float]:
    """Calculate regional average Air Quality Index.

    Args:
        city: City name
        as_of_date: Reference timestamp
        lookback_hours: Hours of data to average

    Returns:
        Average AQI for the region
    """
    session = SessionLocal()
    try:
        # Get locations in city
        locations = (
            session.query(AirQualityLocation.location_id)
            .filter(AirQualityLocation.city == city)
            .all()
        )

        location_ids = [loc.location_id for loc in locations]
        if not location_ids:
            return None

        start_time = as_of_date - timedelta(hours=lookback_hours)

        # Get average PM2.5
        avg_pm25 = (
            session.query(func.avg(AirQualityMeasurement.value))
            .filter(
                AirQualityMeasurement.location_id.in_(location_ids),
                AirQualityMeasurement.parameter == "pm25",
                AirQualityMeasurement.timestamp >= start_time,
                AirQualityMeasurement.timestamp <= as_of_date,
            )
            .scalar()
        )

        if not avg_pm25:
            return None

        # Convert to AQI using EPA formula
        from src.collectors.openaq import OpenAQCollector
        collector = OpenAQCollector()
        return float(collector.calculate_aqi(float(avg_pm25)))

    finally:
        session.close()


@FactorRegistry.register
class AirQualityAnomaly(BaseFactor):
    """Air Quality Anomaly Factor.

    Measures deviation from baseline air quality,
    potential indicator of industrial activity changes.
    """

    FACTOR_NAME = "air_quality_anomaly"
    FACTOR_DESCRIPTION = "Z-score of air quality vs 30-day baseline"
    CATEGORY = "air_quality"
    ENTITY_TYPE = "location"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,  # Location ID
        as_of_date: datetime,
        parameter: str = "pm25",
        lookback_days: int = 30,
    ) -> Optional[float]:
        """Compute air quality anomaly.

        Args:
            entity_id: OpenAQ location ID
            as_of_date: Date for computation
            parameter: Air quality parameter
            lookback_days: Baseline period

        Returns:
            Z-score of current vs baseline
        """
        return calc_air_quality_anomaly(entity_id, as_of_date, parameter, lookback_days)


@FactorRegistry.register
class IndustrialActivityProxy(BaseFactor):
    """Industrial Activity Proxy Factor.

    Estimates industrial activity from nearby air pollution levels.
    """

    FACTOR_NAME = "industrial_activity_proxy"
    FACTOR_DESCRIPTION = "Industrial activity estimate from air quality"
    CATEGORY = "air_quality"
    ENTITY_TYPE = "industrial_zone"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,  # Industrial zone ID
        as_of_date: datetime,
        lookback_hours: int = 24,
    ) -> Optional[float]:
        """Compute industrial activity proxy.

        Args:
            entity_id: Industrial zone ID
            as_of_date: Date for computation
            lookback_hours: Hours to analyze

        Returns:
            Activity proxy score
        """
        return calc_industrial_activity_proxy(entity_id, as_of_date, lookback_hours)


@FactorRegistry.register
class PollutionTrend(BaseFactor):
    """Pollution Trend Factor.

    Measures change in pollution levels vs baseline.
    """

    FACTOR_NAME = "pollution_trend"
    FACTOR_DESCRIPTION = "Percentage change in pollution vs baseline"
    CATEGORY = "air_quality"
    ENTITY_TYPE = "location"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        parameter: str = "pm25",
    ) -> Optional[float]:
        """Compute pollution trend.

        Args:
            entity_id: Location ID
            as_of_date: Date for computation
            parameter: Air quality parameter

        Returns:
            Percentage change
        """
        return calc_pollution_trend(entity_id, as_of_date, parameter)


@FactorRegistry.register
class RegionalAQI(BaseFactor):
    """Regional Air Quality Index Factor.

    Average AQI for a city/region.
    """

    FACTOR_NAME = "regional_aqi"
    FACTOR_DESCRIPTION = "Average Air Quality Index for a region"
    CATEGORY = "air_quality"
    ENTITY_TYPE = "city"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,  # City name
        as_of_date: datetime,
        lookback_hours: int = 24,
    ) -> Optional[float]:
        """Compute regional AQI.

        Args:
            entity_id: City name
            as_of_date: Date for computation
            lookback_hours: Hours to average

        Returns:
            Average AQI
        """
        return calc_regional_aqi(entity_id, as_of_date, lookback_hours)
