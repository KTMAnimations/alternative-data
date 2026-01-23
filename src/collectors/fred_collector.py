"""FRED API collector for building permits data."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

import httpx

from src.collectors.base import BaseCollector, CollectorResult, FetchError, ParseError
from src.core.config import settings
from src.core.database import get_async_session
from src.models.data_sources import BuildingPermitData


# FRED Series IDs for building permits
FRED_SERIES = {
    # National total permits (seasonally adjusted annual rate, thousands)
    "PERMIT": {
        "geography_level": "national",
        "geography_code": "US",
        "geography_name": "United States",
        "permit_type": "total",
        "seasonally_adjusted": True,
    },
    # National total permits (not seasonally adjusted)
    "PERMITNSA": {
        "geography_level": "national",
        "geography_code": "US",
        "geography_name": "United States",
        "permit_type": "total",
        "seasonally_adjusted": False,
    },
    # Single-family permits (seasonally adjusted)
    "PERMIT1": {
        "geography_level": "national",
        "geography_code": "US",
        "geography_name": "United States",
        "permit_type": "single_family",
        "seasonally_adjusted": True,
    },
    # Multi-family permits (5+ units, seasonally adjusted)
    "PERMIT5": {
        "geography_level": "national",
        "geography_code": "US",
        "geography_name": "United States",
        "permit_type": "multi_family_5plus",
        "seasonally_adjusted": True,
    },
    # Housing starts (for ratio calculations)
    "HOUST": {
        "geography_level": "national",
        "geography_code": "US",
        "geography_name": "United States",
        "permit_type": "housing_starts",
        "seasonally_adjusted": True,
    },
    # Single-family housing starts
    "HOUST1F": {
        "geography_level": "national",
        "geography_code": "US",
        "geography_name": "United States",
        "permit_type": "housing_starts_single_family",
        "seasonally_adjusted": True,
    },
    # Regional permits - Northeast
    "PERMIT1NE": {
        "geography_level": "region",
        "geography_code": "NE",
        "geography_name": "Northeast",
        "permit_type": "single_family",
        "seasonally_adjusted": True,
    },
    # Regional permits - Midwest
    "PERMIT1MW": {
        "geography_level": "region",
        "geography_code": "MW",
        "geography_name": "Midwest",
        "permit_type": "single_family",
        "seasonally_adjusted": True,
    },
    # Regional permits - South
    "PERMIT1S": {
        "geography_level": "region",
        "geography_code": "SO",
        "geography_name": "South",
        "permit_type": "single_family",
        "seasonally_adjusted": True,
    },
    # Regional permits - West
    "PERMIT1W": {
        "geography_level": "region",
        "geography_code": "WE",
        "geography_name": "West",
        "permit_type": "single_family",
        "seasonally_adjusted": True,
    },
}

# Primary entities for homebuilders and home improvement
PRIMARY_ENTITIES = ["DHI", "LEN", "PHM", "HD", "LOW"]


class FREDCollector(BaseCollector):
    """Collector for FRED building permits data."""

    name = "fred_building_permits"
    source_id = 5  # F-005
    update_frequency = "monthly"

    FRED_API_BASE = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, series_ids: Optional[list[str]] = None):
        """Initialize FRED collector.

        Args:
            series_ids: List of FRED series IDs to collect.
                       If None, collects all configured series.
        """
        super().__init__()
        self.series_ids = series_ids or list(FRED_SERIES.keys())
        self._api_key = settings.fred_api_key

    def _validate_api_key(self) -> None:
        """Validate FRED API key is configured."""
        if not self._api_key:
            raise FetchError(
                "FRED API key not configured. Set FRED_API_KEY environment variable."
            )

    async def fetch(
        self,
        series_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        **kwargs
    ) -> dict[str, Any]:
        """Fetch data from FRED API.

        Args:
            series_id: Specific series to fetch. If None, fetches all configured series.
            start_date: Start date for observations.
            end_date: End date for observations.

        Returns:
            Dictionary with series_id -> observations mapping.

        Raises:
            FetchError: If API request fails.
        """
        self._validate_api_key()

        series_to_fetch = [series_id] if series_id else self.series_ids
        results = {}

        client = await self.get_client()

        for sid in series_to_fetch:
            if sid not in FRED_SERIES:
                self.logger.warning("Unknown series ID", series_id=sid)
                continue

            params = {
                "series_id": sid,
                "api_key": self._api_key,
                "file_type": "json",
                "sort_order": "asc",
            }

            if start_date:
                params["observation_start"] = start_date.isoformat()
            if end_date:
                params["observation_end"] = end_date.isoformat()

            try:
                response = await client.get(self.FRED_API_BASE, params=params)
                response.raise_for_status()
                data = response.json()

                if "observations" not in data:
                    self.logger.warning(
                        "No observations in response",
                        series_id=sid,
                        response_keys=list(data.keys()),
                    )
                    continue

                results[sid] = {
                    "observations": data["observations"],
                    "metadata": FRED_SERIES[sid],
                }

                self.logger.debug(
                    "Fetched series",
                    series_id=sid,
                    observation_count=len(data["observations"]),
                )

            except httpx.HTTPStatusError as e:
                self.logger.error(
                    "FRED API error",
                    series_id=sid,
                    status_code=e.response.status_code,
                    response_text=e.response.text[:500],
                )
                raise FetchError(f"FRED API error for {sid}: {e.response.status_code}")
            except httpx.HTTPError as e:
                self.logger.error("HTTP error", series_id=sid, error=str(e))
                raise FetchError(f"HTTP error fetching {sid}: {str(e)}")

        if not results:
            raise FetchError("No data fetched from any series")

        return results

    async def parse(self, raw_data: dict[str, Any]) -> list[BuildingPermitData]:
        """Parse FRED API response into BuildingPermitData records.

        Args:
            raw_data: Dictionary with series_id -> observations mapping.

        Returns:
            List of BuildingPermitData model instances.

        Raises:
            ParseError: If parsing fails.
        """
        records = []

        try:
            for series_id, series_data in raw_data.items():
                metadata = series_data["metadata"]
                observations = series_data["observations"]

                for obs in observations:
                    # Skip missing values (FRED uses "." for missing)
                    if obs["value"] == ".":
                        continue

                    try:
                        # Parse date (FRED uses YYYY-MM-DD format)
                        obs_date = datetime.strptime(obs["date"], "%Y-%m-%d").date()

                        # Parse value (FRED returns thousands for permit series)
                        # Convert to actual units
                        raw_value = float(obs["value"])
                        units_authorized = int(raw_value * 1000)  # Convert from thousands

                        record = BuildingPermitData(
                            period=obs_date,
                            geography_level=metadata["geography_level"],
                            geography_code=metadata["geography_code"],
                            geography_name=metadata["geography_name"],
                            permit_type=metadata["permit_type"],
                            units_authorized=units_authorized,
                            seasonally_adjusted=metadata["seasonally_adjusted"],
                        )
                        records.append(record)

                    except (ValueError, KeyError) as e:
                        self.logger.warning(
                            "Failed to parse observation",
                            series_id=series_id,
                            observation=obs,
                            error=str(e),
                        )
                        continue

        except Exception as e:
            self.logger.error("Parse error", error=str(e))
            raise ParseError(f"Failed to parse FRED data: {str(e)}")

        return records

    async def validate(self, records: list[BuildingPermitData]) -> list[BuildingPermitData]:
        """Validate parsed records.

        Args:
            records: List of BuildingPermitData records.

        Returns:
            List of valid records.
        """
        valid_records = []

        for record in records:
            # Validate positive units (permits should be positive)
            if record.units_authorized < 0:
                self.logger.warning(
                    "Invalid negative units",
                    period=record.period,
                    units=record.units_authorized,
                )
                continue

            # Validate date is not in the future
            if record.period > date.today():
                self.logger.warning(
                    "Future date detected",
                    period=record.period,
                )
                continue

            # Validate date is within reasonable historical range (1960+)
            if record.period.year < 1960:
                self.logger.warning(
                    "Date too old",
                    period=record.period,
                )
                continue

            valid_records.append(record)

        return valid_records

    async def store(self, records: list[BuildingPermitData]) -> int:
        """Store validated records to database.

        Args:
            records: List of BuildingPermitData records.

        Returns:
            Number of records stored.
        """
        if not records:
            return 0

        stored_count = 0

        async with get_async_session() as session:
            for record in records:
                # Use merge to handle upserts (update existing or insert new)
                merged = await session.merge(record)
                stored_count += 1

            await session.commit()

        return stored_count

    async def compute_changes(
        self,
        records: list[BuildingPermitData],
    ) -> list[BuildingPermitData]:
        """Compute MoM and YoY changes for records.

        Args:
            records: List of BuildingPermitData records.

        Returns:
            Records with mom_change_pct and yoy_change_pct populated.
        """
        # Group records by geography and permit type
        from collections import defaultdict
        grouped: dict[tuple, list[BuildingPermitData]] = defaultdict(list)

        for record in records:
            key = (
                record.geography_level,
                record.geography_code,
                record.permit_type,
                record.seasonally_adjusted,
            )
            grouped[key].append(record)

        # Sort each group by date and compute changes
        for key, group in grouped.items():
            sorted_group = sorted(group, key=lambda r: r.period)

            for i, record in enumerate(sorted_group):
                # MoM change (compare to previous month)
                if i > 0:
                    prev = sorted_group[i - 1]
                    # Check if previous record is actually the prior month
                    expected_prev_month = record.period.replace(day=1)
                    if prev.period.month == expected_prev_month.month - 1 or (
                        prev.period.month == 12 and expected_prev_month.month == 1
                    ):
                        if prev.units_authorized > 0:
                            mom_change = (
                                (record.units_authorized - prev.units_authorized)
                                / prev.units_authorized
                            ) * 100
                            record.mom_change_pct = Decimal(str(round(mom_change, 4)))

                # YoY change (compare to same month last year)
                prior_year_date = record.period.replace(year=record.period.year - 1)
                for prev in sorted_group:
                    if prev.period == prior_year_date:
                        if prev.units_authorized > 0:
                            yoy_change = (
                                (record.units_authorized - prev.units_authorized)
                                / prev.units_authorized
                            ) * 100
                            record.yoy_change_pct = Decimal(str(round(yoy_change, 4)))
                        break

        return records

    async def backfill(
        self,
        start_date: date,
        end_date: date,
        **kwargs
    ) -> list[CollectorResult]:
        """Backfill historical data for a date range.

        FRED API supports fetching entire date range in one request,
        so we override the default day-by-day approach.

        Args:
            start_date: Start date for backfill.
            end_date: End date for backfill.

        Returns:
            List containing a single CollectorResult.
        """
        self.logger.info(
            "Starting FRED backfill",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            series_count=len(self.series_ids),
        )

        try:
            # Fetch all data for date range
            raw_data = await self.fetch(
                start_date=start_date,
                end_date=end_date,
            )

            # Parse records
            records = await self.parse(raw_data)

            # Compute changes
            records = await self.compute_changes(records)

            # Validate
            valid_records = await self.validate(records)

            # Store
            stored_count = await self.store(valid_records)

            self.logger.info(
                "FRED backfill complete",
                records_fetched=len(records),
                records_stored=stored_count,
            )

            return [CollectorResult(
                success=True,
                data=valid_records,
                records_fetched=len(records),
                records_stored=stored_count,
                metadata={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "series_ids": self.series_ids,
                },
            )]

        except Exception as e:
            self.logger.exception("FRED backfill failed")
            return [CollectorResult(
                success=False,
                error_message=str(e),
            )]
        finally:
            await self.close()

    async def collect(self, **kwargs) -> CollectorResult:
        """Collect latest FRED data.

        By default, fetches the last 24 months of data to ensure
        we have enough history for MoM and YoY calculations.
        """
        from dateutil.relativedelta import relativedelta

        end_date = kwargs.get("end_date", date.today())
        start_date = kwargs.get("start_date", end_date - relativedelta(months=24))

        results = await self.backfill(start_date, end_date)
        return results[0] if results else CollectorResult(
            success=False,
            error_message="No results from backfill",
        )
