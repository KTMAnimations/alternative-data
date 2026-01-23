"""Google Trends-derived factor computations."""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.trends import TrendInterest, TrendKeyword, TrendBreakout
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


def calc_search_momentum(
    keyword: str,
    target_date: date,
    short_window: int = 7,
    long_window: int = 28,
    geo: str = "US",
) -> Optional[float]:
    """Calculate search interest momentum.

    Momentum = (short-term avg - long-term avg) / long-term avg

    Args:
        keyword: Search term
        target_date: Reference date
        short_window: Short-term window in days
        long_window: Long-term window in days
        geo: Geographic region

    Returns:
        Momentum score (-1 to +inf)
    """
    session = SessionLocal()
    try:
        short_start = target_date - timedelta(days=short_window)
        long_start = target_date - timedelta(days=long_window)

        short_avg = (
            session.query(func.avg(TrendInterest.interest))
            .filter(
                TrendInterest.keyword == keyword,
                TrendInterest.geo == geo,
                TrendInterest.date >= short_start,
                TrendInterest.date <= target_date,
            )
            .scalar()
        )

        long_avg = (
            session.query(func.avg(TrendInterest.interest))
            .filter(
                TrendInterest.keyword == keyword,
                TrendInterest.geo == geo,
                TrendInterest.date >= long_start,
                TrendInterest.date <= target_date,
            )
            .scalar()
        )

        if short_avg is None or long_avg is None or long_avg == 0:
            return None

        return (float(short_avg) - float(long_avg)) / float(long_avg)
    finally:
        session.close()


def calc_search_volatility(
    keyword: str,
    target_date: date,
    lookback_days: int = 30,
    geo: str = "US",
) -> Optional[float]:
    """Calculate search interest volatility.

    Higher volatility may indicate market uncertainty or events.

    Args:
        keyword: Search term
        target_date: Reference date
        lookback_days: Analysis window
        geo: Geographic region

    Returns:
        Standard deviation of interest
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        interests = (
            session.query(TrendInterest.interest)
            .filter(
                TrendInterest.keyword == keyword,
                TrendInterest.geo == geo,
                TrendInterest.date >= start_date,
                TrendInterest.date <= target_date,
                TrendInterest.interest.isnot(None),
            )
            .all()
        )

        if not interests or len(interests) < 5:
            return None

        values = [i[0] for i in interests]
        return float(np.std(values))
    finally:
        session.close()


def calc_relative_search_strength(
    keyword: str,
    target_date: date,
    comparison_keywords: List[str],
    lookback_days: int = 7,
    geo: str = "US",
) -> Optional[float]:
    """Calculate relative search strength vs comparison keywords.

    RSI-style indicator for relative interest.

    Args:
        keyword: Primary keyword
        target_date: Reference date
        comparison_keywords: Keywords to compare against
        lookback_days: Analysis window
        geo: Geographic region

    Returns:
        Relative strength score (0-100)
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        # Get average interest for primary keyword
        primary_avg = (
            session.query(func.avg(TrendInterest.interest))
            .filter(
                TrendInterest.keyword == keyword,
                TrendInterest.geo == geo,
                TrendInterest.date >= start_date,
                TrendInterest.date <= target_date,
            )
            .scalar()
        )

        if primary_avg is None:
            return None

        # Get average interest for comparison keywords
        comparison_avgs = []
        for comp_kw in comparison_keywords:
            comp_avg = (
                session.query(func.avg(TrendInterest.interest))
                .filter(
                    TrendInterest.keyword == comp_kw,
                    TrendInterest.geo == geo,
                    TrendInterest.date >= start_date,
                    TrendInterest.date <= target_date,
                )
                .scalar()
            )
            if comp_avg is not None:
                comparison_avgs.append(float(comp_avg))

        if not comparison_avgs:
            return None

        total_avg = sum(comparison_avgs) + float(primary_avg)
        if total_avg == 0:
            return None

        # RSI-style: primary / (primary + avg_comparison) * 100
        avg_comparison = sum(comparison_avgs) / len(comparison_avgs)
        return (float(primary_avg) / (float(primary_avg) + avg_comparison)) * 100
    finally:
        session.close()


def calc_search_yoy_change(
    keyword: str,
    target_date: date,
    lookback_days: int = 7,
    geo: str = "US",
) -> Optional[float]:
    """Calculate year-over-year change in search interest.

    Args:
        keyword: Search term
        target_date: Reference date
        lookback_days: Window for comparison
        geo: Geographic region

    Returns:
        YoY percentage change
    """
    session = SessionLocal()
    try:
        current_start = target_date - timedelta(days=lookback_days)
        prior_end = target_date - timedelta(days=365)
        prior_start = prior_end - timedelta(days=lookback_days)

        current_avg = (
            session.query(func.avg(TrendInterest.interest))
            .filter(
                TrendInterest.keyword == keyword,
                TrendInterest.geo == geo,
                TrendInterest.date >= current_start,
                TrendInterest.date <= target_date,
            )
            .scalar()
        )

        prior_avg = (
            session.query(func.avg(TrendInterest.interest))
            .filter(
                TrendInterest.keyword == keyword,
                TrendInterest.geo == geo,
                TrendInterest.date >= prior_start,
                TrendInterest.date <= prior_end,
            )
            .scalar()
        )

        if current_avg is None or prior_avg is None or prior_avg == 0:
            return None

        return ((float(current_avg) - float(prior_avg)) / float(prior_avg)) * 100
    finally:
        session.close()


def calc_category_composite_interest(
    category: str,
    target_date: date,
    lookback_days: int = 7,
    geo: str = "US",
) -> Optional[float]:
    """Calculate composite interest score for a category.

    Args:
        category: Keyword category (retail, tech, energy, etc.)
        target_date: Reference date
        lookback_days: Analysis window
        geo: Geographic region

    Returns:
        Average interest across category keywords
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        # Get keywords in category
        keywords = (
            session.query(TrendKeyword.keyword)
            .filter(TrendKeyword.category == category)
            .all()
        )

        if not keywords:
            return None

        keyword_list = [k[0] for k in keywords]

        avg_interest = (
            session.query(func.avg(TrendInterest.interest))
            .filter(
                TrendInterest.keyword.in_(keyword_list),
                TrendInterest.geo == geo,
                TrendInterest.date >= start_date,
                TrendInterest.date <= target_date,
            )
            .scalar()
        )

        return float(avg_interest) if avg_interest else None
    finally:
        session.close()


def count_recent_breakouts(
    category: Optional[str] = None,
    lookback_days: int = 7,
    geo: str = "US",
) -> int:
    """Count recent breakout events.

    Args:
        category: Optional category filter
        lookback_days: Days to look back
        geo: Geographic region

    Returns:
        Number of breakouts detected
    """
    session = SessionLocal()
    try:
        cutoff_date = date.today() - timedelta(days=lookback_days)

        query = session.query(func.count(TrendBreakout.id)).filter(
            TrendBreakout.geo == geo,
            TrendBreakout.breakout_date >= cutoff_date,
        )

        if category:
            # Join with keywords to filter by category
            category_keywords = (
                session.query(TrendKeyword.keyword)
                .filter(TrendKeyword.category == category)
                .all()
            )
            keyword_list = [k[0] for k in category_keywords]
            query = query.filter(TrendBreakout.keyword.in_(keyword_list))

        return query.scalar() or 0
    finally:
        session.close()


@FactorRegistry.register
class SearchMomentum(BaseFactor):
    """Search Momentum Factor.

    Measures short-term vs long-term search interest momentum.
    Positive = increasing interest, Negative = declining.
    """

    FACTOR_NAME = "search_momentum"
    FACTOR_DESCRIPTION = "Search interest momentum (7d vs 28d)"
    CATEGORY = "trends"
    ENTITY_TYPE = "keyword"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 28

    def compute(
        self,
        entity_id: str,  # Keyword
        as_of_date: datetime,
        short_window: int = 7,
        long_window: int = 28,
    ) -> Optional[float]:
        """Compute search momentum."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_search_momentum(entity_id, target_date, short_window, long_window)


@FactorRegistry.register
class SearchVolatility(BaseFactor):
    """Search Volatility Factor.

    Measures variability in search interest.
    High volatility may indicate uncertainty or events.
    """

    FACTOR_NAME = "search_volatility"
    FACTOR_DESCRIPTION = "Search interest volatility (std dev)"
    CATEGORY = "trends"
    ENTITY_TYPE = "keyword"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 30,
    ) -> Optional[float]:
        """Compute search volatility."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_search_volatility(entity_id, target_date, lookback_days)


@FactorRegistry.register
class SearchYoYChange(BaseFactor):
    """Search Year-over-Year Change Factor.

    Measures change in interest vs same period last year.
    """

    FACTOR_NAME = "search_yoy_change"
    FACTOR_DESCRIPTION = "Search interest YoY percentage change"
    CATEGORY = "trends"
    ENTITY_TYPE = "keyword"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute search YoY change."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_search_yoy_change(entity_id, target_date, lookback_days)


@FactorRegistry.register
class CategoryInterest(BaseFactor):
    """Category Composite Interest Factor.

    Average interest across all keywords in a category.
    """

    FACTOR_NAME = "category_interest"
    FACTOR_DESCRIPTION = "Average search interest for category"
    CATEGORY = "trends"
    ENTITY_TYPE = "category"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,  # Category name
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute category composite interest."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_category_composite_interest(entity_id, target_date, lookback_days)


@FactorRegistry.register
class RetailSentimentIndex(BaseFactor):
    """Retail Sentiment Index Factor.

    Composite of retail-related search terms indicating consumer sentiment.
    """

    FACTOR_NAME = "retail_sentiment_index"
    FACTOR_DESCRIPTION = "Retail consumer sentiment from search trends"
    CATEGORY = "trends"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    RETAIL_POSITIVE = ["black friday deals", "cyber monday", "holiday shopping", "buy stocks"]
    RETAIL_NEGATIVE = ["recession", "unemployment benefits", "stock market crash"]

    def compute(
        self,
        entity_id: str,  # Ignored, uses predefined keywords
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute retail sentiment index.

        Returns score: positive = bullish sentiment, negative = bearish.
        """
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        start_date = target_date - timedelta(days=lookback_days)

        session = SessionLocal()
        try:
            positive_avg = (
                session.query(func.avg(TrendInterest.interest))
                .filter(
                    TrendInterest.keyword.in_(self.RETAIL_POSITIVE),
                    TrendInterest.date >= start_date,
                    TrendInterest.date <= target_date,
                )
                .scalar()
            )

            negative_avg = (
                session.query(func.avg(TrendInterest.interest))
                .filter(
                    TrendInterest.keyword.in_(self.RETAIL_NEGATIVE),
                    TrendInterest.date >= start_date,
                    TrendInterest.date <= target_date,
                )
                .scalar()
            )

            if positive_avg is None and negative_avg is None:
                return None

            pos = float(positive_avg) if positive_avg else 0
            neg = float(negative_avg) if negative_avg else 0

            # Sentiment = (positive - negative) normalized
            if pos + neg == 0:
                return 0

            return (pos - neg) / (pos + neg) * 100
        finally:
            session.close()
