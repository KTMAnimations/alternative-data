"""UK Carbon Intensity API collector.

Data source: https://carbonintensity.org.uk/
Endpoints: /intensity, /generation, /regional
No authentication required.

Collects:
- National and regional carbon intensity data (gCO2/kWh)
- Generation mix by fuel type (biomass, coal, gas, nuclear, solar, wind, etc.)
- Updates every 30 minutes
- Historical data available from 2018
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
import structlog

from src.collectors.base import BaseCollector, CollectorResult, FetchError, ParseError
from src.models.data_sources import CarbonIntensityReading
from src.core.database import get_async_session

logger = structlog.get_logger()

# Base URL for the UK Carbon Intensity API
BASE_URL = "https://api.carbonintensity.org.uk"

# Region codes for UK DNO regions
UK_REGIONS = [
    "national",  # National grid
    "1",   # North Scotland
    "2",   # South Scotland
    "3",   # North West England
    "4",   # North East England
    "5",   # Yorkshire
    "6",   # North Wales, Merseyside and Cheshire
    "7",   # South Wales
    "8",   # West Midlands
    "9",   # East Midlands
    "10",  # East England
    "11",  # South West England
    "12",  # South England
    "13",  # London
    "14",  # South East England
]

# Fuel types in the generation mix
FUEL_TYPES = [
    "biomass",
    "coal",
    "imports",
    "gas",
    "nuclear",
    "other",
    "hydro",
    "solar",
    "wind",
]

# Renewable fuel types for calculating renewable percentage
RENEWABLE_FUELS = {"biomass", "hydro", "solar", "wind"}


class CarbonIntensityCollector(BaseCollector):
    """Collector for UK Carbon Intensity API data."""

    name = "carbon_intensity"
    source_id = 4  # Adjust based on data_sources table
    update_frequency = "continuous"  # 30-minute intervals

    def __init__(self, regions: Optional[list[str]] = None):
        """Initialize collector.

        Args:
            regions: List of region codes to collect. Defaults to national only.
        """
        super().__init__()
        self.regions = regions or ["national"]

    async def fetch(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        **kwargs
    ) -> dict[str, Any]:
        """Fetch carbon intensity and generation data from API.

        Args:
            start_time: Start of time range (defaults to 24h ago)
            end_time: End of time range (defaults to now)

        Returns:
            Dict containing intensity and generation data per region

        Raises:
            FetchError: If API request fails
        """
        client = await self.get_client()

        # Default to last 24 hours if not specified
        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(hours=24)

        # Format times for API (ISO 8601 without timezone)
        start_str = start_time.strftime("%Y-%m-%dT%H:%MZ")
        end_str = end_time.strftime("%Y-%m-%dT%H:%MZ")

        results = {"regions": {}}

        for region in self.regions:
            try:
                if region == "national":
                    # National intensity with generation mix
                    intensity_url = f"{BASE_URL}/intensity/{start_str}/{end_str}"
                    generation_url = f"{BASE_URL}/generation/{start_str}/{end_str}"
                else:
                    # Regional intensity
                    intensity_url = f"{BASE_URL}/regional/regionid/{region}/intensity/{start_str}/{end_str}"
                    generation_url = f"{BASE_URL}/regional/regionid/{region}/generation/{start_str}/{end_str}"

                self.logger.debug(
                    "Fetching carbon intensity data",
                    region=region,
                    start=start_str,
                    end=end_str
                )

                # Fetch intensity data
                intensity_resp = await client.get(intensity_url)
                if intensity_resp.status_code != 200:
                    self.logger.warning(
                        "Failed to fetch intensity data",
                        region=region,
                        status=intensity_resp.status_code,
                        body=intensity_resp.text[:500]
                    )
                    continue

                intensity_data = intensity_resp.json()

                # Fetch generation mix data
                generation_resp = await client.get(generation_url)
                if generation_resp.status_code != 200:
                    self.logger.warning(
                        "Failed to fetch generation data",
                        region=region,
                        status=generation_resp.status_code
                    )
                    generation_data = None
                else:
                    generation_data = generation_resp.json()

                results["regions"][region] = {
                    "intensity": intensity_data,
                    "generation": generation_data
                }

            except Exception as e:
                self.logger.error(
                    "Error fetching region data",
                    region=region,
                    error=str(e)
                )
                raise FetchError(f"Failed to fetch data for region {region}: {e}")

        if not results["regions"]:
            raise FetchError("No data retrieved from any region")

        results["fetch_params"] = {
            "start_time": start_str,
            "end_time": end_str,
            "regions": self.regions
        }

        return results

    async def parse(self, raw_data: dict[str, Any]) -> list[CarbonIntensityReading]:
        """Parse API response into CarbonIntensityReading records.

        Args:
            raw_data: Raw API response data

        Returns:
            List of CarbonIntensityReading objects

        Raises:
            ParseError: If parsing fails
        """
        records = []

        try:
            for region, data in raw_data.get("regions", {}).items():
                intensity_data = data.get("intensity", {})
                generation_data = data.get("generation")

                # Parse intensity data
                intensity_list = intensity_data.get("data", [])
                if not intensity_list:
                    self.logger.warning("No intensity data for region", region=region)
                    continue

                # Build generation mix lookup by timestamp
                gen_mix_by_time = {}
                if generation_data and "data" in generation_data:
                    for gen_entry in generation_data.get("data", []):
                        gen_from = gen_entry.get("from")
                        if gen_from and "generationmix" in gen_entry:
                            gen_mix_by_time[gen_from] = {
                                item["fuel"]: item["perc"]
                                for item in gen_entry["generationmix"]
                            }

                for entry in intensity_list:
                    try:
                        # Parse timestamp
                        timestamp_str = entry.get("from")
                        if not timestamp_str:
                            continue

                        timestamp = datetime.fromisoformat(
                            timestamp_str.replace("Z", "+00:00")
                        )

                        # Get intensity values
                        intensity_info = entry.get("intensity", {})
                        forecast = intensity_info.get("forecast")
                        actual = intensity_info.get("actual")
                        index = intensity_info.get("index", "unknown")

                        if forecast is None:
                            self.logger.debug(
                                "Skipping entry with no forecast",
                                timestamp=timestamp_str
                            )
                            continue

                        # Get generation mix for this timestamp
                        gen_mix = gen_mix_by_time.get(timestamp_str, {})

                        # Calculate renewable percentage
                        renewable_pct = sum(
                            gen_mix.get(fuel, 0) for fuel in RENEWABLE_FUELS
                        )

                        # Create record
                        record = CarbonIntensityReading(
                            timestamp=timestamp,
                            region=region,
                            intensity_forecast=int(forecast),
                            intensity_actual=int(actual) if actual is not None else None,
                            intensity_index=index,
                            generation_mix=gen_mix,
                            renewable_pct=Decimal(str(renewable_pct))
                        )
                        records.append(record)

                    except (ValueError, KeyError, TypeError) as e:
                        self.logger.warning(
                            "Failed to parse intensity entry",
                            entry=entry,
                            error=str(e)
                        )
                        continue

        except Exception as e:
            raise ParseError(f"Failed to parse carbon intensity data: {e}")

        self.logger.info("Parsed carbon intensity records", count=len(records))
        return records

    async def validate(self, records: list[CarbonIntensityReading]) -> list[CarbonIntensityReading]:
        """Validate carbon intensity records.

        Validates:
        - Intensity values within expected range (0-500 gCO2/kWh)
        - Generation mix percentages sum to approximately 100%
        - Timestamps are at 30-minute intervals

        Args:
            records: List of parsed records

        Returns:
            List of valid records
        """
        valid_records = []

        for record in records:
            # Validate intensity range (typical UK values 0-500 gCO2/kWh)
            if not (0 <= record.intensity_forecast <= 500):
                self.logger.warning(
                    "Intensity forecast out of range",
                    forecast=record.intensity_forecast,
                    timestamp=record.timestamp
                )
                continue

            if record.intensity_actual is not None and not (0 <= record.intensity_actual <= 500):
                self.logger.warning(
                    "Intensity actual out of range",
                    actual=record.intensity_actual,
                    timestamp=record.timestamp
                )
                continue

            # Validate generation mix sums to ~100% (allow 1% tolerance)
            if record.generation_mix:
                total_pct = sum(record.generation_mix.values())
                if not (99.0 <= total_pct <= 101.0):
                    self.logger.warning(
                        "Generation mix does not sum to ~100%",
                        total=total_pct,
                        mix=record.generation_mix,
                        timestamp=record.timestamp
                    )
                    # Don't reject, just log warning - API occasionally has rounding issues

            # Validate 30-minute intervals
            if record.timestamp.minute not in (0, 30):
                self.logger.warning(
                    "Timestamp not on 30-minute interval",
                    timestamp=record.timestamp,
                    minute=record.timestamp.minute
                )
                # Don't reject - API occasionally has slight timing offsets

            # Validate renewable percentage
            if not (Decimal("0") <= record.renewable_pct <= Decimal("100")):
                self.logger.warning(
                    "Renewable percentage out of range",
                    renewable_pct=record.renewable_pct,
                    timestamp=record.timestamp
                )
                continue

            valid_records.append(record)

        self.logger.info(
            "Validation complete",
            total=len(records),
            valid=len(valid_records),
            rejected=len(records) - len(valid_records)
        )
        return valid_records

    async def store(self, records: list[CarbonIntensityReading]) -> int:
        """Store carbon intensity records to database.

        Uses upsert logic to handle duplicate timestamps.

        Args:
            records: List of validated records

        Returns:
            Number of records stored
        """
        if not records:
            return 0

        stored_count = 0

        async with get_async_session() as session:
            from sqlalchemy import select
            from sqlalchemy.dialects.postgresql import insert

            for record in records:
                try:
                    # Check for existing record
                    existing = await session.execute(
                        select(CarbonIntensityReading).where(
                            CarbonIntensityReading.timestamp == record.timestamp,
                            CarbonIntensityReading.region == record.region
                        )
                    )
                    existing_record = existing.scalar_one_or_none()

                    if existing_record:
                        # Update existing record if actual value now available
                        if record.intensity_actual is not None and existing_record.intensity_actual is None:
                            existing_record.intensity_actual = record.intensity_actual
                            existing_record.generation_mix = record.generation_mix
                            existing_record.renewable_pct = record.renewable_pct
                            stored_count += 1
                    else:
                        # Insert new record
                        session.add(record)
                        stored_count += 1

                except Exception as e:
                    self.logger.error(
                        "Failed to store record",
                        timestamp=record.timestamp,
                        region=record.region,
                        error=str(e)
                    )
                    continue

            await session.commit()

        self.logger.info("Stored carbon intensity records", count=stored_count)
        return stored_count

    async def backfill(
        self,
        start_date: date,
        end_date: date,
        batch_size_days: int = 7,
        **kwargs
    ) -> list[CollectorResult]:
        """Backfill historical carbon intensity data.

        Args:
            start_date: Start date for backfill (earliest 2018-01-01)
            end_date: End date for backfill
            batch_size_days: Number of days per API request (max 14)

        Returns:
            List of CollectorResult objects for each batch
        """
        # Ensure we don't go before 2018 (API data availability)
        earliest_date = date(2018, 1, 1)
        if start_date < earliest_date:
            self.logger.warning(
                "Start date before API availability, adjusting",
                requested=start_date,
                adjusted=earliest_date
            )
            start_date = earliest_date

        # Limit batch size to API limits
        batch_size_days = min(batch_size_days, 14)

        self.logger.info(
            "Starting carbon intensity backfill",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            batch_size_days=batch_size_days
        )

        results = []
        current_start = datetime.combine(start_date, datetime.min.time())
        final_end = datetime.combine(end_date, datetime.max.time())

        while current_start < final_end:
            current_end = min(
                current_start + timedelta(days=batch_size_days),
                final_end
            )

            try:
                result = await self.collect(
                    start_time=current_start,
                    end_time=current_end
                )
                results.append(result)

                self.logger.info(
                    "Backfill batch complete",
                    start=current_start.isoformat(),
                    end=current_end.isoformat(),
                    success=result.success,
                    records=result.records_stored
                )

            except Exception as e:
                self.logger.error(
                    "Backfill batch failed",
                    start=current_start.isoformat(),
                    end=current_end.isoformat(),
                    error=str(e)
                )
                results.append(CollectorResult(
                    success=False,
                    error_message=str(e),
                    fetch_timestamp=datetime.utcnow()
                ))

            current_start = current_end

        successful = sum(1 for r in results if r.success)
        total_records = sum(r.records_stored for r in results)

        self.logger.info(
            "Backfill complete",
            total_batches=len(results),
            successful_batches=successful,
            total_records=total_records
        )

        return results


async def create_carbon_intensity_collector(
    regions: Optional[list[str]] = None,
    include_all_regions: bool = False
) -> CarbonIntensityCollector:
    """Factory function to create a CarbonIntensityCollector.

    Args:
        regions: Specific regions to collect (overrides include_all_regions)
        include_all_regions: If True, collect all UK regions plus national

    Returns:
        Configured CarbonIntensityCollector instance
    """
    if regions:
        selected_regions = regions
    elif include_all_regions:
        selected_regions = UK_REGIONS
    else:
        selected_regions = ["national"]

    return CarbonIntensityCollector(regions=selected_regions)
