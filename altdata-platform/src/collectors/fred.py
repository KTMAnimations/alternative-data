"""FRED (Federal Reserve Economic Data) collector."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from src.collectors.base import BaseCollector, CollectorError
from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.schemas import FREDSeries, RawDataCatalog

logger = logging.getLogger(__name__)


# Key economic series to track
FRED_SERIES = {
    # Treasury Yields
    "GS10": "10-Year Treasury Constant Maturity Rate",
    "GS2": "2-Year Treasury Constant Maturity Rate",
    "GS1": "1-Year Treasury Constant Maturity Rate",
    "GS3M": "3-Month Treasury Bill Secondary Market Rate",
    # Credit Spreads
    "BAA10Y": "Moody's Seasoned Baa Corporate Bond Minus 10-Year Treasury",
    "AAA10Y": "Moody's Seasoned Aaa Corporate Bond Minus 10-Year Treasury",
    # Money Supply
    "M2SL": "M2 Money Stock",
    # Labor Market
    "ICSA": "Initial Claims",
    "IC4WSA": "4-Week Moving Average of Initial Claims",
    "UNRATE": "Unemployment Rate",
    # Financial Conditions
    "NFCI": "Chicago Fed National Financial Conditions Index",
    # Inflation
    "T10YIE": "10-Year Breakeven Inflation Rate",
    "CPIAUCSL": "Consumer Price Index for All Urban Consumers",
}


class FREDCollector(BaseCollector[Dict, List[Dict]]):
    """Collector for Federal Reserve Economic Data (FRED).

    Fetches economic time series data from the FRED API.
    """

    SOURCE_NAME = "fred"
    BASE_URL = "https://api.stlouisfed.org/fred"
    DEFAULT_RATE_LIMIT = 2.0  # Conservative rate limit

    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit: Optional[float] = None,
    ):
        """Initialize the FRED collector.

        Args:
            api_key: FRED API key
            rate_limit: Requests per second
        """
        super().__init__(rate_limit=rate_limit or settings.fred_rate_limit)
        self.api_key = api_key or settings.fred_api_key
        if not self.api_key:
            logger.warning("FRED API key not configured - collector will fail")

    async def fetch(self) -> Dict:
        """Fetch all configured FRED series.

        Returns:
            Dict mapping series IDs to their observations
        """
        results = {}

        for series_id in FRED_SERIES:
            try:
                data = await self.fetch_series(series_id)
                results[series_id] = data
            except Exception as e:
                logger.warning(f"Failed to fetch {series_id}: {e}")
                continue

        return results

    async def fetch_series(
        self,
        series_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Fetch a specific FRED series.

        Args:
            series_id: FRED series identifier
            start_date: Start date for observations
            end_date: End date for observations
            limit: Maximum observations to return

        Returns:
            FRED API response with observations
        """
        if not self.api_key:
            raise CollectorError("FRED API key not configured")

        # Default to last 90 days
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=90)

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start_date.strftime("%Y-%m-%d"),
            "observation_end": end_date.strftime("%Y-%m-%d"),
            "limit": limit,
            "sort_order": "desc",
        }

        url = f"{self.BASE_URL}/series/observations"

        await self.rate_limiter.wait()
        response = await self.http_client.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        data["series_id"] = series_id  # Add series ID for reference

        return data

    def parse(self, raw_data: Dict) -> List[Dict]:
        """Parse FRED API response into list of observations.

        Args:
            raw_data: Dict mapping series IDs to API responses

        Returns:
            List of parsed observations
        """
        all_observations = []

        for series_id, data in raw_data.items():
            observations = self.parse_series_response(data, series_id)
            all_observations.extend(observations)

        return all_observations

    def parse_series_response(
        self, response: Dict, series_id: Optional[str] = None
    ) -> List[Dict]:
        """Parse a single FRED series response.

        Args:
            response: FRED API response
            series_id: Series identifier (if not in response)

        Returns:
            List of observation dicts
        """
        observations = []
        series_id = series_id or response.get("series_id")

        for obs in response.get("observations", []):
            try:
                # Skip missing values
                value_str = obs.get("value", ".")
                if value_str == "." or not value_str:
                    continue

                parsed = {
                    "series_id": series_id,
                    "date": datetime.strptime(obs["date"], "%Y-%m-%d"),
                    "value": float(value_str),
                    "realtime_start": datetime.strptime(
                        obs.get("realtime_start", obs["date"]), "%Y-%m-%d"
                    ),
                    "realtime_end": datetime.strptime(
                        obs.get("realtime_end", obs["date"]), "%Y-%m-%d"
                    ),
                }
                observations.append(parsed)

            except (ValueError, KeyError) as e:
                logger.warning(f"Failed to parse observation: {e}")
                continue

        return observations

    async def store_observations(self, observations: List[Dict]) -> int:
        """Store parsed observations in database.

        Args:
            observations: List of parsed observations

        Returns:
            Number of observations stored
        """
        session = SessionLocal()
        count = 0

        try:
            for obs in observations:
                # Check if exists (update if newer)
                existing = (
                    session.query(FREDSeries)
                    .filter_by(
                        series_id=obs["series_id"],
                        observation_date=obs["date"],
                    )
                    .first()
                )

                if existing:
                    # Update if value changed
                    if existing.value != obs["value"]:
                        existing.value = obs["value"]
                        existing.realtime_start = obs["realtime_start"]
                        existing.realtime_end = obs["realtime_end"]
                        count += 1
                else:
                    # Insert new
                    record = FREDSeries(
                        series_id=obs["series_id"],
                        observation_date=obs["date"],
                        value=obs["value"],
                        realtime_start=obs["realtime_start"],
                        realtime_end=obs["realtime_end"],
                    )
                    session.add(record)
                    count += 1

            session.commit()
            logger.info(f"Stored/updated {count} FRED observations")

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store observations: {e}")
            raise
        finally:
            session.close()

        return count

    async def run_collection(
        self,
        series_ids: Optional[List[str]] = None,
        days_back: int = 90,
    ) -> int:
        """Run full collection cycle.

        Args:
            series_ids: Specific series to fetch (default: all configured)
            days_back: Number of days of history to fetch

        Returns:
            Number of observations stored
        """
        logger.info("Starting FRED collection")

        try:
            if series_ids is None:
                series_ids = list(FRED_SERIES.keys())

            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days_back)

            all_observations = []

            for series_id in series_ids:
                try:
                    data = await self.fetch_series(
                        series_id,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    observations = self.parse_series_response(data)
                    all_observations.extend(observations)
                except Exception as e:
                    logger.warning(f"Failed to collect {series_id}: {e}")
                    continue

            # Store raw data
            if all_observations:
                await self.store_raw({"series": series_ids, "observations": all_observations})

            # Store parsed data
            count = await self.store_observations(all_observations)

            logger.info(f"FRED collection complete: {count} observations")
            return count

        finally:
            await self.close()

    def get_latest_value(self, series_id: str) -> Optional[float]:
        """Get the latest value for a series from the database.

        Args:
            series_id: FRED series identifier

        Returns:
            Latest value or None
        """
        session = SessionLocal()
        try:
            result = (
                session.query(FREDSeries)
                .filter_by(series_id=series_id)
                .order_by(FREDSeries.observation_date.desc())
                .first()
            )
            return result.value if result else None
        finally:
            session.close()

    def get_series_data(
        self,
        series_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict]:
        """Get series data from database.

        Args:
            series_id: FRED series identifier
            start_date: Start date filter
            end_date: End date filter

        Returns:
            List of observation dicts
        """
        session = SessionLocal()
        try:
            query = session.query(FREDSeries).filter_by(series_id=series_id)

            if start_date:
                query = query.filter(FREDSeries.observation_date >= start_date)
            if end_date:
                query = query.filter(FREDSeries.observation_date <= end_date)

            results = query.order_by(FREDSeries.observation_date.desc()).all()

            return [
                {
                    "series_id": r.series_id,
                    "date": r.observation_date,
                    "value": r.value,
                }
                for r in results
            ]
        finally:
            session.close()
