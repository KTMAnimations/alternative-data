"""TSA checkpoint-derived factor computations.

Factors derived from TSA passenger throughput data for
airline and travel sector analysis.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.tsa import TSACheckpoint
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


# Entity mapping for TSA factors
AIRLINE_TICKERS = ["DAL", "UAL", "AAL", "LUV", "JBLU", "SAVE", "ALK"]
SECTOR_ETF = "JETS"
TRAVEL_RELATED = ["MAR", "HLT", "H", "BKNG", "EXPE"]


def calc_tsa_throughput_momentum(
    target_date: date,
    lookback_days: int = 7,
) -> Optional[float]:
    """Calculate TSA throughput momentum.

    7-day moving average compared to same period prior year.

    Args:
        target_date: Reference date
        lookback_days: Rolling window size

    Returns:
        Percentage change vs prior year
    """
    session = SessionLocal()
    try:
        # Current period average
        current_start = target_date - timedelta(days=lookback_days - 1)
        current_avg = (
            session.query(func.avg(TSACheckpoint.current_year_throughput))
            .filter(
                TSACheckpoint.date >= current_start,
                TSACheckpoint.date <= target_date,
            )
            .scalar()
        )

        if not current_avg:
            return None

        # Same period prior year
        prior_start = target_date - timedelta(days=365 + lookback_days - 1)
        prior_end = target_date - timedelta(days=365)
        prior_avg = (
            session.query(func.avg(TSACheckpoint.current_year_throughput))
            .filter(
                TSACheckpoint.date >= prior_start,
                TSACheckpoint.date <= prior_end,
            )
            .scalar()
        )

        if not prior_avg or prior_avg == 0:
            return None

        return ((float(current_avg) - float(prior_avg)) / float(prior_avg)) * 100

    finally:
        session.close()


def calc_tsa_weekday_weekend_ratio(
    target_date: date,
    lookback_days: int = 14,
) -> Optional[float]:
    """Calculate weekday to weekend travel ratio.

    Higher ratio indicates more business travel, lower ratio
    indicates more leisure travel.

    Args:
        target_date: Reference date
        lookback_days: Analysis window

    Returns:
        Ratio of weekday to weekend throughput
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days - 1)

        # Weekday average (Mon-Fri, day_of_week 0-4)
        weekday_avg = (
            session.query(func.avg(TSACheckpoint.current_year_throughput))
            .filter(
                TSACheckpoint.date >= start_date,
                TSACheckpoint.date <= target_date,
                TSACheckpoint.day_of_week.in_([0, 1, 2, 3, 4]),
            )
            .scalar()
        )

        # Weekend average (Sat-Sun, day_of_week 5-6)
        weekend_avg = (
            session.query(func.avg(TSACheckpoint.current_year_throughput))
            .filter(
                TSACheckpoint.date >= start_date,
                TSACheckpoint.date <= target_date,
                TSACheckpoint.day_of_week.in_([5, 6]),
            )
            .scalar()
        )

        if not weekday_avg or not weekend_avg or weekend_avg == 0:
            return None

        return float(weekday_avg) / float(weekend_avg)

    finally:
        session.close()


def calc_tsa_enplanement_nowcast(
    target_date: date,
) -> Optional[float]:
    """Estimate monthly airline enplanements from TSA data.

    Uses month-to-date TSA throughput as a proxy for
    official BTS enplanement data (released with 3-4 month lag).

    Args:
        target_date: Reference date

    Returns:
        Estimated monthly enplanements (in millions)
    """
    # Historical correlation coefficient between TSA and BTS enplanements
    CORRELATION_FACTOR = 0.97

    session = SessionLocal()
    try:
        # Get month-to-date throughput
        month_start = target_date.replace(day=1)

        total_throughput = (
            session.query(func.sum(TSACheckpoint.current_year_throughput))
            .filter(
                TSACheckpoint.date >= month_start,
                TSACheckpoint.date <= target_date,
            )
            .scalar()
        )

        if not total_throughput:
            return None

        # TSA screening ≈ 1:1 with domestic enplanements
        # Return in millions
        return float(total_throughput) * CORRELATION_FACTOR / 1_000_000

    finally:
        session.close()


def calc_tsa_holiday_vs_baseline(
    target_date: date,
    baseline_days: int = 30,
) -> Optional[float]:
    """Calculate holiday period throughput vs baseline.

    Measures the spike in travel during holiday periods
    compared to normal baseline.

    Args:
        target_date: Reference date
        baseline_days: Days of baseline to calculate

    Returns:
        Ratio of current throughput to baseline average
    """
    session = SessionLocal()
    try:
        # Get current day throughput
        current = (
            session.query(TSACheckpoint.current_year_throughput)
            .filter(TSACheckpoint.date == target_date)
            .scalar()
        )

        if not current:
            return None

        # Get baseline average (excluding holiday periods)
        baseline_start = target_date - timedelta(days=baseline_days + 7)
        baseline_end = target_date - timedelta(days=7)

        baseline_avg = (
            session.query(func.avg(TSACheckpoint.current_year_throughput))
            .filter(
                TSACheckpoint.date >= baseline_start,
                TSACheckpoint.date <= baseline_end,
                TSACheckpoint.is_holiday_period == False,
            )
            .scalar()
        )

        if not baseline_avg or baseline_avg == 0:
            return None

        return float(current) / float(baseline_avg)

    finally:
        session.close()


def calc_tsa_rolling_volatility(
    target_date: date,
    lookback_days: int = 14,
) -> Optional[float]:
    """Calculate rolling volatility of TSA throughput.

    Higher volatility may indicate uncertain travel patterns
    or external disruptions.

    Args:
        target_date: Reference date
        lookback_days: Analysis window

    Returns:
        Standard deviation of daily throughput
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days - 1)

        # Get standard deviation
        std_dev = (
            session.query(func.stddev(TSACheckpoint.current_year_throughput))
            .filter(
                TSACheckpoint.date >= start_date,
                TSACheckpoint.date <= target_date,
            )
            .scalar()
        )

        if std_dev is None:
            return None

        return float(std_dev)

    finally:
        session.close()


@FactorRegistry.register
class TSAThroughputMomentum(BaseFactor):
    """TSA Throughput Momentum Factor.

    7-day rolling average vs same period prior year.
    Positive values indicate increased travel demand.

    Target: DAL, UAL, AAL, LUV, JBLU, JETS
    """

    FACTOR_NAME = "tsa_throughput_momentum"
    FACTOR_DESCRIPTION = "TSA throughput 7-day MA vs prior year (%)"
    CATEGORY = "transportation"
    ENTITY_TYPE = "company"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute TSA throughput momentum."""
        # This is a sector-level signal, same for all airlines
        if entity_id not in AIRLINE_TICKERS + [SECTOR_ETF]:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_tsa_throughput_momentum(target_date, lookback_days)


@FactorRegistry.register
class TSAWeekdayWeekendRatio(BaseFactor):
    """TSA Weekday/Weekend Ratio Factor.

    Ratio of weekday to weekend travel.
    Higher = more business travel (bullish for DAL, UAL).
    Lower = more leisure travel (bullish for LUV, JBLU).

    Target: DAL, UAL (business-heavy), LUV, JBLU (leisure-heavy)
    """

    FACTOR_NAME = "tsa_weekday_weekend_ratio"
    FACTOR_DESCRIPTION = "Ratio of weekday to weekend TSA throughput"
    CATEGORY = "transportation"
    ENTITY_TYPE = "company"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 14

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 14,
    ) -> Optional[float]:
        """Compute weekday/weekend ratio."""
        if entity_id not in AIRLINE_TICKERS + [SECTOR_ETF]:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_tsa_weekday_weekend_ratio(target_date, lookback_days)


@FactorRegistry.register
class TSAEnplanementNowcast(BaseFactor):
    """TSA Enplanement Nowcast Factor.

    Estimates monthly airline enplanements using TSA data.
    BTS official data has 3-4 month lag; this is a real-time proxy.

    Target: JETS sector, airline stocks
    """

    FACTOR_NAME = "tsa_enplanement_nowcast"
    FACTOR_DESCRIPTION = "Estimated monthly enplanements from TSA (millions)"
    CATEGORY = "transportation"
    ENTITY_TYPE = "sector"
    FREQUENCY = "monthly"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute enplanement nowcast."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_tsa_enplanement_nowcast(target_date)


@FactorRegistry.register
class TSAHolidaySpike(BaseFactor):
    """TSA Holiday Spike Factor.

    Measures throughput during holiday periods vs baseline.
    Higher values indicate stronger holiday travel demand.

    Target: Airlines, hotels, OTAs
    """

    FACTOR_NAME = "tsa_holiday_spike"
    FACTOR_DESCRIPTION = "Holiday period throughput vs baseline ratio"
    CATEGORY = "transportation"
    ENTITY_TYPE = "company"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        baseline_days: int = 30,
    ) -> Optional[float]:
        """Compute holiday spike ratio."""
        if entity_id not in AIRLINE_TICKERS + TRAVEL_RELATED + [SECTOR_ETF]:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_tsa_holiday_vs_baseline(target_date, baseline_days)


@FactorRegistry.register
class TSAThroughputVolatility(BaseFactor):
    """TSA Throughput Volatility Factor.

    Rolling standard deviation of daily throughput.
    High volatility may indicate disruptions or uncertainty.

    Target: Airlines, travel sector
    """

    FACTOR_NAME = "tsa_throughput_volatility"
    FACTOR_DESCRIPTION = "Rolling 14-day TSA throughput volatility"
    CATEGORY = "transportation"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 14

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 14,
    ) -> Optional[float]:
        """Compute throughput volatility."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_tsa_rolling_volatility(target_date, lookback_days)
