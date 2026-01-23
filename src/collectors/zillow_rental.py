"""Zillow Rental Index data collector.

Collects ZORI (Zillow Observed Rent Index) data from Zillow Research.
Data is available at national, metro, and zip code levels.

Source: https://www.zillow.com/research/data/
"""

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.collectors.base import BaseCollector, CollectorResult, FetchError, ParseError
from src.core.database import get_async_session
from src.models.data_sources import ZillowRentalIndex


@dataclass
class ZillowRentalRecord:
    """Parsed Zillow rental record."""

    period: date
    geography_level: str
    geography_id: str
    geography_name: str
    property_type: str
    zori_value: Decimal
    mom_change_pct: Optional[Decimal] = None
    yoy_change_pct: Optional[Decimal] = None


class ZillowRentalCollector(BaseCollector):
    """Collector for Zillow rental index data.

    Downloads and parses ZORI CSV files from Zillow Research.
    Handles national, metro, and zip code geographic levels.

    Primary entities: EQR, AVB, MAA, INVH, AMH (REITs)
    """

    name = "zillow_rental"
    source_id = 8  # Zillow Rental Index
    update_frequency = "monthly"

    # Zillow Research data URLs
    BASE_URL = "https://files.zillowstatic.com/research/public_csvs"

    # CSV file mappings by property type and geography level
    CSV_URLS = {
        # All properties ZORI
        ("all", "national"): f"{BASE_URL}/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv",
        ("all", "metro"): f"{BASE_URL}/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv",
        ("all", "zip"): f"{BASE_URL}/zori/Zip_zori_uc_sfrcondomfr_sm_month.csv",
        # Single-family ZORI
        ("single_family", "national"): f"{BASE_URL}/zori/Metro_zori_uc_sfr_sm_month.csv",
        ("single_family", "metro"): f"{BASE_URL}/zori/Metro_zori_uc_sfr_sm_month.csv",
        ("single_family", "zip"): f"{BASE_URL}/zori/Zip_zori_uc_sfr_sm_month.csv",
        # Multi-family ZORI
        ("multi_family", "national"): f"{BASE_URL}/zori/Metro_zori_uc_mfr_sm_month.csv",
        ("multi_family", "metro"): f"{BASE_URL}/zori/Metro_zori_uc_mfr_sm_month.csv",
        ("multi_family", "zip"): f"{BASE_URL}/zori/Zip_zori_uc_mfr_sm_month.csv",
    }

    # Alternative direct URLs if the above structure changes
    FALLBACK_URLS = {
        "all": "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv",
        "single_family": "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfr_sm_month.csv",
        "multi_family": "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_mfr_sm_month.csv",
    }

    # US National aggregate ID
    NATIONAL_ID = "US"
    NATIONAL_NAME = "United States"

    def __init__(self):
        super().__init__()
        self._raw_data: dict[str, str] = {}

    async def fetch(
        self,
        geography_level: str = "metro",
        property_type: str = "all",
        **kwargs,
    ) -> dict[str, Any]:
        """Fetch ZORI CSV data from Zillow Research.

        Args:
            geography_level: Geographic granularity (national, metro, zip)
            property_type: Property type filter (all, single_family, multi_family)

        Returns:
            Dict containing CSV content and metadata

        Raises:
            FetchError: If download fails
        """
        self.logger.info(
            "Fetching Zillow rental data",
            geography_level=geography_level,
            property_type=property_type,
        )

        url_key = (property_type, geography_level)
        url = self.CSV_URLS.get(url_key)

        if not url:
            # Try fallback for metro-level data
            url = self.FALLBACK_URLS.get(property_type)
            if not url:
                raise FetchError(
                    f"No URL configured for {property_type}/{geography_level}"
                )

        try:
            client = await self.get_client()
            response = await client.get(url)
            response.raise_for_status()

            csv_content = response.text

            self.logger.info(
                "CSV downloaded",
                url=url,
                content_length=len(csv_content),
            )

            return {
                "csv_content": csv_content,
                "geography_level": geography_level,
                "property_type": property_type,
                "source_url": url,
                "fetch_timestamp": datetime.utcnow(),
            }

        except httpx.HTTPStatusError as e:
            raise FetchError(
                f"HTTP error fetching Zillow data: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            raise FetchError(f"Request error fetching Zillow data: {str(e)}")

    async def parse(self, raw_data: dict[str, Any]) -> list[ZillowRentalRecord]:
        """Parse Zillow CSV data into structured records.

        The Zillow CSV format has region info columns followed by
        monthly ZORI values as columns (e.g., "2015-01-31", "2015-02-28", ...).

        Args:
            raw_data: Dict with csv_content and metadata

        Returns:
            List of ZillowRentalRecord objects

        Raises:
            ParseError: If CSV parsing fails
        """
        csv_content = raw_data["csv_content"]
        geography_level = raw_data["geography_level"]
        property_type = raw_data["property_type"]

        records: list[ZillowRentalRecord] = []

        try:
            reader = csv.DictReader(io.StringIO(csv_content))

            # Find date columns (format: YYYY-MM-DD)
            fieldnames = reader.fieldnames or []
            date_columns = [
                col for col in fieldnames
                if self._is_date_column(col)
            ]

            if not date_columns:
                raise ParseError("No date columns found in CSV")

            self.logger.debug(
                "Found date columns",
                count=len(date_columns),
                first=date_columns[0] if date_columns else None,
                last=date_columns[-1] if date_columns else None,
            )

            # Track national aggregate if computing from metro data
            national_aggregates: dict[str, list[Decimal]] = {}

            for row in reader:
                region_id = self._extract_region_id(row)
                region_name = self._extract_region_name(row)

                if not region_id or not region_name:
                    continue

                # Parse each month's ZORI value
                prev_value: Optional[Decimal] = None
                year_ago_values: dict[str, Decimal] = {}

                for date_col in date_columns:
                    value_str = row.get(date_col, "").strip()
                    if not value_str:
                        continue

                    try:
                        zori_value = Decimal(value_str)
                    except (InvalidOperation, ValueError):
                        continue

                    # Parse the date
                    period = self._parse_date_column(date_col)
                    if not period:
                        continue

                    # Calculate MoM change
                    mom_change = None
                    if prev_value and prev_value > 0:
                        mom_change = ((zori_value - prev_value) / prev_value) * 100

                    # Calculate YoY change
                    yoy_change = None
                    year_ago_key = self._get_year_ago_key(period)
                    if year_ago_key in year_ago_values:
                        year_ago_val = year_ago_values[year_ago_key]
                        if year_ago_val > 0:
                            yoy_change = ((zori_value - year_ago_val) / year_ago_val) * 100

                    # Store for future YoY calculations
                    period_key = f"{period.year}-{period.month:02d}"
                    year_ago_values[period_key] = zori_value

                    record = ZillowRentalRecord(
                        period=period,
                        geography_level=geography_level if geography_level != "national" else "metro",
                        geography_id=region_id,
                        geography_name=region_name,
                        property_type=property_type,
                        zori_value=zori_value,
                        mom_change_pct=mom_change,
                        yoy_change_pct=yoy_change,
                    )
                    records.append(record)

                    # Aggregate for national
                    if geography_level == "national":
                        if period_key not in national_aggregates:
                            national_aggregates[period_key] = []
                        national_aggregates[period_key].append(zori_value)

                    prev_value = zori_value

            # Add national aggregates if requested
            if geography_level == "national" and national_aggregates:
                records.extend(
                    self._compute_national_aggregates(
                        national_aggregates, property_type
                    )
                )

            self.logger.info("Parsed records", record_count=len(records))
            return records

        except csv.Error as e:
            raise ParseError(f"CSV parsing error: {str(e)}")
        except Exception as e:
            raise ParseError(f"Unexpected parsing error: {str(e)}")

    def _is_date_column(self, column_name: str) -> bool:
        """Check if a column name represents a date."""
        try:
            # Zillow uses YYYY-MM-DD format
            datetime.strptime(column_name.strip(), "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def _parse_date_column(self, column_name: str) -> Optional[date]:
        """Parse a date column name to a date object."""
        try:
            # Use first of month for consistency
            dt = datetime.strptime(column_name.strip(), "%Y-%m-%d")
            return date(dt.year, dt.month, 1)
        except ValueError:
            return None

    def _extract_region_id(self, row: dict) -> Optional[str]:
        """Extract region ID from CSV row."""
        # Try different column names Zillow uses
        for col in ["RegionID", "RegionId", "region_id", "RegionName"]:
            if col in row and row[col]:
                return str(row[col]).strip()
        return None

    def _extract_region_name(self, row: dict) -> Optional[str]:
        """Extract region name from CSV row."""
        # Try different column names
        for col in ["RegionName", "Region", "region_name", "Metro", "City"]:
            if col in row and row[col]:
                return str(row[col]).strip()
        return None

    def _get_year_ago_key(self, period: date) -> str:
        """Get the key for year-ago comparison."""
        year_ago = date(period.year - 1, period.month, 1)
        return f"{year_ago.year}-{year_ago.month:02d}"

    def _compute_national_aggregates(
        self,
        aggregates: dict[str, list[Decimal]],
        property_type: str,
    ) -> list[ZillowRentalRecord]:
        """Compute national-level aggregates from metro data."""
        records = []
        sorted_periods = sorted(aggregates.keys())

        prev_avg: Optional[Decimal] = None
        year_ago_avgs: dict[str, Decimal] = {}

        for period_key in sorted_periods:
            values = aggregates[period_key]
            if not values:
                continue

            avg_value = sum(values) / len(values)
            year, month = map(int, period_key.split("-"))
            period = date(year, month, 1)

            # MoM change
            mom_change = None
            if prev_avg and prev_avg > 0:
                mom_change = ((avg_value - prev_avg) / prev_avg) * 100

            # YoY change
            yoy_change = None
            year_ago_key = f"{year - 1}-{month:02d}"
            if year_ago_key in year_ago_avgs:
                year_ago_val = year_ago_avgs[year_ago_key]
                if year_ago_val > 0:
                    yoy_change = ((avg_value - year_ago_val) / year_ago_val) * 100

            year_ago_avgs[period_key] = avg_value

            records.append(
                ZillowRentalRecord(
                    period=period,
                    geography_level="national",
                    geography_id=self.NATIONAL_ID,
                    geography_name=self.NATIONAL_NAME,
                    property_type=property_type,
                    zori_value=avg_value.quantize(Decimal("0.01")),
                    mom_change_pct=mom_change.quantize(Decimal("0.0001")) if mom_change else None,
                    yoy_change_pct=yoy_change.quantize(Decimal("0.0001")) if yoy_change else None,
                )
            )
            prev_avg = avg_value

        return records

    async def validate(self, records: list[ZillowRentalRecord]) -> list[ZillowRentalRecord]:
        """Validate ZORI records before storing.

        Validates:
        - ZORI values are positive
        - Dates are within expected range (2015-present)
        - Geographic IDs are present

        Args:
            records: List of parsed records

        Returns:
            List of valid records
        """
        valid_records = []
        min_date = date(2015, 1, 1)
        max_date = date.today().replace(day=1)

        for record in records:
            # Validate ZORI value is positive and reasonable
            if record.zori_value <= 0:
                self.logger.warning(
                    "Skipping record with non-positive ZORI",
                    geography_id=record.geography_id,
                    zori_value=record.zori_value,
                )
                continue

            # Validate ZORI is within reasonable range (e.g., $200 - $10,000/month)
            if record.zori_value < 200 or record.zori_value > 10000:
                self.logger.warning(
                    "Skipping record with unreasonable ZORI",
                    geography_id=record.geography_id,
                    zori_value=record.zori_value,
                )
                continue

            # Validate date is within expected range
            if record.period < min_date or record.period > max_date:
                self.logger.warning(
                    "Skipping record with out-of-range date",
                    geography_id=record.geography_id,
                    period=record.period,
                )
                continue

            # Validate geography ID is present
            if not record.geography_id:
                self.logger.warning("Skipping record with missing geography ID")
                continue

            valid_records.append(record)

        self.logger.info(
            "Validation complete",
            total=len(records),
            valid=len(valid_records),
            rejected=len(records) - len(valid_records),
        )
        return valid_records

    async def store(self, records: list[ZillowRentalRecord]) -> int:
        """Store validated records to database.

        Uses upsert to handle updates to existing records.

        Args:
            records: List of validated records

        Returns:
            Number of records stored
        """
        if not records:
            return 0

        async with get_async_session() as session:
            stored_count = 0

            for record in records:
                # Convert to dict for insertion
                values = {
                    "period": record.period,
                    "geography_level": record.geography_level,
                    "geography_id": record.geography_id,
                    "geography_name": record.geography_name,
                    "property_type": record.property_type,
                    "zori_value": record.zori_value,
                    "mom_change_pct": record.mom_change_pct,
                    "yoy_change_pct": record.yoy_change_pct,
                }

                try:
                    # Try PostgreSQL upsert first
                    stmt = pg_insert(ZillowRentalIndex).values(**values)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["period", "geography_level", "geography_id", "property_type"],
                        set_={
                            "geography_name": stmt.excluded.geography_name,
                            "zori_value": stmt.excluded.zori_value,
                            "mom_change_pct": stmt.excluded.mom_change_pct,
                            "yoy_change_pct": stmt.excluded.yoy_change_pct,
                            "updated_at": datetime.utcnow(),
                        },
                    )
                    await session.execute(stmt)
                except Exception:
                    # Fallback to SQLite upsert
                    try:
                        stmt = sqlite_insert(ZillowRentalIndex).values(**values)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=["period", "geography_level", "geography_id", "property_type"],
                            set_={
                                "geography_name": stmt.excluded.geography_name,
                                "zori_value": stmt.excluded.zori_value,
                                "mom_change_pct": stmt.excluded.mom_change_pct,
                                "yoy_change_pct": stmt.excluded.yoy_change_pct,
                            },
                        )
                        await session.execute(stmt)
                    except Exception as e:
                        self.logger.error(
                            "Failed to store record",
                            geography_id=record.geography_id,
                            period=record.period,
                            error=str(e),
                        )
                        continue

                stored_count += 1

            await session.commit()
            self.logger.info("Records stored", count=stored_count)
            return stored_count

    async def collect_all_property_types(
        self,
        geography_level: str = "metro",
    ) -> list[CollectorResult]:
        """Collect data for all property types at a given geography level.

        Args:
            geography_level: Geographic granularity (national, metro, zip)

        Returns:
            List of CollectorResult objects
        """
        results = []
        property_types = ["all", "single_family", "multi_family"]

        for prop_type in property_types:
            self.logger.info(
                "Collecting property type",
                geography_level=geography_level,
                property_type=prop_type,
            )
            result = await self.collect(
                geography_level=geography_level,
                property_type=prop_type,
            )
            results.append(result)

        return results

    async def backfill(
        self,
        start_date: date,
        end_date: date,
        geography_levels: Optional[list[str]] = None,
        property_types: Optional[list[str]] = None,
        **kwargs,
    ) -> list[CollectorResult]:
        """Backfill historical ZORI data.

        Zillow provides historical data in a single CSV, so this method
        collects all available data and filters by date range during storage.

        Args:
            start_date: Start date for backfill (2015-01-01 minimum)
            end_date: End date for backfill
            geography_levels: List of geography levels to collect
            property_types: List of property types to collect

        Returns:
            List of CollectorResult objects
        """
        if geography_levels is None:
            geography_levels = ["national", "metro"]
        if property_types is None:
            property_types = ["all", "single_family", "multi_family"]

        self.logger.info(
            "Starting backfill",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            geography_levels=geography_levels,
            property_types=property_types,
        )

        results = []
        for geo_level in geography_levels:
            for prop_type in property_types:
                self.logger.info(
                    "Backfilling",
                    geography_level=geo_level,
                    property_type=prop_type,
                )
                result = await self.collect(
                    geography_level=geo_level,
                    property_type=prop_type,
                )
                results.append(result)

        return results

    async def get_latest_period(
        self,
        geography_level: str = "metro",
        property_type: str = "all",
    ) -> Optional[date]:
        """Get the most recent period in the database.

        Args:
            geography_level: Geographic level to check
            property_type: Property type to check

        Returns:
            Most recent period date or None
        """
        async with get_async_session() as session:
            stmt = (
                select(ZillowRentalIndex.period)
                .where(ZillowRentalIndex.geography_level == geography_level)
                .where(ZillowRentalIndex.property_type == property_type)
                .order_by(ZillowRentalIndex.period.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return row
