"""TSA checkpoint throughput data collector.

Data Source: https://www.tsa.gov/travel/passenger-volumes
Frequency: Daily (released by 9am ET next day)
Historical: 2019-present
"""

import logging
import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector, CollectorError, ValidationError
from src.models.database import SessionLocal
from src.models.tsa import TSACheckpoint

logger = logging.getLogger(__name__)


# US federal holidays and common travel periods
HOLIDAY_PERIODS = {
    # Format: (month, day_start, day_end)
    "new_years": [(12, 30, 31), (1, 1, 3)],
    "mlk_day": [(1, 15, 21)],  # Third Monday of January
    "presidents_day": [(2, 15, 21)],
    "memorial_day": [(5, 25, 31)],
    "july_4th": [(7, 1, 7)],
    "labor_day": [(9, 1, 7)],
    "thanksgiving": [(11, 20, 30)],
    "christmas": [(12, 20, 31)],
}


def is_holiday_period(check_date: date) -> bool:
    """Check if date falls within a holiday travel period."""
    month = check_date.month
    day = check_date.day

    for period_list in HOLIDAY_PERIODS.values():
        for period in period_list:
            if len(period) == 3:
                p_month, p_start, p_end = period
                if month == p_month and p_start <= day <= p_end:
                    return True

    return False


class TSACheckpointCollector(BaseCollector[str, List[Dict]]):
    """Collector for TSA checkpoint throughput data.

    Scrapes daily passenger screening data from TSA website.
    Data is released by 9am ET the following day.
    """

    SOURCE_NAME = "tsa_checkpoint"
    DEFAULT_RATE_LIMIT = 0.5  # Be respectful to government sites

    TSA_URL = "https://www.tsa.gov/travel/passenger-volumes"

    async def fetch(self) -> str:
        """Fetch TSA passenger volumes page."""
        await self.rate_limiter.wait()

        try:
            response = await self.http_client.get(self.TSA_URL)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch TSA data: {e}")
            raise CollectorError(f"TSA fetch failed: {e}")

    def parse(self, raw_data: str) -> List[Dict]:
        """Parse TSA checkpoint data from HTML.

        The TSA page contains a table with columns:
        - Date
        - Current Year Throughput
        - Same Weekday Prior Year
        """
        soup = BeautifulSoup(raw_data, "html.parser")

        # Find the data table
        table = soup.find("table")
        if not table:
            raise ValidationError("Could not find data table on TSA page")

        records = []

        # Parse table rows (skip header)
        rows = table.find_all("tr")[1:]  # Skip header row

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            try:
                # Parse date
                date_text = cells[0].get_text(strip=True)
                parsed_date = self._parse_date(date_text)
                if not parsed_date:
                    continue

                # Parse throughput values
                current_throughput = self._parse_number(cells[1].get_text(strip=True))

                # Prior year throughput (may not always be present)
                prior_throughput = None
                if len(cells) >= 3:
                    prior_throughput = self._parse_number(cells[2].get_text(strip=True))

                # Calculate YoY change
                yoy_change = None
                if current_throughput and prior_throughput and prior_throughput > 0:
                    yoy_change = ((current_throughput - prior_throughput) / prior_throughput) * 100

                record = {
                    "date": parsed_date,
                    "current_year_throughput": current_throughput,
                    "prior_year_throughput": prior_throughput,
                    "yoy_change_pct": yoy_change,
                    "day_of_week": parsed_date.weekday(),
                    "is_holiday_period": is_holiday_period(parsed_date),
                }

                records.append(record)

            except Exception as e:
                logger.warning(f"Failed to parse TSA row: {e}")
                continue

        logger.info(f"Parsed {len(records)} TSA checkpoint records")
        return records

    def _parse_date(self, date_text: str) -> Optional[date]:
        """Parse date from various formats."""
        formats = [
            "%m/%d/%Y",
            "%m/%d/%y",
            "%Y-%m-%d",
            "%B %d, %Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_text, fmt).date()
            except ValueError:
                continue

        return None

    def _parse_number(self, text: str) -> Optional[int]:
        """Parse number from text, handling commas and formatting."""
        if not text:
            return None

        # Remove commas and whitespace
        clean = re.sub(r"[,\s]", "", text)

        try:
            return int(clean)
        except ValueError:
            return None

    async def store_checkpoints(self, records: List[Dict]) -> int:
        """Store checkpoint data in database.

        Args:
            records: Parsed checkpoint records

        Returns:
            Number of records stored
        """
        if not records:
            return 0

        session = SessionLocal()
        stored_count = 0

        try:
            for record in records:
                # Check if record already exists
                existing = (
                    session.query(TSACheckpoint)
                    .filter_by(date=record["date"])
                    .first()
                )

                if existing:
                    # Update existing record
                    existing.current_year_throughput = record["current_year_throughput"]
                    existing.prior_year_throughput = record["prior_year_throughput"]
                    existing.yoy_change_pct = record["yoy_change_pct"]
                    existing.day_of_week = record["day_of_week"]
                    existing.is_holiday_period = record["is_holiday_period"]
                else:
                    # Insert new record
                    checkpoint = TSACheckpoint(
                        date=record["date"],
                        current_year_throughput=record["current_year_throughput"],
                        prior_year_throughput=record["prior_year_throughput"],
                        yoy_change_pct=record["yoy_change_pct"],
                        day_of_week=record["day_of_week"],
                        is_holiday_period=record["is_holiday_period"],
                    )
                    session.add(checkpoint)
                    stored_count += 1

            session.commit()
            logger.info(f"Stored {stored_count} new TSA checkpoint records")
            return stored_count

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store TSA data: {e}")
            raise
        finally:
            session.close()

    async def run_collection(self) -> int:
        """Execute full collection cycle.

        Returns:
            Number of new records stored
        """
        logger.info("Starting TSA checkpoint collection")

        try:
            # Fetch raw HTML
            raw_html = await self.fetch()

            # Store raw data
            await self.store_raw(raw_html)

            # Parse records
            records = self.parse(raw_html)

            # Validate parsed data
            self._validate_records(records)

            # Store in database
            stored = await self.store_checkpoints(records)

            logger.info(f"TSA collection complete: {stored} new records")
            return stored

        finally:
            await self.close()

    def _validate_records(self, records: List[Dict]) -> None:
        """Validate parsed records for data quality."""
        if not records:
            raise ValidationError("No records parsed from TSA data")

        for record in records:
            throughput = record.get("current_year_throughput")
            if throughput is not None:
                # TSA throughput should be between 500K and 4M
                if throughput < 500_000 or throughput > 4_000_000:
                    logger.warning(
                        f"Unusual throughput value {throughput} for {record.get('date')}"
                    )
