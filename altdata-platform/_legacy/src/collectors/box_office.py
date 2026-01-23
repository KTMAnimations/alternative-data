"""Movie box office data collector.

Data Source: https://www.the-numbers.com/box-office-chart/daily
Frequency: Daily
Historical: 1995-present
"""

import logging
import re
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector, CollectorError, ValidationError
from src.models.database import SessionLocal
from src.models.box_office import BoxOfficeDaily, STUDIO_TICKER_MAP

logger = logging.getLogger(__name__)


class BoxOfficeCollector(BaseCollector[str, List[Dict]]):
    """Collector for movie box office data.

    Scrapes daily box office data from TheNumbers.
    """

    SOURCE_NAME = "box_office"
    DEFAULT_RATE_LIMIT = 0.5  # Be respectful

    BASE_URL = "https://www.the-numbers.com/box-office-chart/daily"

    async def fetch(
        self,
        target_date: date = None,
    ) -> str:
        """Fetch box office page.

        Args:
            target_date: Date to fetch (default: yesterday)

        Returns:
            HTML content
        """
        await self.rate_limiter.wait()

        if target_date is None:
            target_date = date.today() - timedelta(days=1)

        # TheNumbers URL format: /daily/YYYY/MM/DD
        url = f"{self.BASE_URL}/{target_date.year}/{target_date.month:02d}/{target_date.day:02d}"

        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch box office data: {e}")
            raise CollectorError(f"Box office fetch failed: {e}")

    def parse(self, raw_data: str) -> List[Dict]:
        """Parse box office HTML.

        Args:
            raw_data: HTML content

        Returns:
            List of movie records
        """
        soup = BeautifulSoup(raw_data, "html.parser")
        records = []

        # Find the main data table
        table = soup.find("table", {"id": "box_office_chart"})
        if not table:
            # Try alternative table selector
            table = soup.find("table", class_="chart")

        if not table:
            logger.warning("Could not find box office table")
            return records

        # Parse rows
        rows = table.find_all("tr")[1:]  # Skip header

        # Try to extract date from page
        page_date = self._extract_date(soup) or date.today() - timedelta(days=1)

        for row in rows:
            try:
                record = self._parse_row(row, page_date)
                if record:
                    records.append(record)
            except Exception as e:
                logger.warning(f"Failed to parse box office row: {e}")
                continue

        logger.info(f"Parsed {len(records)} box office records")
        return records

    def _extract_date(self, soup: BeautifulSoup) -> Optional[date]:
        """Extract date from page."""
        # Look for date in title or header
        title = soup.find("title")
        if title:
            text = title.get_text()
            match = re.search(r"(\w+ \d+, \d+)", text)
            if match:
                try:
                    return datetime.strptime(match.group(1), "%B %d, %Y").date()
                except ValueError:
                    pass
        return None

    def _parse_row(self, row, page_date: date) -> Optional[Dict]:
        """Parse a single table row."""
        cells = row.find_all("td")
        if len(cells) < 5:
            return None

        # Common cell order: Rank, Movie, Daily Gross, %Change, Theaters, Total Gross, Days
        try:
            rank_text = cells[0].get_text(strip=True)
            rank = int(re.sub(r"[^\d]", "", rank_text)) if rank_text else None

            movie_cell = cells[1]
            movie_title = movie_cell.get_text(strip=True)

            daily_gross = self._parse_currency(cells[2].get_text(strip=True))
            theater_count = self._parse_number(cells[4].get_text(strip=True)) if len(cells) > 4 else None
            total_gross = self._parse_currency(cells[5].get_text(strip=True)) if len(cells) > 5 else None
            days_text = cells[6].get_text(strip=True) if len(cells) > 6 else None
            days_in_release = self._parse_number(days_text) if days_text else None

            # Map distributor to ticker
            distributor = self._extract_distributor(movie_cell, movie_title)
            ticker = self._map_distributor_to_ticker(distributor)

            # Calculate per-theater average
            per_theater = None
            if daily_gross and theater_count and theater_count > 0:
                per_theater = daily_gross / theater_count

            record = {
                "date": page_date,
                "movie_title": movie_title,
                "distributor": distributor,
                "distributor_ticker": ticker,
                "daily_gross": daily_gross,
                "cumulative_gross": total_gross,
                "theater_count": theater_count,
                "per_theater_avg": per_theater,
                "days_in_release": days_in_release,
                "daily_rank": rank,
                "is_new_release": "Yes" if days_in_release and days_in_release <= 3 else "No",
            }

            return record

        except Exception as e:
            logger.debug(f"Row parse error: {e}")
            return None

    def _extract_distributor(self, cell, title: str) -> Optional[str]:
        """Extract distributor from cell or title."""
        # Look for distributor in link or text
        link = cell.find("a")
        if link:
            href = link.get("href", "")
            if "movie-distributor" in href:
                return link.get_text(strip=True)

        # Try to match from known distributors
        for studio in STUDIO_TICKER_MAP.keys():
            if studio.lower() in title.lower():
                return studio

        return None

    def _map_distributor_to_ticker(self, distributor: Optional[str]) -> Optional[str]:
        """Map distributor name to ticker."""
        if not distributor:
            return None

        # Direct match
        if distributor in STUDIO_TICKER_MAP:
            return STUDIO_TICKER_MAP[distributor]

        # Partial match
        distributor_lower = distributor.lower()
        for studio, ticker in STUDIO_TICKER_MAP.items():
            if studio.lower() in distributor_lower or distributor_lower in studio.lower():
                return ticker

        return None

    def _parse_currency(self, text: str) -> Optional[float]:
        """Parse currency value from text."""
        if not text:
            return None
        clean = re.sub(r"[$,\s]", "", text)
        try:
            return float(clean)
        except ValueError:
            return None

    def _parse_number(self, text: str) -> Optional[int]:
        """Parse integer from text."""
        if not text:
            return None
        clean = re.sub(r"[,\s]", "", text)
        try:
            return int(clean)
        except ValueError:
            return None

    async def store_records(self, records: List[Dict]) -> int:
        """Store box office records in database.

        Args:
            records: Parsed records

        Returns:
            Number of records stored
        """
        if not records:
            return 0

        session = SessionLocal()
        stored_count = 0

        try:
            for record in records:
                existing = (
                    session.query(BoxOfficeDaily)
                    .filter_by(
                        date=record["date"],
                        movie_title=record["movie_title"],
                    )
                    .first()
                )

                if existing:
                    # Update with latest values
                    for key, value in record.items():
                        if hasattr(existing, key) and value is not None:
                            setattr(existing, key, value)
                else:
                    box_office = BoxOfficeDaily(**record)
                    session.add(box_office)
                    stored_count += 1

            session.commit()
            logger.info(f"Stored {stored_count} new box office records")
            return stored_count

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store box office data: {e}")
            raise
        finally:
            session.close()

    async def run_collection(
        self,
        target_date: date = None,
    ) -> int:
        """Execute full collection cycle.

        Args:
            target_date: Date to collect (default: yesterday)

        Returns:
            Number of new records stored
        """
        logger.info("Starting box office collection")

        if target_date is None:
            target_date = date.today() - timedelta(days=1)

        try:
            # Fetch data
            raw_data = await self.fetch(target_date)

            # Store raw data
            await self.store_raw(raw_data)

            # Parse records
            records = self.parse(raw_data)

            # Store in database
            stored = await self.store_records(records)

            logger.info(f"Box office collection complete: {stored} new records")
            return stored

        finally:
            await self.close()
