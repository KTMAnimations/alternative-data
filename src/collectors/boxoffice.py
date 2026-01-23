"""Box office data collector from The Numbers."""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.collectors.base import BaseCollector, CollectorResult, FetchError, ParseError
from src.core.database import get_async_session
from src.entity_mapping.studio_ticker_mapping import get_ticker_for_studio
from src.models.data_sources import BoxOfficeDaily


class BoxOfficeCollector(BaseCollector):
    """Collector for daily box office data from The Numbers."""

    name = "boxoffice"
    source_id = 6  # Box office data source ID
    update_frequency = "daily"

    BASE_URL = "https://www.the-numbers.com"
    DAILY_CHART_URL = f"{BASE_URL}/box-office-chart/daily"
    WEEKEND_CHART_URL = f"{BASE_URL}/box-office-chart/weekend"

    # Historical data available from 1995
    BACKFILL_START_DATE = date(1995, 1, 1)

    def __init__(self):
        super().__init__()
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    async def fetch(
        self,
        target_date: Optional[date] = None,
        chart_type: str = "daily",
        **kwargs,
    ) -> str:
        """Fetch box office chart HTML from The Numbers.

        Args:
            target_date: Date to fetch data for (defaults to yesterday)
            chart_type: 'daily' or 'weekend'

        Returns:
            HTML content of the chart page

        Raises:
            FetchError: If HTTP request fails
        """
        if target_date is None:
            target_date = date.today() - timedelta(days=1)

        # Build URL for specific date
        if chart_type == "weekend":
            url = f"{self.WEEKEND_CHART_URL}/{target_date.year}/{target_date.month:02d}/{target_date.day:02d}"
        else:
            url = f"{self.DAILY_CHART_URL}/{target_date.year}/{target_date.month:02d}/{target_date.day:02d}"

        self.logger.info("Fetching box office data", url=url, date=target_date.isoformat())

        try:
            client = await self.get_client()
            response = await client.get(url, headers=self._headers)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            raise FetchError(f"HTTP {e.response.status_code} fetching {url}") from e
        except httpx.RequestError as e:
            raise FetchError(f"Request failed for {url}: {str(e)}") from e

    async def parse(self, raw_data: str) -> list[dict[str, Any]]:
        """Parse box office HTML into structured records.

        Args:
            raw_data: HTML content from The Numbers

        Returns:
            List of parsed box office records

        Raises:
            ParseError: If HTML parsing fails
        """
        try:
            soup = BeautifulSoup(raw_data, "html.parser")
            records = []

            # Find the main data table
            table = soup.find("table", {"id": "box_office_daily_table"})
            if not table:
                # Try alternative table selectors
                table = soup.find("table", class_="data")
                if not table:
                    # Look for any table with movie data
                    tables = soup.find_all("table")
                    for t in tables:
                        if t.find("th", string=re.compile(r"Movie|Title", re.I)):
                            table = t
                            break

            if not table:
                self.logger.warning("No box office table found in HTML")
                return []

            # Extract date from page
            page_date = self._extract_date_from_page(soup)

            # Parse table rows
            rows = table.find_all("tr")[1:]  # Skip header row
            for rank, row in enumerate(rows, start=1):
                cells = row.find_all(["td", "th"])
                if len(cells) < 5:
                    continue

                record = self._parse_row(cells, rank, page_date)
                if record:
                    records.append(record)

            self.logger.info("Parsed box office records", count=len(records))
            return records

        except Exception as e:
            raise ParseError(f"Failed to parse box office HTML: {str(e)}") from e

    def _extract_date_from_page(self, soup: BeautifulSoup) -> date:
        """Extract the data date from the page.

        Args:
            soup: Parsed HTML

        Returns:
            Date from the page or yesterday's date as fallback
        """
        # Try to find date in page title or header
        title = soup.find("title")
        if title:
            # Pattern: "Daily Box Office Chart for Tuesday, January 14, 2025"
            date_match = re.search(
                r"(\w+),\s+(\w+)\s+(\d+),\s+(\d{4})",
                title.text
            )
            if date_match:
                try:
                    date_str = f"{date_match.group(2)} {date_match.group(3)}, {date_match.group(4)}"
                    return datetime.strptime(date_str, "%B %d, %Y").date()
                except ValueError:
                    pass

        # Look for date in h1 or breadcrumb
        for selector in ["h1", ".breadcrumb", ".date-header"]:
            element = soup.select_one(selector)
            if element:
                date_match = re.search(
                    r"(\w+)\s+(\d+),\s+(\d{4})",
                    element.text
                )
                if date_match:
                    try:
                        date_str = f"{date_match.group(1)} {date_match.group(2)}, {date_match.group(3)}"
                        return datetime.strptime(date_str, "%B %d, %Y").date()
                    except ValueError:
                        pass

        # Default to yesterday
        return date.today() - timedelta(days=1)

    def _parse_row(
        self,
        cells: list,
        rank: int,
        page_date: date,
    ) -> Optional[dict[str, Any]]:
        """Parse a single table row into a record.

        Args:
            cells: Table cells from the row
            rank: Row rank (position)
            page_date: Date of the data

        Returns:
            Parsed record dict or None if invalid
        """
        try:
            # Cell indices vary by table format, try common patterns
            # Pattern 1: Rank, Movie, Daily Gross, Change, Theaters, Per Theater, Total Gross, Days
            # Pattern 2: Movie, Distributor, Daily Gross, Theaters, Total Gross, Days

            movie_title = None
            distributor = None
            daily_gross = None
            theater_count = None
            cumulative_gross = None
            days_in_release = 1
            per_theater_avg = None

            for i, cell in enumerate(cells):
                text = cell.get_text(strip=True)

                # Look for movie title (usually a link)
                link = cell.find("a")
                if link and not movie_title:
                    href = link.get("href", "")
                    if "/movie/" in href or not any(x in href for x in ["/person/", "/studio/"]):
                        movie_title = link.get_text(strip=True)
                        # Check for distributor in same cell or next
                        distributor_elem = cell.find("span", class_="distributor")
                        if distributor_elem:
                            distributor = distributor_elem.get_text(strip=True)

                # Look for distributor link
                if link and "/studio/" in link.get("href", ""):
                    distributor = link.get_text(strip=True)

                # Parse monetary values (gross)
                # Order in HTML: daily_gross, per_theater, cumulative_gross
                if "$" in text:
                    value = self._parse_money(text)
                    if value:
                        if daily_gross is None:
                            daily_gross = value
                        elif per_theater_avg is None:
                            # Per theater is typically < $10,000
                            if value < 50000:
                                per_theater_avg = value
                            else:
                                cumulative_gross = value
                        elif cumulative_gross is None:
                            cumulative_gross = value

                # Parse theater count (comma-separated number, no $)
                # Only parse after movie title is found and if we don't have it yet
                if "," in text and "$" not in text and movie_title and theater_count is None:
                    try:
                        count = int(text.replace(",", ""))
                        if 100 < count < 10000:  # Reasonable theater range
                            theater_count = count
                    except ValueError:
                        pass

                # Parse days in release
                if text.isdigit():
                    days = int(text)
                    if 1 <= days < 365:
                        days_in_release = days

            # Validate required fields
            if not movie_title or daily_gross is None:
                return None

            # Set defaults for missing values
            if theater_count is None:
                theater_count = 1
            if cumulative_gross is None:
                cumulative_gross = daily_gross
            if per_theater_avg is None and theater_count > 0:
                per_theater_avg = daily_gross / theater_count

            # Map distributor to ticker
            ticker = get_ticker_for_studio(distributor) if distributor else None

            # Determine if opening weekend (days 1-3, Friday-Sunday)
            is_opening = days_in_release <= 3 and page_date.weekday() in [4, 5, 6]

            return {
                "date": page_date,
                "movie_title": movie_title[:300],  # Truncate to DB field size
                "distributor": distributor or "Unknown",
                "distributor_ticker": ticker,
                "daily_gross": daily_gross,
                "cumulative_gross": cumulative_gross,
                "theater_count": theater_count,
                "per_theater_avg": per_theater_avg,
                "days_in_release": days_in_release,
                "rank": rank,
                "is_opening_weekend": is_opening,
            }

        except Exception as e:
            self.logger.warning("Failed to parse row", error=str(e))
            return None

    def _parse_money(self, text: str) -> Optional[Decimal]:
        """Parse monetary value from text.

        Args:
            text: Text containing dollar amount

        Returns:
            Decimal value or None
        """
        # Remove $ and commas, handle parentheses for negative
        text = text.strip()
        is_negative = "(" in text or "-" in text

        # Extract numbers
        match = re.search(r"[\d,]+(?:\.\d+)?", text.replace(",", ""))
        if match:
            try:
                value = Decimal(match.group().replace(",", ""))
                return -value if is_negative else value
            except Exception:
                pass
        return None

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate box office records.

        Args:
            records: List of parsed records

        Returns:
            List of valid records
        """
        valid_records = []
        for record in records:
            # Validate required fields
            if not record.get("movie_title"):
                self.logger.warning("Skipping record with no movie title")
                continue

            # Validate gross is positive
            if record.get("daily_gross", 0) < 0:
                self.logger.warning(
                    "Skipping record with negative gross",
                    movie=record.get("movie_title")
                )
                continue

            # Validate theater count is positive
            if record.get("theater_count", 0) <= 0:
                self.logger.warning(
                    "Skipping record with invalid theater count",
                    movie=record.get("movie_title")
                )
                continue

            valid_records.append(record)

        return valid_records

    async def store(self, records: list[dict[str, Any]]) -> int:
        """Store box office records to database.

        Args:
            records: List of validated records

        Returns:
            Number of records stored
        """
        if not records:
            return 0

        stored_count = 0
        async with get_async_session() as session:
            for record in records:
                # Use upsert to handle duplicates
                stmt = pg_insert(BoxOfficeDaily).values(
                    date=record["date"],
                    movie_title=record["movie_title"],
                    distributor=record["distributor"],
                    distributor_ticker=record["distributor_ticker"],
                    daily_gross=record["daily_gross"],
                    cumulative_gross=record["cumulative_gross"],
                    theater_count=record["theater_count"],
                    per_theater_avg=record["per_theater_avg"],
                    days_in_release=record["days_in_release"],
                    rank=record["rank"],
                    is_opening_weekend=record["is_opening_weekend"],
                ).on_conflict_do_update(
                    constraint="uq_boxoffice_date_movie",
                    set_={
                        "daily_gross": record["daily_gross"],
                        "cumulative_gross": record["cumulative_gross"],
                        "theater_count": record["theater_count"],
                        "per_theater_avg": record["per_theater_avg"],
                        "rank": record["rank"],
                        "updated_at": datetime.utcnow(),
                    }
                )
                await session.execute(stmt)
                stored_count += 1

            await session.commit()

        self.logger.info("Stored box office records", count=stored_count)
        return stored_count

    async def backfill(
        self,
        start_date: date,
        end_date: date,
        chart_type: str = "daily",
        delay_seconds: float = 1.0,
        **kwargs,
    ) -> list[CollectorResult]:
        """Backfill historical box office data.

        Args:
            start_date: Start date for backfill (minimum 1995-01-01)
            end_date: End date for backfill
            chart_type: 'daily' or 'weekend'
            delay_seconds: Delay between requests to avoid rate limiting

        Returns:
            List of CollectorResult for each date
        """
        import asyncio

        # Enforce minimum start date
        if start_date < self.BACKFILL_START_DATE:
            start_date = self.BACKFILL_START_DATE
            self.logger.warning(
                "Adjusted start date to minimum",
                start_date=start_date.isoformat()
            )

        self.logger.info(
            "Starting box office backfill",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            chart_type=chart_type,
        )

        results = []
        current = start_date

        while current <= end_date:
            result = await self.collect(
                target_date=current,
                chart_type=chart_type,
            )
            results.append(result)

            if not result.success:
                self.logger.warning(
                    "Failed to collect data for date",
                    date=current.isoformat(),
                    error=result.error_message,
                )

            current += timedelta(days=1)

            # Rate limiting delay
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)

        success_count = sum(1 for r in results if r.success)
        self.logger.info(
            "Backfill complete",
            total_days=len(results),
            successful=success_count,
            failed=len(results) - success_count,
        )

        return results

    async def get_latest_date(self) -> Optional[date]:
        """Get the most recent date in the database.

        Returns:
            Latest date with box office data or None
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(BoxOfficeDaily.date)
                .order_by(BoxOfficeDaily.date.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            return row
