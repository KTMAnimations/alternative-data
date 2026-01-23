"""OpenTable reservation data collector.

Data Source: https://www.opentable.com/c/state-of-industry/
Frequency: Weekly (updates each Monday)
Historical: 2020-present
Note: JavaScript-rendered page requires Playwright
"""

import asyncio
import logging
import re
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

from src.collectors.base import BaseCollector, CollectorError, ValidationError
from src.models.database import SessionLocal
from src.models.opentable import OpenTableMetrics

logger = logging.getLogger(__name__)


# Major regions tracked by OpenTable
MAJOR_REGIONS = ["US", "UK", "Germany", "Australia", "Canada", "Ireland", "Mexico"]


class OpenTableCollector(BaseCollector[Dict, List[Dict]]):
    """Collector for OpenTable seated diners data.

    Scrapes weekly reservation comparison data from OpenTable's
    State of Industry dashboard. Requires Playwright for JS rendering.
    """

    SOURCE_NAME = "opentable"
    DEFAULT_RATE_LIMIT = 0.2  # Be respectful

    OPENTABLE_URL = "https://www.opentable.com/c/state-of-industry/"

    async def fetch(self) -> Dict:
        """Fetch OpenTable State of Industry page.

        Uses Playwright to render JavaScript content.
        """
        await self.rate_limiter.wait()

        try:
            # Try to use Playwright for JS rendering
            return await self._fetch_with_playwright()
        except ImportError:
            logger.warning("Playwright not available, attempting static fetch")
            return await self._fetch_static()
        except Exception as e:
            logger.error(f"Playwright fetch failed: {e}")
            raise CollectorError(f"OpenTable fetch failed: {e}")

    async def _fetch_with_playwright(self) -> Dict:
        """Fetch using Playwright for JS-rendered content."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError("Playwright is required for OpenTable scraping")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(self.OPENTABLE_URL, wait_until="networkidle")

                # Wait for data to load
                await page.wait_for_timeout(3000)

                # Extract page content and any embedded data
                html_content = await page.content()

                # Try to extract data from page scripts or API calls
                # OpenTable typically embeds data in JSON or data attributes
                data = {
                    "html": html_content,
                    "fetch_time": datetime.utcnow().isoformat(),
                }

                return data
            finally:
                await browser.close()

    async def _fetch_static(self) -> Dict:
        """Fallback static fetch without JS rendering."""
        response = await self.http_client.get(self.OPENTABLE_URL)
        response.raise_for_status()
        return {
            "html": response.text,
            "fetch_time": datetime.utcnow().isoformat(),
        }

    def parse(self, raw_data: Dict) -> List[Dict]:
        """Parse OpenTable data from fetched content.

        OpenTable presents data as YoY comparison percentages.
        Format varies, so we try multiple parsing strategies.
        """
        html_content = raw_data.get("html", "")

        records = []

        # Try to extract embedded JSON data
        json_records = self._extract_json_data(html_content)
        if json_records:
            records.extend(json_records)

        # Try HTML table parsing
        table_records = self._extract_table_data(html_content)
        if table_records:
            records.extend(table_records)

        # Deduplicate
        seen = set()
        unique_records = []
        for record in records:
            key = (record.get("week_ending"), record.get("region"), record.get("city"))
            if key not in seen:
                seen.add(key)
                unique_records.append(record)

        logger.info(f"Parsed {len(unique_records)} OpenTable records")
        return unique_records

    def _extract_json_data(self, html: str) -> List[Dict]:
        """Extract data from embedded JSON in page."""
        records = []

        # Look for JSON data embedded in script tags
        import json

        json_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'data-state="([^"]+)"',
            r'"seatedDiners":\s*(\[.*?\])',
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    parsed = self._parse_json_structure(data)
                    records.extend(parsed)
                except json.JSONDecodeError:
                    continue

        return records

    def _parse_json_structure(self, data: Any) -> List[Dict]:
        """Parse various JSON structures that OpenTable might use."""
        records = []

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    record = self._extract_record_from_dict(item)
                    if record:
                        records.append(record)
        elif isinstance(data, dict):
            # Look for nested data
            for key in ["data", "metrics", "regions", "seatedDiners"]:
                if key in data:
                    nested = self._parse_json_structure(data[key])
                    records.extend(nested)

        return records

    def _extract_record_from_dict(self, item: Dict) -> Optional[Dict]:
        """Extract a record from a dict item."""
        # Try to identify date and value fields
        week_ending = None
        region = None
        yoy_pct = None

        # Date field detection
        for date_key in ["date", "week_ending", "weekEnding", "period"]:
            if date_key in item:
                week_ending = self._parse_date(item[date_key])
                break

        # Region detection
        for region_key in ["region", "country", "market", "location"]:
            if region_key in item:
                region = str(item[region_key])
                break

        # YoY percentage detection
        for pct_key in ["yoy", "yoyPct", "change", "seatedDiners", "pctChange"]:
            if pct_key in item:
                try:
                    yoy_pct = float(item[pct_key])
                    break
                except (ValueError, TypeError):
                    continue

        if week_ending and region and yoy_pct is not None:
            return {
                "week_ending": week_ending,
                "region": region,
                "city": item.get("city"),
                "yoy_seated_diners_pct": yoy_pct,
            }

        return None

    def _extract_table_data(self, html: str) -> List[Dict]:
        """Extract data from HTML tables."""
        from bs4 import BeautifulSoup

        records = []
        soup = BeautifulSoup(html, "html.parser")

        # Find tables that might contain the data
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            headers = []

            for row in rows:
                cells = row.find_all(["th", "td"])
                if not cells:
                    continue

                # First row might be headers
                if not headers and row.find("th"):
                    headers = [c.get_text(strip=True).lower() for c in cells]
                    continue

                if len(cells) >= 2:
                    # Try to parse as date/value pairs
                    date_text = cells[0].get_text(strip=True)
                    value_text = cells[1].get_text(strip=True)

                    parsed_date = self._parse_date(date_text)
                    parsed_value = self._parse_percentage(value_text)

                    if parsed_date and parsed_value is not None:
                        records.append({
                            "week_ending": parsed_date,
                            "region": "US",  # Default if not specified
                            "city": None,
                            "yoy_seated_diners_pct": parsed_value,
                        })

        return records

    def _parse_date(self, date_text: Any) -> Optional[date]:
        """Parse date from various formats."""
        if isinstance(date_text, date):
            return date_text
        if isinstance(date_text, datetime):
            return date_text.date()
        if not isinstance(date_text, str):
            return None

        formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%m/%d/%y",
            "%B %d, %Y",
            "%b %d, %Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_text, fmt).date()
            except ValueError:
                continue

        return None

    def _parse_percentage(self, text: str) -> Optional[float]:
        """Parse percentage value from text."""
        if not text:
            return None

        # Remove percentage sign and whitespace
        clean = re.sub(r"[%\s]", "", text)

        # Handle +/- prefix
        try:
            return float(clean)
        except ValueError:
            return None

    async def store_metrics(self, records: List[Dict]) -> int:
        """Store OpenTable metrics in database.

        Args:
            records: Parsed metric records

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
                    session.query(OpenTableMetrics)
                    .filter_by(
                        week_ending=record["week_ending"],
                        region=record["region"],
                        city=record.get("city"),
                    )
                    .first()
                )

                if existing:
                    existing.yoy_seated_diners_pct = record["yoy_seated_diners_pct"]
                else:
                    metric = OpenTableMetrics(
                        week_ending=record["week_ending"],
                        region=record["region"],
                        city=record.get("city"),
                        yoy_seated_diners_pct=record["yoy_seated_diners_pct"],
                    )
                    session.add(metric)
                    stored_count += 1

            session.commit()
            logger.info(f"Stored {stored_count} new OpenTable records")
            return stored_count

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store OpenTable data: {e}")
            raise
        finally:
            session.close()

    async def run_collection(self) -> int:
        """Execute full collection cycle.

        Returns:
            Number of new records stored
        """
        logger.info("Starting OpenTable collection")

        try:
            # Fetch data
            raw_data = await self.fetch()

            # Store raw data
            await self.store_raw(raw_data)

            # Parse records
            records = self.parse(raw_data)

            # Validate
            self._validate_records(records)

            # Store in database
            stored = await self.store_metrics(records)

            logger.info(f"OpenTable collection complete: {stored} new records")
            return stored

        finally:
            await self.close()

    def _validate_records(self, records: List[Dict]) -> None:
        """Validate parsed records."""
        if not records:
            logger.warning("No records parsed from OpenTable data")
            return

        for record in records:
            yoy = record.get("yoy_seated_diners_pct")
            if yoy is not None:
                # YoY should be reasonable (between -100% and +200%)
                if yoy < -100 or yoy > 200:
                    logger.warning(
                        f"Unusual YoY value {yoy} for {record.get('region')} "
                        f"on {record.get('week_ending')}"
                    )
