"""OpenTable seated diners collector using Playwright for JS-rendered content."""

import asyncio
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

import structlog
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout
from sqlalchemy import select
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.collectors.base import BaseCollector, CollectorResult, FetchError, ParseError
from src.core.config import settings
from src.core.database import get_async_session
from src.models.data_sources import OpenTableMetrics

logger = structlog.get_logger()


# OpenTable data URL (public state of the industry page)
OPENTABLE_URL = "https://www.opentable.com/state-of-industry"

# Expected regions from OpenTable data
EXPECTED_REGIONS = ["US", "UK", "Germany", "Australia", "Canada"]

# Primary entities affected by restaurant dining data
PRIMARY_ENTITIES = ["DRI", "MCD", "SBUX", "CMG", "YUM"]


class OpenTableCollector(BaseCollector):
    """Collector for OpenTable seated diners data.

    OpenTable publishes weekly YoY seated diners percentages by region.
    Data is typically updated on Tuesdays for the previous week.
    """

    name: str = "opentable"
    source_id: int = 2  # Assigned source ID for OpenTable
    update_frequency: str = "weekly"

    def __init__(self):
        super().__init__()
        self._browser: Optional[Browser] = None
        self._playwright = None

    async def _get_browser(self) -> Browser:
        """Get or create Playwright browser instance."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ]
            )
        return self._browser

    async def close(self):
        """Close browser and HTTP client."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        await super().close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=30),
        retry=retry_if_exception_type((PlaywrightTimeout, FetchError)),
    )
    async def fetch(self, **kwargs) -> dict[str, Any]:
        """Fetch OpenTable state of industry data using Playwright.

        Args:
            **kwargs: Optional arguments including:
                - date: Target date for data (defaults to latest)

        Returns:
            Dictionary containing raw page content and extracted data

        Raises:
            FetchError: If page cannot be loaded or data not found
        """
        browser = await self._get_browser()
        page: Page = await browser.new_page()

        try:
            # Set realistic viewport and user agent
            await page.set_viewport_size({"width": 1920, "height": 1080})
            await page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
            })

            self.logger.info("Navigating to OpenTable state of industry page")

            # Navigate with extended timeout for JS-heavy page
            await page.goto(
                OPENTABLE_URL,
                wait_until="networkidle",
                timeout=60000,
            )

            # Wait for content to render
            await page.wait_for_timeout(3000)

            # Wait for data elements to be present
            try:
                await page.wait_for_selector(
                    "[data-region], .region-data, table, .chart-data",
                    timeout=30000,
                )
            except PlaywrightTimeout:
                self.logger.warning("Primary selectors not found, attempting fallback")

            # Get page content
            html_content = await page.content()

            # Try to extract structured data from the page
            # OpenTable may use different data structures, try multiple approaches
            data = await self._extract_data_from_page(page)

            return {
                "html_content": html_content,
                "extracted_data": data,
                "fetch_timestamp": datetime.utcnow().isoformat(),
                "url": OPENTABLE_URL,
            }

        except PlaywrightTimeout as e:
            self.logger.error("Page load timeout", error=str(e))
            raise FetchError(f"Page load timeout: {str(e)}")
        except Exception as e:
            self.logger.error("Failed to fetch OpenTable data", error=str(e))
            raise FetchError(f"Failed to fetch data: {str(e)}")
        finally:
            await page.close()

    async def _extract_data_from_page(self, page: Page) -> dict[str, Any]:
        """Extract structured data from the page using JavaScript evaluation.

        Args:
            page: Playwright page object

        Returns:
            Dictionary containing extracted region data
        """
        # Try to extract data via JavaScript evaluation
        try:
            data = await page.evaluate("""
                () => {
                    const result = {regions: [], weekEnding: null};

                    // Look for data in various DOM structures
                    // Method 1: Look for region-specific elements
                    const regionElements = document.querySelectorAll(
                        '[data-region], [class*="region"], [class*="country"]'
                    );

                    // Method 2: Look for table data
                    const tables = document.querySelectorAll('table');
                    tables.forEach(table => {
                        const rows = table.querySelectorAll('tr');
                        rows.forEach(row => {
                            const cells = row.querySelectorAll('td, th');
                            if (cells.length >= 2) {
                                const text = Array.from(cells).map(c => c.textContent.trim());
                                result.tableData = result.tableData || [];
                                result.tableData.push(text);
                            }
                        });
                    });

                    // Method 3: Look for chart data or JSON embedded in scripts
                    const scripts = document.querySelectorAll('script');
                    scripts.forEach(script => {
                        const content = script.textContent;
                        if (content && content.includes('seatedDiners')) {
                            result.hasScriptData = true;
                        }
                    });

                    // Extract text content that might contain percentages
                    const allText = document.body.innerText;
                    const percentMatches = allText.match(/-?\d+\.?\d*%/g);
                    result.percentages = percentMatches || [];

                    return result;
                }
            """)
            return data
        except Exception as e:
            self.logger.warning("JavaScript evaluation failed", error=str(e))
            return {}

    async def parse(self, raw_data: Any) -> list[dict]:
        """Parse raw OpenTable data into structured records.

        Args:
            raw_data: Dictionary containing HTML content and extracted data

        Returns:
            List of dictionaries with parsed OpenTable metrics

        Raises:
            ParseError: If data cannot be parsed
        """
        try:
            html_content = raw_data.get("html_content", "")
            extracted_data = raw_data.get("extracted_data", {})

            records = []

            # Parse week ending date from page content
            week_ending = self._extract_week_ending(html_content)

            # Parse regional data
            regional_data = self._parse_regional_data(html_content, extracted_data)

            for region, yoy_pct in regional_data.items():
                if region in EXPECTED_REGIONS:
                    records.append({
                        "week_ending": week_ending,
                        "region": region,
                        "city": None,  # National/regional level, not city-specific
                        "yoy_seated_diners_pct": yoy_pct,
                        "wow_change_pct": None,  # Will be calculated during storage
                        "data_quality_score": Decimal("1.0"),
                    })

            if not records:
                # If we couldn't parse real data, raise an error
                raise ParseError("No regional data could be parsed from page")

            self.logger.info(
                "Parsed OpenTable data",
                record_count=len(records),
                week_ending=week_ending,
            )

            return records

        except ParseError:
            raise
        except Exception as e:
            self.logger.error("Failed to parse OpenTable data", error=str(e))
            raise ParseError(f"Failed to parse data: {str(e)}")

    def _extract_week_ending(self, html_content: str) -> date:
        """Extract week ending date from HTML content.

        Args:
            html_content: Raw HTML string

        Returns:
            Date object for week ending
        """
        # Look for date patterns in the content
        date_patterns = [
            r"week\s+ending\s+(\w+\s+\d{1,2},?\s+\d{4})",
            r"as\s+of\s+(\w+\s+\d{1,2},?\s+\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{4})",
            r"(\d{4}-\d{2}-\d{2})",
        ]

        for pattern in date_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                try:
                    # Try various date formats
                    for fmt in ["%B %d, %Y", "%B %d %Y", "%m/%d/%Y", "%Y-%m-%d"]:
                        try:
                            return datetime.strptime(date_str.replace(",", ""), fmt).date()
                        except ValueError:
                            continue
                except Exception:
                    continue

        # Default to previous Tuesday if no date found
        today = date.today()
        days_since_tuesday = (today.weekday() - 1) % 7
        return today - timedelta(days=days_since_tuesday)

    def _parse_regional_data(
        self,
        html_content: str,
        extracted_data: dict,
    ) -> dict[str, Decimal]:
        """Parse regional YoY percentages from content.

        Args:
            html_content: Raw HTML string
            extracted_data: Data extracted via JavaScript

        Returns:
            Dictionary mapping region names to YoY percentages
        """
        regional_data = {}

        # Try to find region-specific data in the HTML
        for region in EXPECTED_REGIONS:
            # Look for patterns like "US: -15%" or "United States -15%"
            patterns = [
                rf"{region}[:\s]+(-?\d+\.?\d*)%",
                rf"{region}[:\s]+(-?\d+\.?\d*)\s*percent",
            ]

            # Add country name variations
            region_variations = {
                "US": ["United States", "USA", "U.S."],
                "UK": ["United Kingdom", "Great Britain", "Britain"],
                "Germany": ["Deutschland", "DE"],
                "Australia": ["AU", "AUS"],
                "Canada": ["CA", "CAN"],
            }

            for variation in region_variations.get(region, []):
                patterns.append(rf"{variation}[:\s]+(-?\d+\.?\d*)%")

            for pattern in patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    try:
                        regional_data[region] = Decimal(match.group(1))
                        break
                    except Exception:
                        continue

        return regional_data

    async def validate(self, records: list[dict]) -> list[dict]:
        """Validate parsed records.

        Args:
            records: List of parsed record dictionaries

        Returns:
            List of valid records

        Validates:
            - YoY percentage is in reasonable range (-100% to +200%)
            - All expected regions are present
            - Week ending date is valid
        """
        valid_records = []
        regions_found = set()

        for record in records:
            yoy_pct = record.get("yoy_seated_diners_pct")
            region = record.get("region")
            week_ending = record.get("week_ending")

            # Validate YoY range
            if yoy_pct is None or yoy_pct < Decimal("-100") or yoy_pct > Decimal("200"):
                self.logger.warning(
                    "Invalid YoY percentage",
                    region=region,
                    yoy_pct=yoy_pct,
                )
                continue

            # Validate week ending date
            if week_ending is None or week_ending > date.today():
                self.logger.warning(
                    "Invalid week ending date",
                    region=region,
                    week_ending=week_ending,
                )
                continue

            valid_records.append(record)
            regions_found.add(region)

        # Warn if not all expected regions are present
        missing_regions = set(EXPECTED_REGIONS) - regions_found
        if missing_regions:
            self.logger.warning(
                "Missing regions in data",
                missing=list(missing_regions),
                found=list(regions_found),
            )

        return valid_records

    async def store(self, records: list[dict]) -> int:
        """Store validated records to the database.

        Args:
            records: List of validated record dictionaries

        Returns:
            Number of records successfully stored
        """
        if not records:
            return 0

        stored_count = 0

        async with get_async_session() as session:
            for record in records:
                try:
                    # Check if record already exists
                    existing = await session.execute(
                        select(OpenTableMetrics).where(
                            OpenTableMetrics.week_ending == record["week_ending"],
                            OpenTableMetrics.region == record["region"],
                            OpenTableMetrics.city == record.get("city"),
                        )
                    )
                    existing_record = existing.scalar_one_or_none()

                    # Calculate WoW change if prior week exists
                    wow_change = await self._calculate_wow_change(
                        session,
                        record["week_ending"],
                        record["region"],
                        record["yoy_seated_diners_pct"],
                    )
                    record["wow_change_pct"] = wow_change

                    if existing_record:
                        # Update existing record
                        for key, value in record.items():
                            setattr(existing_record, key, value)
                        self.logger.debug(
                            "Updated existing record",
                            region=record["region"],
                            week_ending=record["week_ending"],
                        )
                    else:
                        # Create new record
                        metrics = OpenTableMetrics(**record)
                        session.add(metrics)
                        self.logger.debug(
                            "Created new record",
                            region=record["region"],
                            week_ending=record["week_ending"],
                        )

                    stored_count += 1

                except Exception as e:
                    self.logger.error(
                        "Failed to store record",
                        region=record.get("region"),
                        error=str(e),
                    )

        return stored_count

    async def _calculate_wow_change(
        self,
        session,
        week_ending: date,
        region: str,
        current_yoy: Decimal,
    ) -> Optional[Decimal]:
        """Calculate week-over-week change in YoY percentage.

        Args:
            session: Database session
            week_ending: Current week ending date
            region: Region name
            current_yoy: Current YoY percentage

        Returns:
            WoW change percentage or None if prior week not available
        """
        prior_week = week_ending - timedelta(days=7)

        result = await session.execute(
            select(OpenTableMetrics.yoy_seated_diners_pct).where(
                OpenTableMetrics.week_ending == prior_week,
                OpenTableMetrics.region == region,
                OpenTableMetrics.city.is_(None),
            )
        )
        prior_yoy = result.scalar_one_or_none()

        if prior_yoy is not None:
            return current_yoy - prior_yoy

        return None

    async def backfill(
        self,
        start_date: date,
        end_date: date,
        **kwargs,
    ) -> list[CollectorResult]:
        """Backfill historical OpenTable data.

        OpenTable published state of industry data starting from 2020.
        This method handles weekly data collection.

        Args:
            start_date: Start date for backfill (should be a Tuesday)
            end_date: End date for backfill

        Returns:
            List of CollectorResult objects for each week
        """
        self.logger.info(
            "Starting OpenTable backfill",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        results = []
        current = start_date

        # Ensure we start on a Tuesday
        while current.weekday() != 1:  # Tuesday = 1
            current += timedelta(days=1)

        while current <= end_date:
            self.logger.info("Backfilling week", week_ending=current.isoformat())

            result = await self.collect(target_date=current)
            results.append(result)

            # Move to next Tuesday
            current += timedelta(days=7)

            # Rate limiting between requests
            await asyncio.sleep(2)

        self.logger.info(
            "Backfill complete",
            weeks_processed=len(results),
            successful=sum(1 for r in results if r.success),
        )

        return results


# Convenience function for scheduled collection
async def collect_opentable_data() -> CollectorResult:
    """Convenience function to collect latest OpenTable data.

    Returns:
        CollectorResult with collection status and data
    """
    collector = OpenTableCollector()
    try:
        return await collector.collect()
    finally:
        await collector.close()
