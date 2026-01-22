"""Weather-derived factor computations."""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.weather import WeatherObservation, WeatherDaily, WeatherAlert
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


def calc_heating_degree_days(
    location_id: str,
    start_date: datetime,
    end_date: datetime,
    base_temp: float = 18.0,
) -> Optional[float]:
    """Calculate Heating Degree Days - proxy for energy demand.

    HDD = max(0, base_temp - avg_temp) summed over period.

    Args:
        location_id: Weather location ID
        start_date: Start of period
        end_date: End of period
        base_temp: Base temperature in Celsius (default 18)

    Returns:
        Total heating degree days
    """
    session = SessionLocal()
    try:
        observations = (
            session.query(
                func.date(WeatherObservation.timestamp).label('obs_date'),
                func.avg(WeatherObservation.temp_c).label('avg_temp')
            )
            .filter(
                WeatherObservation.location_id == location_id,
                WeatherObservation.timestamp >= start_date,
                WeatherObservation.timestamp <= end_date,
                WeatherObservation.temp_c.isnot(None),
            )
            .group_by(func.date(WeatherObservation.timestamp))
            .all()
        )

        if not observations:
            return None

        hdd = sum(max(0, base_temp - obs.avg_temp) for obs in observations)
        return hdd
    finally:
        session.close()


def calc_cooling_degree_days(
    location_id: str,
    start_date: datetime,
    end_date: datetime,
    base_temp: float = 18.0,
) -> Optional[float]:
    """Calculate Cooling Degree Days - proxy for AC/electricity demand.

    CDD = max(0, avg_temp - base_temp) summed over period.

    Args:
        location_id: Weather location ID
        start_date: Start of period
        end_date: End of period
        base_temp: Base temperature in Celsius

    Returns:
        Total cooling degree days
    """
    session = SessionLocal()
    try:
        observations = (
            session.query(
                func.date(WeatherObservation.timestamp).label('obs_date'),
                func.avg(WeatherObservation.temp_c).label('avg_temp')
            )
            .filter(
                WeatherObservation.location_id == location_id,
                WeatherObservation.timestamp >= start_date,
                WeatherObservation.timestamp <= end_date,
                WeatherObservation.temp_c.isnot(None),
            )
            .group_by(func.date(WeatherObservation.timestamp))
            .all()
        )

        if not observations:
            return None

        cdd = sum(max(0, obs.avg_temp - base_temp) for obs in observations)
        return cdd
    finally:
        session.close()


def calc_retail_weather_index(
    cities: List[str],
    target_date: date,
) -> Optional[float]:
    """Calculate composite index of weather favorability for retail foot traffic.

    Optimal: 15-25C, no precipitation, low wind.

    Args:
        cities: List of location IDs
        target_date: Date to calculate for

    Returns:
        Retail weather score (0-100)
    """
    session = SessionLocal()
    try:
        scores = []

        for city in cities:
            # Get latest observation for the date
            obs = (
                session.query(WeatherObservation)
                .filter(
                    WeatherObservation.location_id == city,
                    func.date(WeatherObservation.timestamp) == target_date,
                )
                .order_by(WeatherObservation.timestamp.desc())
                .first()
            )

            if not obs or obs.temp_c is None:
                continue

            score = 100

            # Temperature penalty
            if obs.temp_c < 5 or obs.temp_c > 35:
                score -= 40
            elif obs.temp_c < 10 or obs.temp_c > 30:
                score -= 20
            elif obs.temp_c < 15 or obs.temp_c > 25:
                score -= 10

            # Precipitation penalty
            if (obs.rain_1h_mm or 0) > 5 or (obs.snow_1h_mm or 0) > 0:
                score -= 30
            elif (obs.rain_1h_mm or 0) > 0:
                score -= 15

            # Wind penalty
            if (obs.wind_speed_ms or 0) > 15:
                score -= 20
            elif (obs.wind_speed_ms or 0) > 10:
                score -= 10

            scores.append(max(0, score))

        return np.mean(scores) if scores else None
    finally:
        session.close()


def calc_agricultural_stress_index(
    region: str,
    start_date: datetime,
    end_date: datetime,
) -> Optional[float]:
    """Calculate index of agricultural weather stress.

    Higher = more stress = potential crop issues.

    Args:
        region: Region name (midwest, california, southeast)
        start_date: Start of period
        end_date: End of period

    Returns:
        Agricultural stress score
    """
    REGION_CITIES = {
        "midwest": ["des_moines_us", "omaha_us", "chicago_us"],
        "california": ["fresno_us", "los_angeles_us"],
        "southeast": ["atlanta_us", "miami_us"],
    }

    cities = REGION_CITIES.get(region.lower(), [])
    if not cities:
        return None

    session = SessionLocal()
    try:
        observations = (
            session.query(WeatherObservation)
            .filter(
                WeatherObservation.location_id.in_(cities),
                WeatherObservation.timestamp >= start_date,
                WeatherObservation.timestamp <= end_date,
            )
            .all()
        )

        if not observations:
            return None

        stress_score = 0

        for obs in observations:
            # Heat stress
            if obs.temp_c and obs.temp_c > 35:
                stress_score += 2
            elif obs.temp_c and obs.temp_c > 32:
                stress_score += 1

            # Frost stress
            if obs.temp_c and obs.temp_c < 0:
                stress_score += 3
            elif obs.temp_c and obs.temp_c < 2:
                stress_score += 1

            # Drought indicator (low humidity + high temp + no rain)
            if (obs.humidity_pct and obs.humidity_pct < 30 and
                obs.temp_c and obs.temp_c > 25 and
                not obs.rain_1h_mm):
                stress_score += 1

        # Normalize by number of observations
        return stress_score / len(observations) if observations else 0
    finally:
        session.close()


def calc_weather_yoy_anomaly(
    location_id: str,
    target_date: date,
    metric: str = "temp_c",
) -> Optional[float]:
    """Calculate year-over-year weather anomaly.

    Args:
        location_id: Weather location ID
        target_date: Reference date
        metric: Weather metric to compare

    Returns:
        Difference from same period last year
    """
    session = SessionLocal()
    try:
        current_start = target_date - timedelta(days=7)
        current_end = target_date
        prior_start = current_start - timedelta(days=365)
        prior_end = current_end - timedelta(days=365)

        current_avg = (
            session.query(func.avg(getattr(WeatherObservation, metric)))
            .filter(
                WeatherObservation.location_id == location_id,
                func.date(WeatherObservation.timestamp) >= current_start,
                func.date(WeatherObservation.timestamp) <= current_end,
            )
            .scalar()
        )

        prior_avg = (
            session.query(func.avg(getattr(WeatherObservation, metric)))
            .filter(
                WeatherObservation.location_id == location_id,
                func.date(WeatherObservation.timestamp) >= prior_start,
                func.date(WeatherObservation.timestamp) <= prior_end,
            )
            .scalar()
        )

        if current_avg is None or prior_avg is None:
            return None

        return float(current_avg) - float(prior_avg)
    finally:
        session.close()


def calc_precipitation_anomaly(
    location_id: str,
    target_date: date,
    lookback_days: int = 30,
) -> Optional[float]:
    """Calculate precipitation anomaly vs historical average.

    Args:
        location_id: Weather location ID
        target_date: Reference date
        lookback_days: Days to look back

    Returns:
        Precipitation anomaly (current - historical)
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        # Current period precipitation
        current_precip = (
            session.query(func.sum(WeatherObservation.rain_1h_mm))
            .filter(
                WeatherObservation.location_id == location_id,
                func.date(WeatherObservation.timestamp) >= start_date,
                func.date(WeatherObservation.timestamp) <= target_date,
            )
            .scalar()
        ) or 0

        # Same period last year
        prior_start = start_date - timedelta(days=365)
        prior_end = target_date - timedelta(days=365)

        prior_precip = (
            session.query(func.sum(WeatherObservation.rain_1h_mm))
            .filter(
                WeatherObservation.location_id == location_id,
                func.date(WeatherObservation.timestamp) >= prior_start,
                func.date(WeatherObservation.timestamp) <= prior_end,
            )
            .scalar()
        ) or 0

        return float(current_precip) - float(prior_precip)
    finally:
        session.close()


@FactorRegistry.register
class HeatingDegreeDays(BaseFactor):
    """Heating Degree Days Factor.

    Measures cumulative heating demand based on temperature.
    Higher values indicate more energy needed for heating.
    """

    FACTOR_NAME = "heating_degree_days"
    FACTOR_DESCRIPTION = "Cumulative heating degree days (base 18C)"
    CATEGORY = "weather"
    ENTITY_TYPE = "location"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,  # Location ID
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute heating degree days."""
        start_date = as_of_date - timedelta(days=lookback_days)
        return calc_heating_degree_days(entity_id, start_date, as_of_date)


@FactorRegistry.register
class CoolingDegreeDays(BaseFactor):
    """Cooling Degree Days Factor.

    Measures cumulative cooling demand based on temperature.
    Higher values indicate more energy needed for cooling.
    """

    FACTOR_NAME = "cooling_degree_days"
    FACTOR_DESCRIPTION = "Cumulative cooling degree days (base 18C)"
    CATEGORY = "weather"
    ENTITY_TYPE = "location"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute cooling degree days."""
        start_date = as_of_date - timedelta(days=lookback_days)
        return calc_cooling_degree_days(entity_id, start_date, as_of_date)


@FactorRegistry.register
class RetailWeatherIndex(BaseFactor):
    """Retail Weather Index Factor.

    Composite score of weather favorability for retail foot traffic.
    Higher = better shopping weather.
    """

    FACTOR_NAME = "retail_weather_index"
    FACTOR_DESCRIPTION = "Weather favorability for retail (0-100)"
    CATEGORY = "weather"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    # Default cities for index
    DEFAULT_CITIES = [
        "new_york_us", "los_angeles_us", "chicago_us",
        "houston_us", "dallas_us", "atlanta_us"
    ]

    def compute(
        self,
        entity_id: str,  # Ignored, uses default cities
        as_of_date: datetime,
        cities: List[str] = None,
    ) -> Optional[float]:
        """Compute retail weather index."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        city_list = cities or self.DEFAULT_CITIES
        return calc_retail_weather_index(city_list, target_date)


@FactorRegistry.register
class AgriculturalStressIndex(BaseFactor):
    """Agricultural Stress Index Factor.

    Measures weather-related agricultural stress.
    Higher = more stress = potential crop issues.
    """

    FACTOR_NAME = "agricultural_stress_index"
    FACTOR_DESCRIPTION = "Agricultural weather stress score"
    CATEGORY = "weather"
    ENTITY_TYPE = "region"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,  # Region name
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute agricultural stress index."""
        start_date = as_of_date - timedelta(days=lookback_days)
        return calc_agricultural_stress_index(entity_id, start_date, as_of_date)


@FactorRegistry.register
class WeatherYoYAnomaly(BaseFactor):
    """Weather Year-over-Year Anomaly Factor.

    Measures temperature deviation from same period last year.
    """

    FACTOR_NAME = "weather_yoy_anomaly"
    FACTOR_DESCRIPTION = "Temperature anomaly vs same period last year"
    CATEGORY = "weather"
    ENTITY_TYPE = "location"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,  # Location ID
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute weather YoY anomaly."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_weather_yoy_anomaly(entity_id, target_date)


@FactorRegistry.register
class PrecipitationAnomaly(BaseFactor):
    """Precipitation Anomaly Factor.

    Measures precipitation deviation from same period last year.
    """

    FACTOR_NAME = "precipitation_anomaly"
    FACTOR_DESCRIPTION = "Precipitation anomaly vs same period last year"
    CATEGORY = "weather"
    ENTITY_TYPE = "location"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 30,
    ) -> Optional[float]:
        """Compute precipitation anomaly."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_precipitation_anomaly(entity_id, target_date, lookback_days)


def calc_severe_weather_exposure(
    entity_id: str,
    as_of_date: datetime,
    lookback_hours: int = 72,
) -> Optional[float]:
    """Calculate severe weather exposure for a company.

    Counts weather alerts affecting company locations.
    Higher values indicate greater operational risk.

    Args:
        entity_id: Company entity ID
        as_of_date: Reference timestamp
        lookback_hours: Hours to look back for alerts

    Returns:
        Severity-weighted alert count
    """
    session = SessionLocal()
    try:
        from src.models.schemas import Entity

        # Get company entity to find associated locations
        entity = session.query(Entity).filter_by(id=entity_id).first()
        if not entity:
            return None

        # Get company locations from metadata
        locations = []
        if entity.extra_data and 'locations' in entity.extra_data:
            locations = entity.extra_data['locations']
        elif entity.extra_data and 'headquarters' in entity.extra_data:
            locations = [entity.extra_data['headquarters']]

        if not locations:
            # Default to major US cities if no specific locations
            locations = ["new_york_us", "los_angeles_us", "chicago_us"]

        start_time = as_of_date - timedelta(hours=lookback_hours)

        # Severity weights
        SEVERITY_WEIGHTS = {
            "extreme": 4.0,
            "severe": 3.0,
            "moderate": 2.0,
            "minor": 1.0,
            "watch": 0.5,
            "advisory": 0.25,
        }

        total_exposure = 0.0

        for location in locations:
            # Query weather alerts for this location
            alerts = (
                session.query(WeatherAlert)
                .filter(
                    WeatherAlert.location_id == location,
                    WeatherAlert.start_time <= as_of_date,
                    WeatherAlert.end_time >= start_time,
                )
                .all()
            )

            for alert in alerts:
                severity = (alert.severity or "minor").lower()
                weight = SEVERITY_WEIGHTS.get(severity, 1.0)
                total_exposure += weight

        return total_exposure

    finally:
        session.close()


@FactorRegistry.register
class SevereWeatherExposure(BaseFactor):
    """Severe Weather Exposure Factor.

    Measures company exposure to severe weather events.
    Higher values indicate greater operational risk.
    """

    FACTOR_NAME = "severe_weather_exposure"
    FACTOR_DESCRIPTION = "Severity-weighted weather alert exposure"
    CATEGORY = "weather"
    ENTITY_TYPE = "company"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 3

    def compute(
        self,
        entity_id: str,  # Company entity ID
        as_of_date: datetime,
        lookback_hours: int = 72,
    ) -> Optional[float]:
        """Compute severe weather exposure.

        Args:
            entity_id: Company entity ID
            as_of_date: Date for computation
            lookback_hours: Hours to look back

        Returns:
            Severity-weighted exposure score
        """
        return calc_severe_weather_exposure(entity_id, as_of_date, lookback_hours)
