"""Carbon intensity-derived factor computations.

Factors derived from UK Carbon Intensity data for ESG
and energy transition analysis.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.carbon_intensity import CarbonIntensityReading
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


# Entity mapping for carbon intensity factors
UK_UTILITIES = ["NG.L", "SSE.L"]  # National Grid, SSE
CLEAN_ENERGY = ["ENPH", "SEDG", "FSLR", "RUN", "ICLN"]  # Solar/clean energy
ESG_ETFS = ["ESGU", "ESGV", "SUSA"]


def calc_carbon_intensity_trend(
    target_date: date,
    lookback_days: int = 30,
) -> Optional[float]:
    """Calculate trend in carbon intensity.

    Compares recent average to prior period.

    Args:
        target_date: Reference date
        lookback_days: Comparison window

    Returns:
        Percentage change in carbon intensity
    """
    session = SessionLocal()
    try:
        target_datetime = datetime.combine(target_date, datetime.max.time())

        # Recent average (last 7 days)
        recent_start = target_datetime - timedelta(days=7)
        recent_avg = (
            session.query(func.avg(CarbonIntensityReading.intensity_actual))
            .filter(
                CarbonIntensityReading.timestamp >= recent_start,
                CarbonIntensityReading.timestamp <= target_datetime,
                CarbonIntensityReading.region == "national",
            )
            .scalar()
        )

        # Prior period average
        prior_end = target_datetime - timedelta(days=7)
        prior_start = target_datetime - timedelta(days=lookback_days)
        prior_avg = (
            session.query(func.avg(CarbonIntensityReading.intensity_actual))
            .filter(
                CarbonIntensityReading.timestamp >= prior_start,
                CarbonIntensityReading.timestamp <= prior_end,
                CarbonIntensityReading.region == "national",
            )
            .scalar()
        )

        if not prior_avg or prior_avg == 0:
            return None

        return ((float(recent_avg) - float(prior_avg)) / float(prior_avg)) * 100

    finally:
        session.close()


def calc_renewable_share(
    target_date: date,
    lookback_hours: int = 24,
) -> Optional[float]:
    """Calculate renewable energy share in generation mix.

    Args:
        target_date: Reference date
        lookback_hours: Hours to average

    Returns:
        Percentage of generation from renewables
    """
    session = SessionLocal()
    try:
        target_datetime = datetime.combine(target_date, datetime.max.time())
        start_datetime = target_datetime - timedelta(hours=lookback_hours)

        # Get average of renewable percentages
        avg_solar = (
            session.query(func.avg(CarbonIntensityReading.pct_solar))
            .filter(
                CarbonIntensityReading.timestamp >= start_datetime,
                CarbonIntensityReading.timestamp <= target_datetime,
                CarbonIntensityReading.region == "national",
            )
            .scalar()
        ) or 0

        avg_wind = (
            session.query(func.avg(CarbonIntensityReading.pct_wind))
            .filter(
                CarbonIntensityReading.timestamp >= start_datetime,
                CarbonIntensityReading.timestamp <= target_datetime,
                CarbonIntensityReading.region == "national",
            )
            .scalar()
        ) or 0

        avg_hydro = (
            session.query(func.avg(CarbonIntensityReading.pct_hydro))
            .filter(
                CarbonIntensityReading.timestamp >= start_datetime,
                CarbonIntensityReading.timestamp <= target_datetime,
                CarbonIntensityReading.region == "national",
            )
            .scalar()
        ) or 0

        return float(avg_solar) + float(avg_wind) + float(avg_hydro)

    finally:
        session.close()


def calc_renewable_share_growth(
    target_date: date,
    lookback_days: int = 30,
) -> Optional[float]:
    """Calculate growth in renewable energy share.

    Args:
        target_date: Reference date
        lookback_days: Comparison period

    Returns:
        Change in renewable percentage points
    """
    session = SessionLocal()
    try:
        target_datetime = datetime.combine(target_date, datetime.max.time())

        # Recent renewable share (last 7 days)
        recent_start = target_datetime - timedelta(days=7)
        recent_share = calc_renewable_share(target_date, 168)  # 7 days in hours

        # Prior period
        prior_date = target_date - timedelta(days=lookback_days)
        prior_share = calc_renewable_share(prior_date, 168)

        if recent_share is None or prior_share is None:
            return None

        return recent_share - prior_share  # Percentage point change

    finally:
        session.close()


def calc_grid_carbon_intensity(
    target_date: date,
) -> Optional[float]:
    """Get latest grid carbon intensity.

    Args:
        target_date: Reference date

    Returns:
        Carbon intensity in gCO2/kWh
    """
    session = SessionLocal()
    try:
        target_datetime = datetime.combine(target_date, datetime.max.time())

        latest = (
            session.query(CarbonIntensityReading.intensity_actual)
            .filter(
                CarbonIntensityReading.timestamp <= target_datetime,
                CarbonIntensityReading.region == "national",
            )
            .order_by(CarbonIntensityReading.timestamp.desc())
            .first()
        )

        if latest and latest[0]:
            return float(latest[0])
        return None

    finally:
        session.close()


def calc_low_carbon_hours_ratio(
    target_date: date,
    threshold: float = 150,  # gCO2/kWh threshold for "low carbon"
    lookback_hours: int = 24,
) -> Optional[float]:
    """Calculate ratio of low-carbon hours.

    Args:
        target_date: Reference date
        threshold: Carbon intensity threshold
        lookback_hours: Hours to analyze

    Returns:
        Ratio of hours below threshold (0-1)
    """
    session = SessionLocal()
    try:
        target_datetime = datetime.combine(target_date, datetime.max.time())
        start_datetime = target_datetime - timedelta(hours=lookback_hours)

        total_readings = (
            session.query(func.count(CarbonIntensityReading.id))
            .filter(
                CarbonIntensityReading.timestamp >= start_datetime,
                CarbonIntensityReading.timestamp <= target_datetime,
                CarbonIntensityReading.region == "national",
                CarbonIntensityReading.intensity_actual.isnot(None),
            )
            .scalar()
        ) or 0

        if total_readings == 0:
            return None

        low_carbon_readings = (
            session.query(func.count(CarbonIntensityReading.id))
            .filter(
                CarbonIntensityReading.timestamp >= start_datetime,
                CarbonIntensityReading.timestamp <= target_datetime,
                CarbonIntensityReading.region == "national",
                CarbonIntensityReading.intensity_actual <= threshold,
            )
            .scalar()
        ) or 0

        return low_carbon_readings / total_readings

    finally:
        session.close()


@FactorRegistry.register
class CarbonIntensityTrend(BaseFactor):
    """Carbon Intensity Trend Factor.

    Change in grid carbon intensity vs prior period.
    Declining trend indicates energy transition progress.

    Target: UK utilities, ESG-focused funds
    """

    FACTOR_NAME = "carbon_intensity_trend"
    FACTOR_DESCRIPTION = "Change in UK grid carbon intensity (%)"
    CATEGORY = "esg"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 30,
    ) -> Optional[float]:
        """Compute carbon intensity trend."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_carbon_intensity_trend(target_date, lookback_days)


@FactorRegistry.register
class RenewableShareGrowth(BaseFactor):
    """Renewable Share Growth Factor.

    Change in renewable energy percentage in grid mix.
    Positive growth indicates energy transition.

    Target: Clean energy stocks, ESG ETFs
    """

    FACTOR_NAME = "renewable_share_growth"
    FACTOR_DESCRIPTION = "Change in renewable energy share (percentage points)"
    CATEGORY = "esg"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 30,
    ) -> Optional[float]:
        """Compute renewable share growth."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_renewable_share_growth(target_date, lookback_days)


@FactorRegistry.register
class GridCarbonIntensity(BaseFactor):
    """Grid Carbon Intensity Factor.

    Current UK grid carbon intensity in gCO2/kWh.
    Lower values indicate cleaner grid.

    Target: UK utilities, carbon markets
    """

    FACTOR_NAME = "grid_carbon_intensity"
    FACTOR_DESCRIPTION = "UK grid carbon intensity (gCO2/kWh)"
    CATEGORY = "esg"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute grid carbon intensity."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_grid_carbon_intensity(target_date)


@FactorRegistry.register
class RenewableEnergyShare(BaseFactor):
    """Renewable Energy Share Factor.

    Percentage of generation from renewable sources.
    Higher = cleaner grid.

    Target: Clean energy stocks
    """

    FACTOR_NAME = "renewable_energy_share"
    FACTOR_DESCRIPTION = "Renewable energy share in UK grid (%)"
    CATEGORY = "esg"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_hours: int = 24,
    ) -> Optional[float]:
        """Compute renewable energy share."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_renewable_share(target_date, lookback_hours)


@FactorRegistry.register
class LowCarbonHoursRatio(BaseFactor):
    """Low Carbon Hours Ratio Factor.

    Ratio of hours with carbon intensity below threshold.
    Higher ratio indicates cleaner overall grid.

    Target: ESG funds, carbon markets
    """

    FACTOR_NAME = "low_carbon_hours_ratio"
    FACTOR_DESCRIPTION = "Ratio of low-carbon hours in past 24h (0-1)"
    CATEGORY = "esg"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        threshold: float = 150,
    ) -> Optional[float]:
        """Compute low carbon hours ratio."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_low_carbon_hours_ratio(target_date, threshold)
