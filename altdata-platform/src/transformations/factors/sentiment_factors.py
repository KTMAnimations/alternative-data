"""Reddit sentiment-derived factor computations."""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.sentiment import (
    SentimentScore,
    TickerMention,
    TickerSentimentDaily,
    SubredditSentimentDaily,
    RedditPost,
)
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


def calc_ticker_sentiment(
    ticker: str,
    target_date: date,
    lookback_days: int = 7,
) -> Optional[float]:
    """Calculate average sentiment for a ticker.

    Args:
        ticker: Stock ticker symbol
        target_date: Reference date
        lookback_days: Days to look back

    Returns:
        Average sentiment score (-1 to 1)
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        avg_sentiment = (
            session.query(func.avg(TickerMention.sentiment_score))
            .filter(
                TickerMention.ticker == ticker,
                func.date(TickerMention.created_utc) >= start_date,
                func.date(TickerMention.created_utc) <= target_date,
                TickerMention.sentiment_score.isnot(None),
            )
            .scalar()
        )

        return float(avg_sentiment) if avg_sentiment is not None else None
    finally:
        session.close()


def calc_ticker_mention_velocity(
    ticker: str,
    target_date: date,
    short_window: int = 1,
    long_window: int = 7,
) -> Optional[float]:
    """Calculate mention velocity (short vs long term).

    Velocity > 1 means mentions increasing, < 1 means decreasing.

    Args:
        ticker: Stock ticker symbol
        target_date: Reference date
        short_window: Short-term window in days
        long_window: Long-term window in days

    Returns:
        Velocity ratio
    """
    session = SessionLocal()
    try:
        short_start = target_date - timedelta(days=short_window)
        long_start = target_date - timedelta(days=long_window)

        short_count = (
            session.query(func.count(TickerMention.id))
            .filter(
                TickerMention.ticker == ticker,
                func.date(TickerMention.created_utc) >= short_start,
                func.date(TickerMention.created_utc) <= target_date,
            )
            .scalar()
        ) or 0

        long_count = (
            session.query(func.count(TickerMention.id))
            .filter(
                TickerMention.ticker == ticker,
                func.date(TickerMention.created_utc) >= long_start,
                func.date(TickerMention.created_utc) <= target_date,
            )
            .scalar()
        ) or 0

        if long_count == 0:
            return None

        # Normalize by window size
        short_rate = short_count / short_window
        long_rate = long_count / long_window

        if long_rate == 0:
            return None

        return short_rate / long_rate
    finally:
        session.close()


def calc_sentiment_momentum(
    ticker: str,
    target_date: date,
    short_window: int = 3,
    long_window: int = 14,
) -> Optional[float]:
    """Calculate sentiment momentum (change in sentiment).

    Args:
        ticker: Stock ticker symbol
        target_date: Reference date
        short_window: Short-term window in days
        long_window: Long-term window in days

    Returns:
        Sentiment momentum (short avg - long avg)
    """
    session = SessionLocal()
    try:
        short_start = target_date - timedelta(days=short_window)
        long_start = target_date - timedelta(days=long_window)

        short_avg = (
            session.query(func.avg(TickerMention.sentiment_score))
            .filter(
                TickerMention.ticker == ticker,
                func.date(TickerMention.created_utc) >= short_start,
                func.date(TickerMention.created_utc) <= target_date,
                TickerMention.sentiment_score.isnot(None),
            )
            .scalar()
        )

        long_avg = (
            session.query(func.avg(TickerMention.sentiment_score))
            .filter(
                TickerMention.ticker == ticker,
                func.date(TickerMention.created_utc) >= long_start,
                func.date(TickerMention.created_utc) <= target_date,
                TickerMention.sentiment_score.isnot(None),
            )
            .scalar()
        )

        if short_avg is None or long_avg is None:
            return None

        return float(short_avg) - float(long_avg)
    finally:
        session.close()


def calc_wsb_sentiment(
    target_date: date,
    lookback_days: int = 1,
) -> Optional[float]:
    """Calculate WallStreetBets subreddit sentiment.

    Args:
        target_date: Reference date
        lookback_days: Days to look back

    Returns:
        Average sentiment score
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        avg_sentiment = (
            session.query(func.avg(SentimentScore.sentiment_score))
            .filter(
                SentimentScore.subreddit == "wallstreetbets",
                func.date(SentimentScore.analyzed_at) >= start_date,
                func.date(SentimentScore.analyzed_at) <= target_date,
                SentimentScore.sentiment_score.isnot(None),
            )
            .scalar()
        )

        return float(avg_sentiment) if avg_sentiment is not None else None
    finally:
        session.close()


def calc_retail_attention_index(
    target_date: date,
    lookback_days: int = 1,
    subreddits: Optional[List[str]] = None,
) -> Optional[float]:
    """Calculate retail investor attention index.

    Based on post volume and engagement across subreddits.

    Args:
        target_date: Reference date
        lookback_days: Days to look back
        subreddits: Subreddits to include (default: all tracked)

    Returns:
        Attention index score
    """
    default_subs = [
        "wallstreetbets", "stocks", "investing", "options",
        "stockmarket", "pennystocks",
    ]
    subs = subreddits or default_subs

    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        # Count posts
        post_count = (
            session.query(func.count(RedditPost.id))
            .filter(
                RedditPost.subreddit.in_(subs),
                func.date(RedditPost.created_utc) >= start_date,
                func.date(RedditPost.created_utc) <= target_date,
            )
            .scalar()
        ) or 0

        # Sum engagement (score + comments)
        engagement = (
            session.query(
                func.sum(RedditPost.score),
                func.sum(RedditPost.num_comments),
            )
            .filter(
                RedditPost.subreddit.in_(subs),
                func.date(RedditPost.created_utc) >= start_date,
                func.date(RedditPost.created_utc) <= target_date,
            )
            .first()
        )

        total_score = engagement[0] or 0
        total_comments = engagement[1] or 0

        # Composite index: log(posts) * log(engagement + 1)
        if post_count == 0:
            return None

        import math
        attention = math.log(post_count + 1) * math.log(total_score + total_comments + 1)
        return attention
    finally:
        session.close()


def calc_sentiment_dispersion(
    ticker: str,
    target_date: date,
    lookback_days: int = 7,
) -> Optional[float]:
    """Calculate sentiment dispersion (disagreement).

    Higher dispersion means more disagreement about the ticker.

    Args:
        ticker: Stock ticker symbol
        target_date: Reference date
        lookback_days: Days to look back

    Returns:
        Standard deviation of sentiment scores
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        sentiments = (
            session.query(TickerMention.sentiment_score)
            .filter(
                TickerMention.ticker == ticker,
                func.date(TickerMention.created_utc) >= start_date,
                func.date(TickerMention.created_utc) <= target_date,
                TickerMention.sentiment_score.isnot(None),
            )
            .all()
        )

        if len(sentiments) < 3:
            return None

        values = [s[0] for s in sentiments]
        return float(np.std(values))
    finally:
        session.close()


@FactorRegistry.register
class TickerSentiment(BaseFactor):
    """Ticker Sentiment Factor.

    Average sentiment score for a stock ticker from Reddit.
    """

    FACTOR_NAME = "ticker_sentiment"
    FACTOR_DESCRIPTION = "Average Reddit sentiment for ticker (-1 to 1)"
    CATEGORY = "sentiment"
    ENTITY_TYPE = "ticker"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,  # Ticker
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute ticker sentiment."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_ticker_sentiment(entity_id, target_date, lookback_days)


@FactorRegistry.register
class MentionVelocity(BaseFactor):
    """Mention Velocity Factor.

    Rate of change in ticker mentions.
    > 1 = increasing mentions, < 1 = decreasing.
    """

    FACTOR_NAME = "mention_velocity"
    FACTOR_DESCRIPTION = "Ticker mention velocity (1d vs 7d rate)"
    CATEGORY = "sentiment"
    ENTITY_TYPE = "ticker"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute mention velocity."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_ticker_mention_velocity(entity_id, target_date)


@FactorRegistry.register
class SentimentMomentum(BaseFactor):
    """Sentiment Momentum Factor.

    Change in sentiment over time.
    Positive = improving sentiment, Negative = worsening.
    """

    FACTOR_NAME = "sentiment_momentum"
    FACTOR_DESCRIPTION = "Sentiment momentum (3d vs 14d)"
    CATEGORY = "sentiment"
    ENTITY_TYPE = "ticker"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 14

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute sentiment momentum."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_sentiment_momentum(entity_id, target_date)


@FactorRegistry.register
class WSBSentiment(BaseFactor):
    """WallStreetBets Sentiment Factor.

    Overall sentiment from r/wallstreetbets.
    """

    FACTOR_NAME = "wsb_sentiment"
    FACTOR_DESCRIPTION = "WallStreetBets subreddit sentiment"
    CATEGORY = "sentiment"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,  # Ignored
        as_of_date: datetime,
        lookback_days: int = 1,
    ) -> Optional[float]:
        """Compute WSB sentiment."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_wsb_sentiment(target_date, lookback_days)


@FactorRegistry.register
class RetailAttentionIndex(BaseFactor):
    """Retail Attention Index Factor.

    Composite measure of retail investor attention.
    Based on post volume and engagement.
    """

    FACTOR_NAME = "retail_attention_index"
    FACTOR_DESCRIPTION = "Retail investor attention from Reddit activity"
    CATEGORY = "sentiment"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,  # Ignored
        as_of_date: datetime,
        lookback_days: int = 1,
    ) -> Optional[float]:
        """Compute retail attention index."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_retail_attention_index(target_date, lookback_days)


@FactorRegistry.register
class SentimentDispersion(BaseFactor):
    """Sentiment Dispersion Factor.

    Measures disagreement in sentiment for a ticker.
    Higher = more disagreement/uncertainty.
    """

    FACTOR_NAME = "sentiment_dispersion"
    FACTOR_DESCRIPTION = "Sentiment disagreement (std dev)"
    CATEGORY = "sentiment"
    ENTITY_TYPE = "ticker"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute sentiment dispersion."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_sentiment_dispersion(entity_id, target_date, lookback_days)
