"""OpenTable reservation-derived factor computations.

Factors derived from seated diners data for restaurant
and consumer discretionary sector analysis.
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Optional

from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.opentable import OpenTableMetrics
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


# Entity mapping for OpenTable factors
RESTAURANT_TICKERS = ["DRI", "MCD", "SBUX", "CMG", "YUM", "QSR", "WING", "CAVA"]
FOOD_DELIVERY = ["DASH", "UBER"]
CONSUMER_DISCRETIONARY = ["XLY"]


def calc_seated_diners_momentum(
    target_date: date,
    region: str = "US",
    lookback_weeks: int = 2,
) -> Optional[float]:
    """Calculate week-over-week change in YoY seated diners.

    Measures momentum in dining recovery/growth.

    Args:
        target_date: Reference date
        region: Geographic region
        lookback_weeks: Weeks to compare

    Returns:
        Change in YoY percentage (e.g., +5 means improvement)
    """
    session = SessionLocal()
    try:
        # Get most recent data point before target_date
        current_week = (
            session.query(OpenTableMetrics)
            .filter(
                OpenTableMetrics.week_ending <= target_date,
                OpenTableMetrics.region == region,
                OpenTableMetrics.city == None,
            )
            .order_by(OpenTableMetrics.week_ending.desc())
            .first()
        )

        if not current_week:
            return None

        # Get prior week data
        prior_date = current_week.week_ending - timedelta(days=7 * lookback_weeks)
        prior_week = (
            session.query(OpenTableMetrics)
            .filter(
                OpenTableMetrics.week_ending <= prior_date,
                OpenTableMetrics.region == region,
                OpenTableMetrics.city == None,
            )
            .order_by(OpenTableMetrics.week_ending.desc())
            .first()
        )

        if not prior_week:
            return None

        if current_week.yoy_seated_diners_pct is None or prior_week.yoy_seated_diners_pct is None:
            return None

        # Return change in YoY percentage
        return current_week.yoy_seated_diners_pct - prior_week.yoy_seated_diners_pct

    finally:
        session.close()


def calc_regional_dining_spread(
    target_date: date,
    regions: List[str] = None,
) -> Optional[float]:
    """Calculate spread between strongest and weakest regions.

    High spread indicates uneven recovery across regions.

    Args:
        target_date: Reference date
        regions: List of regions to include

    Returns:
        Max - Min YoY percentage spread
    """
    if regions is None:
        regions = ["US", "UK", "Germany", "Australia", "Canada"]

    session = SessionLocal()
    try:
        # Get most recent week
        latest_week = (
            session.query(func.max(OpenTableMetrics.week_ending))
            .filter(OpenTableMetrics.week_ending <= target_date)
            .scalar()
        )

        if not latest_week:
            return None

        # Get data for all regions for that week
        metrics = (
            session.query(OpenTableMetrics)
            .filter(
                OpenTableMetrics.week_ending == latest_week,
                OpenTableMetrics.region.in_(regions),
                OpenTableMetrics.city == None,
            )
            .all()
        )

        if len(metrics) < 2:
            return None

        values = [m.yoy_seated_diners_pct for m in metrics if m.yoy_seated_diners_pct is not None]

        if len(values) < 2:
            return None

        return max(values) - min(values)

    finally:
        session.close()


def calc_restaurant_sector_health(
    target_date: date,
    lookback_weeks: int = 4,
) -> Optional[float]:
    """Calculate composite restaurant sector health score.

    Rolling average of US seated diners YoY, normalized to 0-100 scale.

    Args:
        target_date: Reference date
        lookback_weeks: Weeks to average

    Returns:
        Health score (0-100)
    """
    session = SessionLocal()
    try:
        cutoff_date = target_date - timedelta(days=7 * lookback_weeks)

        avg_yoy = (
            session.query(func.avg(OpenTableMetrics.yoy_seated_diners_pct))
            .filter(
                OpenTableMetrics.week_ending >= cutoff_date,
                OpenTableMetrics.week_ending <= target_date,
                OpenTableMetrics.region == "US",
                OpenTableMetrics.city == None,
            )
            .scalar()
        )

        if avg_yoy is None:
            return None

        # Normalize: -50% YoY = 0, 0% YoY = 50, +50% YoY = 100
        return min(100, max(0, float(avg_yoy) + 50))

    finally:
        session.close()


def calc_dining_demand_index(
    target_date: date,
) -> Optional[float]:
    """Calculate current dining demand level.

    Uses latest YoY percentage as demand indicator.

    Args:
        target_date: Reference date

    Returns:
        Current YoY seated diners percentage for US
    """
    session = SessionLocal()
    try:
        latest = (
            session.query(OpenTableMetrics.yoy_seated_diners_pct)
            .filter(
                OpenTableMetrics.week_ending <= target_date,
                OpenTableMetrics.region == "US",
                OpenTableMetrics.city == None,
            )
            .order_by(OpenTableMetrics.week_ending.desc())
            .first()
        )

        if not latest or latest[0] is None:
            return None

        return float(latest[0])

    finally:
        session.close()


def calc_international_dining_momentum(
    target_date: date,
) -> Optional[float]:
    """Calculate average international dining momentum.

    Compares non-US markets to understand global trends.

    Args:
        target_date: Reference date

    Returns:
        Average YoY for non-US markets
    """
    intl_regions = ["UK", "Germany", "Australia", "Canada", "Ireland"]

    session = SessionLocal()
    try:
        latest_week = (
            session.query(func.max(OpenTableMetrics.week_ending))
            .filter(OpenTableMetrics.week_ending <= target_date)
            .scalar()
        )

        if not latest_week:
            return None

        avg_yoy = (
            session.query(func.avg(OpenTableMetrics.yoy_seated_diners_pct))
            .filter(
                OpenTableMetrics.week_ending == latest_week,
                OpenTableMetrics.region.in_(intl_regions),
                OpenTableMetrics.city == None,
            )
            .scalar()
        )

        if avg_yoy is None:
            return None

        return float(avg_yoy)

    finally:
        session.close()


@FactorRegistry.register
class SeatedDinersMomentum(BaseFactor):
    """Seated Diners Momentum Factor.

    Week-over-week change in YoY seated diners percentage.
    Positive momentum indicates improving restaurant demand.

    Target: DRI, MCD, SBUX, CMG, YUM
    """

    FACTOR_NAME = "seated_diners_momentum"
    FACTOR_DESCRIPTION = "Week-over-week change in YoY seated diners (%)"
    CATEGORY = "restaurant"
    ENTITY_TYPE = "company"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 14

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_weeks: int = 2,
    ) -> Optional[float]:
        """Compute seated diners momentum."""
        if entity_id not in RESTAURANT_TICKERS + FOOD_DELIVERY + [CONSUMER_DISCRETIONARY]:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_seated_diners_momentum(target_date, lookback_weeks=lookback_weeks)


@FactorRegistry.register
class RegionalDiningSpread(BaseFactor):
    """Regional Dining Spread Factor.

    Spread between strongest and weakest dining regions.
    High spread indicates uneven recovery patterns.

    Target: Global restaurant chains, travel companies
    """

    FACTOR_NAME = "regional_dining_spread"
    FACTOR_DESCRIPTION = "Max-min spread in YoY seated diners across regions"
    CATEGORY = "restaurant"
    ENTITY_TYPE = "market"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute regional dining spread."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_regional_dining_spread(target_date)


@FactorRegistry.register
class RestaurantSectorHealth(BaseFactor):
    """Restaurant Sector Health Factor.

    Composite health score for restaurant sector (0-100).
    Based on rolling average of seated diners YoY.

    Target: Restaurant stocks, consumer discretionary ETFs
    """

    FACTOR_NAME = "restaurant_sector_health"
    FACTOR_DESCRIPTION = "Restaurant sector health score (0-100)"
    CATEGORY = "restaurant"
    ENTITY_TYPE = "sector"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 28

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_weeks: int = 4,
    ) -> Optional[float]:
        """Compute restaurant sector health."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_restaurant_sector_health(target_date, lookback_weeks)


@FactorRegistry.register
class DiningDemandIndex(BaseFactor):
    """Dining Demand Index Factor.

    Current YoY seated diners percentage as demand indicator.
    Positive = above last year, negative = below.

    Target: Restaurants, food delivery, consumer staples
    """

    FACTOR_NAME = "dining_demand_index"
    FACTOR_DESCRIPTION = "Current US dining demand vs prior year (%)"
    CATEGORY = "restaurant"
    ENTITY_TYPE = "company"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute dining demand index."""
        if entity_id not in RESTAURANT_TICKERS + FOOD_DELIVERY:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_dining_demand_index(target_date)


@FactorRegistry.register
class InternationalDiningMomentum(BaseFactor):
    """International Dining Momentum Factor.

    Average YoY change across non-US markets.
    Useful for global restaurant chains.

    Target: Global QSR chains (MCD, YUM, QSR)
    """

    FACTOR_NAME = "international_dining_momentum"
    FACTOR_DESCRIPTION = "Average international market YoY seated diners (%)"
    CATEGORY = "restaurant"
    ENTITY_TYPE = "company"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute international dining momentum."""
        # Only for companies with significant international exposure
        global_chains = ["MCD", "YUM", "QSR", "SBUX"]
        if entity_id not in global_chains:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_international_dining_momentum(target_date)
