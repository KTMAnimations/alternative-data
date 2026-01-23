"""Building permits data collector using FRED API.

Data Source: https://fred.stlouisfed.org/series/PERMIT
Frequency: Monthly (released ~3 weeks after month end)
Historical: 1960-present
"""

import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

from src.collectors.base import BaseCollector, CollectorError, ValidationError
from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.building_permits import BuildingPermit

logger = logging.getLogger(__name__)


# FRED series for building permits
PERMIT_SERIES = {
    "PERMIT": {"description": "New Private Housing Units Authorized", "type": "total", "sa": "SA"},
    "PERMITNSA": {"description": "New Private Housing Units Authorized NSA", "type": "total", "sa": "NSA"},
    "PERMIT1": {"description": "Single Family Housing Units Authorized", "type": "single_family", "sa": "SA"},
    "PERMIT2": {"description": "2-4 Unit Housing Units Authorized", "type": "multi_family_2_4", "sa": "SA"},
    "PERMIT5": {"description": "5+ Unit Housing Units Authorized", "type": "multi_family_5_plus", "sa": "SA"},
}


class BuildingPermitsCollector(BaseCollector[Dict, List[Dict]]):
    """Collector for building permits data from FRED.

    Extends existing FRED collection to focus on permit series.
    """

    SOURCE_NAME = "building_permits"
    DEFAULT_RATE_LIMIT = 2.0  # FRED allows 120 requests/minute

    FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = settings.fred_api_key

    async def fetch(
        self,
        series_ids: List[str] = None,
        start_date: date = None,
        end_date: date = None,
    ) -> Dict:
        """Fetch building permit data from FRED.

        Args:
            series_ids: FRED series to fetch
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Dict mapping series_id to observations
        """
        if not self.api_key:
            raise CollectorError("FRED API key not configured")

        if series_ids is None:
            series_ids = list(PERMIT_SERIES.keys())

        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365)

        all_data = {}

        for series_id in series_ids:
            await self.rate_limiter.wait()

            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date.strftime("%Y-%m-%d"),
                "observation_end": end_date.strftime("%Y-%m-%d"),
            }

            try:
                response = await self.http_client.get(self.FRED_BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()
                all_data[series_id] = data.get("observations", [])
            except Exception as e:
                logger.warning(f"Failed to fetch FRED series {series_id}: {e}")
                continue

        return {
            "data": all_data,
            "fetch_time": datetime.utcnow().isoformat(),
        }

    def parse(self, raw_data: Dict) -> List[Dict]:
        """Parse FRED permit data.

        Args:
            raw_data: Dict mapping series_id to observations

        Returns:
            List of parsed permit records
        """
        records = []
        data = raw_data.get("data", {})

        for series_id, observations in data.items():
            series_info = PERMIT_SERIES.get(series_id, {})

            for obs in observations:
                try:
                    # Skip missing values
                    value = obs.get("value")
                    if value in [".", "", None]:
                        continue

                    obs_date = datetime.strptime(obs["date"], "%Y-%m-%d").date()

                    record = {
                        "period": obs_date,
                        "geography_level": "national",
                        "geography_code": "US",
                        "geography_name": "United States",
                        "permit_type": series_info.get("type", "total"),
                        "units_authorized": int(float(value) * 1000),  # FRED reports in thousands
                        "is_seasonally_adjusted": series_info.get("sa", "SA"),
                    }

                    records.append(record)

                except Exception as e:
                    logger.warning(f"Failed to parse FRED observation: {e}")
                    continue

        logger.info(f"Parsed {len(records)} building permit records")
        return records

    async def store_permits(self, records: List[Dict]) -> int:
        """Store permit data in database.

        Args:
            records: Parsed permit records

        Returns:
            Number of records stored
        """
        if not records:
            return 0

        session = SessionLocal()
        stored_count = 0

        try:
            for record in records:
                # Check for existing record
                existing = (
                    session.query(BuildingPermit)
                    .filter_by(
                        period=record["period"],
                        geography_code=record["geography_code"],
                        permit_type=record["permit_type"],
                        is_seasonally_adjusted=record["is_seasonally_adjusted"],
                    )
                    .first()
                )

                if existing:
                    existing.units_authorized = record["units_authorized"]
                else:
                    permit = BuildingPermit(**record)
                    session.add(permit)
                    stored_count += 1

            session.commit()
            logger.info(f"Stored {stored_count} new building permit records")
            return stored_count

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store building permit data: {e}")
            raise
        finally:
            session.close()

    async def run_collection(
        self,
        lookback_days: int = 365,
    ) -> int:
        """Execute full collection cycle.

        Args:
            lookback_days: Days of history to fetch

        Returns:
            Number of new records stored
        """
        logger.info("Starting building permits collection")

        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)

        try:
            # Fetch data
            raw_data = await self.fetch(start_date=start_date, end_date=end_date)

            # Store raw data
            await self.store_raw(raw_data)

            # Parse records
            records = self.parse(raw_data)

            # Store in database
            stored = await self.store_permits(records)

            logger.info(f"Building permits collection complete: {stored} new records")
            return stored

        finally:
            await self.close()
