"""UK Carbon Intensity API collector.

Data Source: https://carbonintensity.org.uk/
Frequency: 30-minute intervals
Historical: 2018-present
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.collectors.base import BaseCollector, CollectorError, ValidationError
from src.models.database import SessionLocal
from src.models.carbon_intensity import CarbonIntensityReading

logger = logging.getLogger(__name__)


class CarbonIntensityCollector(BaseCollector[Dict, List[Dict]]):
    """Collector for UK Carbon Intensity data.

    Uses the free Carbon Intensity API provided by National Grid ESO.
    """

    SOURCE_NAME = "carbon_intensity"
    DEFAULT_RATE_LIMIT = 2.0  # Generous limits

    BASE_URL = "https://api.carbonintensity.org.uk"

    async def fetch(
        self,
        start_time: datetime = None,
        end_time: datetime = None,
    ) -> Dict:
        """Fetch carbon intensity data.

        Args:
            start_time: Start of time window
            end_time: End of time window

        Returns:
            API response with intensity and generation data
        """
        await self.rate_limiter.wait()

        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(days=1)

        # Format dates for API
        start_str = start_time.strftime("%Y-%m-%dT%H:%MZ")
        end_str = end_time.strftime("%Y-%m-%dT%H:%MZ")

        try:
            # Fetch intensity data
            intensity_url = f"{self.BASE_URL}/intensity/{start_str}/{end_str}"
            intensity_resp = await self.http_client.get(intensity_url)
            intensity_resp.raise_for_status()
            intensity_data = intensity_resp.json()

            # Fetch generation mix data
            generation_url = f"{self.BASE_URL}/generation/{start_str}/{end_str}"
            generation_resp = await self.http_client.get(generation_url)
            generation_resp.raise_for_status()
            generation_data = generation_resp.json()

            return {
                "intensity": intensity_data,
                "generation": generation_data,
                "fetch_time": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to fetch carbon intensity data: {e}")
            raise CollectorError(f"Carbon Intensity fetch failed: {e}")

    def parse(self, raw_data: Dict) -> List[Dict]:
        """Parse carbon intensity data.

        Args:
            raw_data: API response containing intensity and generation data

        Returns:
            List of parsed readings
        """
        records = []

        # Parse intensity data
        intensity_data = raw_data.get("intensity", {}).get("data", [])
        generation_data = raw_data.get("generation", {}).get("data", [])

        # Index generation data by timestamp
        gen_by_time = {}
        for gen in generation_data:
            timestamp = gen.get("from")
            if timestamp:
                gen_by_time[timestamp] = gen.get("generationmix", [])

        for item in intensity_data:
            try:
                timestamp_str = item.get("from")
                if not timestamp_str:
                    continue

                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

                intensity = item.get("intensity", {})
                generation_mix = gen_by_time.get(timestamp_str, [])

                # Parse generation mix into dict and individual columns
                mix_dict = {}
                pct_values = {}
                for fuel in generation_mix:
                    fuel_name = fuel.get("fuel", "").lower().replace(" ", "_")
                    perc = fuel.get("perc", 0)
                    mix_dict[fuel_name] = perc

                    # Map to column names
                    if fuel_name in ["biomass", "coal", "gas", "hydro", "imports", "nuclear", "solar", "wind", "other"]:
                        pct_values[f"pct_{fuel_name}"] = perc

                record = {
                    "timestamp": timestamp,
                    "region": "national",
                    "intensity_forecast": intensity.get("forecast"),
                    "intensity_actual": intensity.get("actual"),
                    "intensity_index": intensity.get("index"),
                    "generation_mix": mix_dict,
                    **pct_values,
                }

                records.append(record)

            except Exception as e:
                logger.warning(f"Failed to parse carbon intensity record: {e}")
                continue

        logger.info(f"Parsed {len(records)} carbon intensity records")
        return records

    async def store_readings(self, records: List[Dict]) -> int:
        """Store carbon intensity readings in database.

        Args:
            records: Parsed readings

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
                    session.query(CarbonIntensityReading)
                    .filter_by(
                        timestamp=record["timestamp"],
                        region=record["region"],
                    )
                    .first()
                )

                if existing:
                    # Update with actual values if available
                    if record.get("intensity_actual") is not None:
                        existing.intensity_actual = record["intensity_actual"]
                    if record.get("generation_mix"):
                        existing.generation_mix = record["generation_mix"]
                else:
                    reading = CarbonIntensityReading(
                        timestamp=record["timestamp"],
                        region=record["region"],
                        intensity_forecast=record.get("intensity_forecast"),
                        intensity_actual=record.get("intensity_actual"),
                        intensity_index=record.get("intensity_index"),
                        generation_mix=record.get("generation_mix"),
                        pct_biomass=record.get("pct_biomass"),
                        pct_coal=record.get("pct_coal"),
                        pct_gas=record.get("pct_gas"),
                        pct_hydro=record.get("pct_hydro"),
                        pct_imports=record.get("pct_imports"),
                        pct_nuclear=record.get("pct_nuclear"),
                        pct_solar=record.get("pct_solar"),
                        pct_wind=record.get("pct_wind"),
                        pct_other=record.get("pct_other"),
                    )
                    session.add(reading)
                    stored_count += 1

            session.commit()
            logger.info(f"Stored {stored_count} new carbon intensity readings")
            return stored_count

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store carbon intensity data: {e}")
            raise
        finally:
            session.close()

    async def run_collection(
        self,
        lookback_hours: int = 24,
    ) -> int:
        """Execute full collection cycle.

        Args:
            lookback_hours: Hours of data to fetch

        Returns:
            Number of new records stored
        """
        logger.info("Starting carbon intensity collection")

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=lookback_hours)

        try:
            # Fetch data
            raw_data = await self.fetch(start_time, end_time)

            # Store raw data
            await self.store_raw(raw_data)

            # Parse records
            records = self.parse(raw_data)

            # Store in database
            stored = await self.store_readings(records)

            logger.info(f"Carbon intensity collection complete: {stored} new records")
            return stored

        finally:
            await self.close()
