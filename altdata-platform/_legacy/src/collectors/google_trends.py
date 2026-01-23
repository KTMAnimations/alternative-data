"""Google Trends collector for search interest data."""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    from pytrends.request import TrendReq
    HAS_PYTRENDS = True
except ImportError:
    TrendReq = None
    HAS_PYTRENDS = False

from src.collectors.base import BaseCollector, CollectorError
from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.trends import (
    TrendKeyword,
    TrendInterest,
    TrendRelatedQuery,
    TrendComparison,
    TrendBreakout,
)

logger = logging.getLogger(__name__)


class GoogleTrendsCollector(BaseCollector[Dict, Dict]):
    """Collector for Google Trends data.

    Tracks search interest as a proxy for consumer attention and demand.
    """

    SOURCE_NAME = "google_trends"
    DEFAULT_RATE_LIMIT = 0.1  # Very conservative: ~6 requests/minute

    # Default keywords for tracking consumer/market signals
    DEFAULT_KEYWORDS = {
        "retail": [
            "buy stocks", "stock market crash", "recession",
            "black friday deals", "cyber monday", "holiday shopping",
            "amazon prime day", "walmart deals",
        ],
        "consumer": [
            "unemployment benefits", "gas prices", "grocery prices",
            "credit card debt", "mortgage rates", "car prices",
        ],
        "tech": [
            "iphone", "android", "chatgpt", "artificial intelligence",
            "nvidia stock", "tesla stock", "apple stock",
        ],
        "energy": [
            "oil prices", "gas prices", "electric car", "solar panels",
            "energy bill", "heating costs",
        ],
        "crypto": [
            "bitcoin", "ethereum", "crypto crash", "buy crypto",
        ],
    }

    # Keyword to ticker mapping for factor computation
    KEYWORD_TICKERS = {
        "iphone": ["AAPL"],
        "apple stock": ["AAPL"],
        "nvidia stock": ["NVDA"],
        "tesla stock": ["TSLA"],
        "amazon prime day": ["AMZN"],
        "walmart deals": ["WMT"],
        "bitcoin": ["BTC-USD", "COIN"],
        "ethereum": ["ETH-USD"],
    }

    def __init__(
        self,
        rate_limit: Optional[float] = None,
        geo: str = "US",
        hl: str = "en-US",
    ):
        """Initialize the Google Trends collector.

        Args:
            rate_limit: Requests per second
            geo: Geographic region (default US)
            hl: Language (default en-US)
        """
        super().__init__(rate_limit=rate_limit or self.DEFAULT_RATE_LIMIT)
        self.geo = geo
        self.hl = hl
        self._pytrends = None

    @property
    def pytrends(self):
        """Get or create pytrends instance."""
        if not HAS_PYTRENDS:
            raise CollectorError("pytrends package not installed. Install with: pip install pytrends")
        if self._pytrends is None:
            self._pytrends = TrendReq(hl=self.hl, tz=360)
        return self._pytrends

    async def fetch(self) -> List[Dict]:
        """Fetch trends for all tracked keywords.

        Returns:
            List of trend data dicts
        """
        results = []
        for category, keywords in self.DEFAULT_KEYWORDS.items():
            for keyword in keywords:
                try:
                    await self.rate_limiter.wait()
                    data = self.fetch_interest_over_time(keyword)
                    if data:
                        data["_category"] = category
                        results.append(data)
                except Exception as e:
                    logger.warning(f"Failed to fetch trends for '{keyword}': {e}")
        return results

    def fetch_interest_over_time(
        self,
        keyword: str,
        timeframe: str = "today 3-m",
    ) -> Optional[Dict]:
        """Fetch interest over time for a keyword.

        Args:
            keyword: Search term to track
            timeframe: Time period (e.g., 'today 3-m', 'today 12-m')

        Returns:
            Interest data dict or None
        """
        try:
            self.pytrends.build_payload(
                kw_list=[keyword],
                cat=0,
                timeframe=timeframe,
                geo=self.geo,
            )

            df = self.pytrends.interest_over_time()

            if df.empty:
                return None

            return {
                "keyword": keyword,
                "geo": self.geo,
                "timeframe": timeframe,
                "data": [
                    {
                        "date": idx.date(),
                        "interest": int(row[keyword]),
                        "is_partial": bool(row.get("isPartial", False)),
                    }
                    for idx, row in df.iterrows()
                ],
            }

        except Exception as e:
            logger.error(f"Error fetching interest for '{keyword}': {e}")
            return None

    def fetch_related_queries(self, keyword: str) -> Optional[Dict]:
        """Fetch related queries for a keyword.

        Args:
            keyword: Search term

        Returns:
            Related queries data or None
        """
        try:
            self.pytrends.build_payload(
                kw_list=[keyword],
                cat=0,
                timeframe="today 3-m",
                geo=self.geo,
            )

            related = self.pytrends.related_queries()

            if not related or keyword not in related:
                return None

            result = {
                "keyword": keyword,
                "geo": self.geo,
                "top": [],
                "rising": [],
            }

            top_df = related[keyword].get("top")
            if top_df is not None and not top_df.empty:
                result["top"] = top_df.to_dict("records")

            rising_df = related[keyword].get("rising")
            if rising_df is not None and not rising_df.empty:
                result["rising"] = rising_df.to_dict("records")

            return result

        except Exception as e:
            logger.error(f"Error fetching related queries for '{keyword}': {e}")
            return None

    def fetch_comparison(
        self,
        keywords: List[str],
        timeframe: str = "today 3-m",
    ) -> Optional[Dict]:
        """Compare interest between multiple keywords.

        Args:
            keywords: List of keywords to compare (max 5)
            timeframe: Time period

        Returns:
            Comparison data or None
        """
        if len(keywords) > 5:
            keywords = keywords[:5]

        try:
            self.pytrends.build_payload(
                kw_list=keywords,
                cat=0,
                timeframe=timeframe,
                geo=self.geo,
            )

            df = self.pytrends.interest_over_time()

            if df.empty:
                return None

            return {
                "keywords": keywords,
                "keyword_group": ",".join(sorted(keywords)),
                "geo": self.geo,
                "timeframe": timeframe,
                "data": [
                    {
                        "date": idx.date(),
                        "values": {kw: int(row[kw]) for kw in keywords},
                        "is_partial": bool(row.get("isPartial", False)),
                    }
                    for idx, row in df.iterrows()
                ],
            }

        except Exception as e:
            logger.error(f"Error fetching comparison for {keywords}: {e}")
            return None

    def parse(self, raw_data: List[Dict]) -> List[Dict]:
        """Parse trend data.

        Args:
            raw_data: List of raw trend dicts

        Returns:
            List of parsed trend dicts
        """
        return raw_data  # Already in usable format

    def detect_breakout(
        self,
        keyword: str,
        threshold: float = 2.0,
        lookback_days: int = 30,
    ) -> Optional[Dict]:
        """Detect breakout events in search interest.

        A breakout is when interest exceeds threshold * average.

        Args:
            keyword: Keyword to analyze
            threshold: Multiplier for breakout detection
            lookback_days: Days to calculate baseline

        Returns:
            Breakout data if detected, None otherwise
        """
        data = self.fetch_interest_over_time(keyword, "today 3-m")
        if not data or not data.get("data"):
            return None

        points = data["data"]
        if len(points) < lookback_days + 7:
            return None

        # Calculate baseline from lookback period
        baseline_points = points[-(lookback_days + 7):-7]
        if not baseline_points:
            return None

        baseline_avg = sum(p["interest"] for p in baseline_points) / len(baseline_points)

        if baseline_avg == 0:
            return None

        # Check recent period for breakout
        recent_points = points[-7:]
        for point in recent_points:
            if point["interest"] > baseline_avg * threshold:
                return {
                    "keyword": keyword,
                    "geo": self.geo,
                    "breakout_date": point["date"],
                    "interest_before": baseline_avg,
                    "interest_peak": point["interest"],
                    "percent_change": ((point["interest"] - baseline_avg) / baseline_avg) * 100,
                }

        return None

    async def store_interest_data(self, data: List[Dict]) -> int:
        """Store interest data in database.

        Args:
            data: List of interest data dicts

        Returns:
            Number of records stored
        """
        session = SessionLocal()
        count = 0

        try:
            for item in data:
                keyword = item.get("keyword")
                geo = item.get("geo", "US")
                category = item.get("_category")

                # Ensure keyword exists
                kw_record = (
                    session.query(TrendKeyword)
                    .filter_by(keyword=keyword)
                    .first()
                )
                if not kw_record:
                    kw_record = TrendKeyword(
                        keyword=keyword,
                        category=category,
                        related_tickers=self.KEYWORD_TICKERS.get(keyword.lower()),
                    )
                    session.add(kw_record)
                kw_record.last_fetched = datetime.utcnow()

                # Store interest data points
                for point in item.get("data", []):
                    record = TrendInterest(
                        keyword=keyword,
                        geo=geo,
                        date=point["date"],
                        interest=point["interest"],
                        is_partial=point.get("is_partial", False),
                        fetched_at=datetime.utcnow(),
                    )
                    session.add(record)
                    count += 1

            session.commit()
            logger.info(f"Stored {count} trend interest records")

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store trend data: {e}")
            raise
        finally:
            session.close()

        return count

    async def run_collection(self) -> int:
        """Run full collection cycle.

        Returns:
            Number of records stored
        """
        logger.info("Starting Google Trends collection")

        try:
            raw_data = await self.fetch()
            if raw_data:
                await self.store_raw(raw_data)

            parsed = self.parse(raw_data)
            count = await self.store_interest_data(parsed)

            logger.info(f"Google Trends collection complete: {count} records")
            return count

        finally:
            await self.close()
