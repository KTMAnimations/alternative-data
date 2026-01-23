"""Zillow rental data collector.

Data Source: https://www.zillow.com/research/data/
Frequency: Monthly
Historical: 2015-present
"""

import csv
import io
import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from src.collectors.base import BaseCollector, CollectorError, ValidationError
from src.models.database import SessionLocal
from src.models.zillow_rental import ZillowRentalIndex

logger = logging.getLogger(__name__)


# Zillow data download URLs
ZILLOW_DATA_URLS = {
    "zori_all_homes": "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv",
    "zori_sfr": "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfr_sm_month.csv",
}


class ZillowRentalCollector(BaseCollector[Dict, List[Dict]]):
    """Collector for Zillow rental index data.

    Downloads public CSV files from Zillow Research.
    """

    SOURCE_NAME = "zillow_rental"
    DEFAULT_RATE_LIMIT = 0.5  # Be respectful

    async def fetch(
        self,
        dataset: str = "zori_all_homes",
    ) -> Dict:
        """Fetch Zillow rental data CSV.

        Args:
            dataset: Which dataset to fetch

        Returns:
            Dict with CSV content and metadata
        """
        await self.rate_limiter.wait()

        url = ZILLOW_DATA_URLS.get(dataset)
        if not url:
            raise CollectorError(f"Unknown Zillow dataset: {dataset}")

        try:
            response = await self.http_client.get(url)
            response.raise_for_status()

            return {
                "csv_content": response.text,
                "dataset": dataset,
                "fetch_time": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to fetch Zillow data: {e}")
            raise CollectorError(f"Zillow fetch failed: {e}")

    def parse(self, raw_data: Dict) -> List[Dict]:
        """Parse Zillow CSV data.

        Args:
            raw_data: Dict containing CSV content

        Returns:
            List of parsed records
        """
        csv_content = raw_data.get("csv_content", "")
        dataset = raw_data.get("dataset", "zori_all_homes")
        records = []

        # Determine property type from dataset
        property_type = "all_homes" if "all_homes" in dataset else "sfr"

        reader = csv.DictReader(io.StringIO(csv_content))

        for row in reader:
            try:
                # Extract region info
                region_id = row.get("RegionID")
                region_name = row.get("RegionName")
                state_code = row.get("StateName")
                region_type = row.get("RegionType", "metro")

                # Parse date columns (format: YYYY-MM-DD)
                date_columns = [col for col in row.keys() if self._is_date_column(col)]

                for date_col in date_columns:
                    value = row.get(date_col)
                    if not value or value == "":
                        continue

                    try:
                        zori_value = float(value)
                        period = datetime.strptime(date_col, "%Y-%m-%d").date()

                        record = {
                            "period": period,
                            "region_type": region_type.lower() if region_type else "metro",
                            "region_id": region_id,
                            "region_name": region_name,
                            "state_code": state_code,
                            "property_type": property_type,
                            "zori_value": zori_value,
                        }

                        records.append(record)

                    except (ValueError, TypeError) as e:
                        continue

            except Exception as e:
                logger.warning(f"Failed to parse Zillow row: {e}")
                continue

        # Calculate MoM and YoY changes
        records = self._calculate_changes(records)

        logger.info(f"Parsed {len(records)} Zillow rental records")
        return records

    def _is_date_column(self, col: str) -> bool:
        """Check if column name is a date."""
        try:
            datetime.strptime(col, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def _calculate_changes(self, records: List[Dict]) -> List[Dict]:
        """Calculate MoM and YoY changes for records."""
        # Group by region and property type
        by_region = {}
        for record in records:
            key = (record["region_id"], record["property_type"])
            if key not in by_region:
                by_region[key] = []
            by_region[key].append(record)

        # Sort each group by date and calculate changes
        for key, region_records in by_region.items():
            region_records.sort(key=lambda x: x["period"])

            for i, record in enumerate(region_records):
                # MoM change
                if i > 0:
                    prev = region_records[i - 1]
                    if prev["zori_value"] and prev["zori_value"] > 0:
                        record["mom_change"] = (
                            (record["zori_value"] - prev["zori_value"]) / prev["zori_value"]
                        ) * 100

                # YoY change (12 months back)
                if i >= 12:
                    prev_year = region_records[i - 12]
                    if prev_year["zori_value"] and prev_year["zori_value"] > 0:
                        record["yoy_change"] = (
                            (record["zori_value"] - prev_year["zori_value"]) / prev_year["zori_value"]
                        ) * 100

        return records

    async def store_records(self, records: List[Dict]) -> int:
        """Store Zillow records in database.

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
                    session.query(ZillowRentalIndex)
                    .filter_by(
                        period=record["period"],
                        region_id=record["region_id"],
                        property_type=record["property_type"],
                    )
                    .first()
                )

                if existing:
                    for key, value in record.items():
                        if hasattr(existing, key) and value is not None:
                            setattr(existing, key, value)
                else:
                    zillow_record = ZillowRentalIndex(**record)
                    session.add(zillow_record)
                    stored_count += 1

            session.commit()
            logger.info(f"Stored {stored_count} new Zillow rental records")
            return stored_count

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store Zillow data: {e}")
            raise
        finally:
            session.close()

    async def run_collection(
        self,
        datasets: List[str] = None,
    ) -> int:
        """Execute full collection cycle.

        Args:
            datasets: List of datasets to fetch

        Returns:
            Number of new records stored
        """
        logger.info("Starting Zillow rental collection")

        if datasets is None:
            datasets = list(ZILLOW_DATA_URLS.keys())

        total_stored = 0

        try:
            for dataset in datasets:
                # Fetch data
                raw_data = await self.fetch(dataset)

                # Store raw data
                await self.store_raw(raw_data)

                # Parse records
                records = self.parse(raw_data)

                # Store in database
                stored = await self.store_records(records)
                total_stored += stored

            logger.info(f"Zillow rental collection complete: {total_stored} new records")
            return total_stored

        finally:
            await self.close()
