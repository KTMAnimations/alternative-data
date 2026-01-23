"""TSA Checkpoint passenger throughput data collector.

Collects daily passenger volumes from TSA.gov for airline industry analysis.
Primary entities: DAL, UAL, AAL, LUV, JBLU, JETS
"""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

import httpx
import structlog
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.collectors.base import BaseCollector, CollectorResult, FetchError, ParseError
from src.core.database import get_async_session
from src.models.data_sources import TSACheckpoint

logger = structlog.get_logger()


# Holiday periods for travel pattern analysis
HOLIDAY_PERIODS = [
    # New Year's
    ((12, 23), (1, 3)),
    # MLK Weekend
    ((1, 13), (1, 20)),
    # Presidents Day Weekend
    ((2, 14), (2, 21)),
    # Spring Break (approximate)
    ((3, 10), (4, 15)),
    # Memorial Day Weekend
    ((5, 24), (5, 31)),
    # Independence Day
    ((6, 30), (7, 7)),
    # Labor Day Weekend
    ((8, 29), (9, 5)),
    # Columbus Day Weekend
    ((10, 7), (10, 14)),
    # Thanksgiving
    ((11, 20), (12, 1)),
    # Christmas
    ((12, 18), (12, 31)),
]


def is_holiday_period(check_date: date) -> bool:
    """Check if date falls within a major travel holiday period."""
    month_day = (check_date.month, check_date.day)

    for start, end in HOLIDAY_PERIODS:
        # Handle year wraparound (Dec-Jan)
        if start > end:
            if month_day >= start or month_day <= end:
                return True
        else:
            if start <= month_day <= end:
                return True
    return False


class TSACheckpointCollector(BaseCollector):
    """Collector for TSA passenger throughput data.

    Scrapes the TSA.gov passenger volumes page to extract daily
    checkpoint throughput numbers for current year and prior year.

    The data provides leading indicators for:
    - Airline passenger demand (DAL, UAL, AAL, LUV, JBLU)
    - Travel industry ETFs (JETS)
    - Hotel and leisure demand
    """

    name = "tsa_checkpoint"
    source_id = 1  # TSA data source ID
    update_frequency = "daily"

    TSA_URL = "https://www.tsa.gov/travel/passenger-volumes"
    MIN_THROUGHPUT = 1_000_000  # Minimum realistic daily throughput
    MAX_THROUGHPUT = 4_000_000  # Maximum realistic daily throughput

    def __init__(self):
        super().__init__()
        self._html_cache: Optional[str] = None

    async def fetch(self, **kwargs) -> str:
        """Fetch HTML content from TSA passenger volumes page.

        Args:
            **kwargs: Optional arguments (date parameter for backfill is ignored
                     as TSA provides all data on single page)

        Returns:
            Raw HTML content from TSA.gov

        Raises:
            FetchError: If HTTP request fails
        """
        client = await self.get_client()

        try:
            response = await client.get(
                self.TSA_URL,
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
            response.raise_for_status()
            self._html_cache = response.text
            return response.text

        except httpx.HTTPStatusError as e:
            raise FetchError(
                f"HTTP {e.response.status_code} fetching TSA data: {e.response.reason_phrase}"
            )
        except httpx.RequestError as e:
            raise FetchError(f"Request failed: {str(e)}")

    async def parse(self, raw_data: str) -> list[dict[str, Any]]:
        """Parse HTML table to extract daily throughput data.

        The TSA page contains a table with columns:
        - Date
        - Current Year throughput
        - Prior Year throughput (same day of week)

        Args:
            raw_data: HTML content from TSA.gov

        Returns:
            List of dictionaries with parsed checkpoint data

        Raises:
            ParseError: If HTML structure is unexpected or data cannot be parsed
        """
        try:
            soup = BeautifulSoup(raw_data, "html.parser")

            # Find the data table
            table = soup.find("table")
            if not table:
                raise ParseError("Could not find data table on TSA page")

            records = []
            rows = table.find_all("tr")

            # Skip header row
            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) < 3:
                    continue

                try:
                    record = self._parse_row(cells)
                    if record:
                        records.append(record)
                except ValueError as e:
                    self.logger.warning(
                        "Failed to parse row",
                        error=str(e),
                        row_text=[c.get_text(strip=True) for c in cells]
                    )
                    continue

            if not records:
                raise ParseError("No valid records parsed from TSA page")

            self.logger.info(
                "Parsed TSA data",
                record_count=len(records),
                date_range=f"{records[-1]['date']} to {records[0]['date']}"
            )

            return records

        except ParseError:
            raise
        except Exception as e:
            raise ParseError(f"Failed to parse TSA HTML: {str(e)}")

    def _parse_row(self, cells: list) -> Optional[dict[str, Any]]:
        """Parse a single table row into a record.

        Args:
            cells: List of BeautifulSoup td elements

        Returns:
            Dictionary with parsed data or None if row is invalid
        """
        date_text = cells[0].get_text(strip=True)
        current_text = cells[1].get_text(strip=True)
        prior_text = cells[2].get_text(strip=True) if len(cells) > 2 else None

        # Parse date (format: "1/15/2024" or "January 15, 2024")
        parsed_date = self._parse_date(date_text)
        if not parsed_date:
            return None

        # Parse throughput numbers (remove commas)
        current_throughput = self._parse_number(current_text)
        if current_throughput is None:
            return None

        prior_throughput = self._parse_number(prior_text) if prior_text else None

        # Calculate YoY change
        yoy_change = None
        if prior_throughput and prior_throughput > 0:
            yoy_change = Decimal(str(
                ((current_throughput - prior_throughput) / prior_throughput) * 100
            )).quantize(Decimal("0.0001"))

        return {
            "date": parsed_date,
            "current_year_throughput": current_throughput,
            "prior_year_throughput": prior_throughput,
            "yoy_change_pct": yoy_change,
            "day_of_week": parsed_date.weekday(),
            "is_holiday_period": is_holiday_period(parsed_date),
        }

    def _parse_date(self, date_text: str) -> Optional[date]:
        """Parse date string in various formats."""
        # Try different date formats
        formats = [
            "%m/%d/%Y",
            "%m/%d/%y",
            "%B %d, %Y",
            "%b %d, %Y",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_text, fmt).date()
            except ValueError:
                continue

        # Try to extract date from text
        match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", date_text)
        if match:
            month, day, year = match.groups()
            year = int(year)
            if year < 100:
                year += 2000
            return date(year, int(month), int(day))

        return None

    def _parse_number(self, text: str) -> Optional[int]:
        """Parse number string, removing commas and handling edge cases."""
        if not text or text.strip() in ("-", "N/A", ""):
            return None

        # Remove commas and whitespace
        cleaned = re.sub(r"[,\s]", "", text)

        try:
            return int(cleaned)
        except ValueError:
            return None

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate throughput records.

        Validates:
        - Throughput values are in realistic range (1M-4M)
        - Dates are not in the future
        - No duplicate dates

        Args:
            records: List of parsed records

        Returns:
            List of valid records with data quality scores
        """
        valid_records = []
        seen_dates = set()
        today = date.today()

        for record in records:
            issues = []
            quality_score = Decimal("1.0")

            # Check for duplicate dates
            if record["date"] in seen_dates:
                self.logger.warning("Duplicate date found", date=record["date"])
                continue
            seen_dates.add(record["date"])

            # Check date is not in future
            if record["date"] > today:
                self.logger.warning("Future date found", date=record["date"])
                continue

            # Validate throughput range
            throughput = record["current_year_throughput"]
            if throughput < self.MIN_THROUGHPUT:
                issues.append("throughput_below_minimum")
                quality_score -= Decimal("0.1")
            elif throughput > self.MAX_THROUGHPUT:
                issues.append("throughput_above_maximum")
                quality_score -= Decimal("0.1")

            # Check prior year data availability
            if record["prior_year_throughput"] is None:
                issues.append("missing_prior_year")
                quality_score -= Decimal("0.05")

            record["data_quality_score"] = max(quality_score, Decimal("0.5"))
            record["validation_issues"] = issues
            valid_records.append(record)

        return valid_records

    async def store(self, records: list[dict[str, Any]]) -> int:
        """Store validated records to database using upsert.

        Args:
            records: List of validated records

        Returns:
            Number of records stored/updated
        """
        if not records:
            return 0

        async with get_async_session() as session:
            stored_count = 0

            for record in records:
                # Prepare record for database
                db_record = {
                    "date": record["date"],
                    "current_year_throughput": record["current_year_throughput"],
                    "prior_year_throughput": record["prior_year_throughput"],
                    "yoy_change_pct": record["yoy_change_pct"],
                    "day_of_week": record["day_of_week"],
                    "is_holiday_period": record["is_holiday_period"],
                    "data_quality_score": record["data_quality_score"],
                }

                # Use PostgreSQL upsert (INSERT ... ON CONFLICT)
                stmt = pg_insert(TSACheckpoint).values(**db_record)
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_tsa_date",
                    set_={
                        "current_year_throughput": stmt.excluded.current_year_throughput,
                        "prior_year_throughput": stmt.excluded.prior_year_throughput,
                        "yoy_change_pct": stmt.excluded.yoy_change_pct,
                        "data_quality_score": stmt.excluded.data_quality_score,
                        "revision_status": "revised",
                    }
                )

                await session.execute(stmt)
                stored_count += 1

            await session.commit()

        return stored_count

    async def backfill(
        self,
        start_date: date,
        end_date: date,
        **kwargs
    ) -> list[CollectorResult]:
        """Backfill historical data from TSA.

        TSA provides all historical data on a single page, so we fetch once
        and filter records by date range.

        Args:
            start_date: Start of date range (2019-01-01 minimum)
            end_date: End of date range

        Returns:
            List containing single CollectorResult
        """
        self.logger.info(
            "Starting TSA backfill",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        # TSA data starts from 2019
        min_date = date(2019, 1, 1)
        if start_date < min_date:
            start_date = min_date
            self.logger.info(f"Adjusted start date to {start_date}")

        try:
            # Fetch all data
            raw_data = await self._fetch_with_retry()

            # Parse all records
            all_records = await self.parse(raw_data)

            # Filter to date range
            filtered_records = [
                r for r in all_records
                if start_date <= r["date"] <= end_date
            ]

            self.logger.info(
                "Filtered records for backfill",
                total_records=len(all_records),
                filtered_records=len(filtered_records),
            )

            # Validate
            valid_records = await self.validate(filtered_records)

            # Store
            stored_count = await self.store(valid_records)

            return [CollectorResult(
                success=True,
                data=valid_records,
                records_fetched=len(filtered_records),
                records_stored=stored_count,
                fetch_timestamp=datetime.utcnow(),
                metadata={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "total_available": len(all_records),
                }
            )]

        except Exception as e:
            self.logger.exception("Backfill failed")
            return [CollectorResult(
                success=False,
                error_message=str(e),
                fetch_timestamp=datetime.utcnow(),
            )]
        finally:
            await self.close()

    async def check_data_gaps(
        self,
        start_date: date,
        end_date: date,
    ) -> list[date]:
        """Check for gaps in stored data.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of dates missing from database
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(TSACheckpoint.date)
                .where(TSACheckpoint.date >= start_date)
                .where(TSACheckpoint.date <= end_date)
            )
            stored_dates = {row[0] for row in result.fetchall()}

        # Generate all dates in range
        all_dates = set()
        current = start_date
        while current <= end_date:
            all_dates.add(current)
            current += timedelta(days=1)

        # Find missing dates
        missing = sorted(all_dates - stored_dates)

        return missing


# Singleton instance for convenience
tsa_collector = TSACheckpointCollector()
