"""Box office-derived factor computations.

Factors derived from movie box office data for entertainment
sector analysis.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict

from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.box_office import BoxOfficeDaily, STUDIO_TICKER_MAP
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


# Studio tickers
STUDIO_TICKERS = list(set(t for t in STUDIO_TICKER_MAP.values() if t))
THEATER_TICKERS = ["AMC", "CNK", "IMAX"]


def calc_studio_market_share(
    ticker: str,
    target_date: date,
    lookback_days: int = 30,
) -> Optional[float]:
    """Calculate studio's market share of box office.

    Args:
        ticker: Studio ticker
        target_date: Reference date
        lookback_days: Analysis window

    Returns:
        Market share percentage
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        # Studio gross
        studio_gross = (
            session.query(func.sum(BoxOfficeDaily.daily_gross))
            .filter(
                BoxOfficeDaily.date >= start_date,
                BoxOfficeDaily.date <= target_date,
                BoxOfficeDaily.distributor_ticker == ticker,
            )
            .scalar()
        ) or 0

        # Total market gross
        total_gross = (
            session.query(func.sum(BoxOfficeDaily.daily_gross))
            .filter(
                BoxOfficeDaily.date >= start_date,
                BoxOfficeDaily.date <= target_date,
            )
            .scalar()
        ) or 0

        if total_gross == 0:
            return None

        return (float(studio_gross) / float(total_gross)) * 100

    finally:
        session.close()


def calc_total_box_office(
    target_date: date,
    lookback_days: int = 7,
) -> Optional[float]:
    """Calculate total box office for period.

    Args:
        target_date: Reference date
        lookback_days: Analysis window

    Returns:
        Total box office in millions
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        total = (
            session.query(func.sum(BoxOfficeDaily.daily_gross))
            .filter(
                BoxOfficeDaily.date >= start_date,
                BoxOfficeDaily.date <= target_date,
            )
            .scalar()
        )

        if total:
            return float(total) / 1_000_000  # Return in millions
        return 0.0

    finally:
        session.close()


def calc_box_office_momentum(
    target_date: date,
    lookback_days: int = 7,
) -> Optional[float]:
    """Calculate week-over-week box office change.

    Args:
        target_date: Reference date
        lookback_days: Window size

    Returns:
        Percentage change vs prior period
    """
    session = SessionLocal()
    try:
        # Current week
        current_start = target_date - timedelta(days=lookback_days)
        current_total = (
            session.query(func.sum(BoxOfficeDaily.daily_gross))
            .filter(
                BoxOfficeDaily.date >= current_start,
                BoxOfficeDaily.date <= target_date,
            )
            .scalar()
        ) or 0

        # Prior week
        prior_end = current_start - timedelta(days=1)
        prior_start = prior_end - timedelta(days=lookback_days)
        prior_total = (
            session.query(func.sum(BoxOfficeDaily.daily_gross))
            .filter(
                BoxOfficeDaily.date >= prior_start,
                BoxOfficeDaily.date <= prior_end,
            )
            .scalar()
        ) or 0

        if prior_total == 0:
            return None

        return ((float(current_total) - float(prior_total)) / float(prior_total)) * 100

    finally:
        session.close()


def calc_opening_weekend_performance(
    target_date: date,
    lookback_days: int = 3,
) -> Optional[Dict]:
    """Get top opening weekend performances.

    Args:
        target_date: Reference date
        lookback_days: Days to look back

    Returns:
        Dict with top opener info
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        # Find new releases (days_in_release <= 3)
        new_releases = (
            session.query(
                BoxOfficeDaily.movie_title,
                BoxOfficeDaily.distributor_ticker,
                func.sum(BoxOfficeDaily.daily_gross).label("total_gross"),
            )
            .filter(
                BoxOfficeDaily.date >= start_date,
                BoxOfficeDaily.date <= target_date,
                BoxOfficeDaily.is_new_release == "Yes",
            )
            .group_by(BoxOfficeDaily.movie_title, BoxOfficeDaily.distributor_ticker)
            .order_by(func.sum(BoxOfficeDaily.daily_gross).desc())
            .first()
        )

        if new_releases:
            return {
                "movie": new_releases[0],
                "ticker": new_releases[1],
                "gross": float(new_releases[2]) / 1_000_000 if new_releases[2] else 0,
            }
        return None

    finally:
        session.close()


def calc_per_theater_average(
    target_date: date,
) -> Optional[float]:
    """Calculate industry-wide per-theater average.

    Args:
        target_date: Reference date

    Returns:
        Average gross per theater
    """
    session = SessionLocal()
    try:
        avg_pta = (
            session.query(func.avg(BoxOfficeDaily.per_theater_avg))
            .filter(
                BoxOfficeDaily.date == target_date,
                BoxOfficeDaily.per_theater_avg.isnot(None),
            )
            .scalar()
        )

        if avg_pta:
            return float(avg_pta)
        return None

    finally:
        session.close()


@FactorRegistry.register
class StudioMarketShare(BaseFactor):
    """Studio Market Share Factor.

    Studio's share of total box office revenue.
    Indicates competitive position.

    Target: DIS, WBD, PARA, CMCSA, SONY
    """

    FACTOR_NAME = "studio_market_share"
    FACTOR_DESCRIPTION = "Studio box office market share (%)"
    CATEGORY = "entertainment"
    ENTITY_TYPE = "company"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 30,
    ) -> Optional[float]:
        """Compute studio market share."""
        if entity_id not in STUDIO_TICKERS:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_studio_market_share(entity_id, target_date, lookback_days)


@FactorRegistry.register
class BoxOfficeMomentum(BaseFactor):
    """Box Office Momentum Factor.

    Week-over-week change in total box office.
    Indicates theatrical demand trends.

    Target: Studios, theater chains
    """

    FACTOR_NAME = "box_office_momentum"
    FACTOR_DESCRIPTION = "Weekly box office change (%)"
    CATEGORY = "entertainment"
    ENTITY_TYPE = "sector"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute box office momentum."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_box_office_momentum(target_date)


@FactorRegistry.register
class TotalBoxOffice(BaseFactor):
    """Total Box Office Factor.

    Weekly theatrical revenue in millions.
    Overall market health indicator.

    Target: AMC, CNK, IMAX
    """

    FACTOR_NAME = "total_box_office"
    FACTOR_DESCRIPTION = "Weekly box office total ($ millions)"
    CATEGORY = "entertainment"
    ENTITY_TYPE = "company"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute total box office."""
        if entity_id not in THEATER_TICKERS + STUDIO_TICKERS:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_total_box_office(target_date)


@FactorRegistry.register
class PerTheaterAverage(BaseFactor):
    """Per Theater Average Factor.

    Industry average gross per theater.
    Indicates demand intensity.

    Target: Theater chains
    """

    FACTOR_NAME = "per_theater_average"
    FACTOR_DESCRIPTION = "Average gross per theater ($)"
    CATEGORY = "entertainment"
    ENTITY_TYPE = "company"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute per-theater average."""
        if entity_id not in THEATER_TICKERS:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_per_theater_average(target_date)
