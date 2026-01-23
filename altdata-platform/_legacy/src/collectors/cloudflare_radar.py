"""Cloudflare Radar API collector.

Data Source: https://developers.cloudflare.com/radar/
Frequency: Near real-time
Historical: 2020-present
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.collectors.base import BaseCollector, CollectorError, ValidationError
from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.cloudflare_radar import CloudflareRadarMetrics

logger = logging.getLogger(__name__)


class CloudflareRadarCollector(BaseCollector[Dict, List[Dict]]):
    """Collector for Cloudflare Radar data.

    Fetches internet traffic and security metrics from Cloudflare Radar API.
    """

    SOURCE_NAME = "cloudflare_radar"
    DEFAULT_RATE_LIMIT = 1.0

    BASE_URL = "https://api.cloudflare.com/client/v4/radar"

    def __init__(self, api_token: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_token = api_token or getattr(settings, 'cloudflare_api_token', None)

    async def fetch(
        self,
        start_time: datetime = None,
        end_time: datetime = None,
        location: str = None,
    ) -> Dict:
        """Fetch Cloudflare Radar data.

        Args:
            start_time: Start of time window
            end_time: End of time window
            location: Country code (optional)

        Returns:
            API response with traffic and attack data
        """
        await self.rate_limiter.wait()

        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(hours=24)

        headers = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        all_data = {}

        # Fetch traffic timeseries
        try:
            traffic_params = {
                "dateStart": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "dateEnd": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "format": "json",
            }
            if location:
                traffic_params["location"] = location

            traffic_url = f"{self.BASE_URL}/http/timeseries"
            traffic_resp = await self.http_client.get(
                traffic_url,
                params=traffic_params,
                headers=headers,
            )

            if traffic_resp.status_code == 200:
                all_data["traffic"] = traffic_resp.json()
            else:
                logger.warning(f"Traffic fetch failed: {traffic_resp.status_code}")
                all_data["traffic"] = {}

        except Exception as e:
            logger.warning(f"Failed to fetch traffic data: {e}")
            all_data["traffic"] = {}

        # Fetch attack timeseries
        try:
            attack_url = f"{self.BASE_URL}/attacks/layer7/timeseries"
            attack_resp = await self.http_client.get(
                attack_url,
                params=traffic_params,
                headers=headers,
            )

            if attack_resp.status_code == 200:
                all_data["attacks"] = attack_resp.json()
            else:
                all_data["attacks"] = {}

        except Exception as e:
            logger.warning(f"Failed to fetch attack data: {e}")
            all_data["attacks"] = {}

        all_data["fetch_time"] = datetime.utcnow().isoformat()
        return all_data

    def parse(self, raw_data: Dict) -> List[Dict]:
        """Parse Cloudflare Radar data.

        Args:
            raw_data: API response

        Returns:
            List of parsed metrics
        """
        records = []

        # Parse traffic data
        traffic_data = raw_data.get("traffic", {}).get("result", {})
        traffic_series = traffic_data.get("serie_0", {})

        timestamps = traffic_series.get("timestamps", [])
        values = traffic_series.get("values", [])

        for i, ts in enumerate(timestamps):
            try:
                timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                value = values[i] if i < len(values) else None

                record = {
                    "timestamp": timestamp,
                    "region_type": "global",
                    "region_code": "GLOBAL",
                    "traffic_index": float(value) * 100 if value else None,  # Normalize to 100 baseline
                }

                records.append(record)

            except Exception as e:
                logger.debug(f"Failed to parse traffic point: {e}")
                continue

        # Parse attack data
        attack_data = raw_data.get("attacks", {}).get("result", {})
        attack_series = attack_data.get("serie_0", {})

        attack_timestamps = attack_series.get("timestamps", [])
        attack_values = attack_series.get("values", [])

        # Merge attack data with traffic data by timestamp
        attack_by_time = {}
        for i, ts in enumerate(attack_timestamps):
            if i < len(attack_values):
                attack_by_time[ts] = attack_values[i]

        # Update records with attack data
        for record in records:
            ts_str = record["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ")
            if ts_str in attack_by_time:
                record["attack_volume_index"] = float(attack_by_time[ts_str]) * 100

        logger.info(f"Parsed {len(records)} Cloudflare Radar records")
        return records

    async def store_metrics(self, records: List[Dict]) -> int:
        """Store Cloudflare metrics in database.

        Args:
            records: Parsed metrics

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
                    session.query(CloudflareRadarMetrics)
                    .filter_by(
                        timestamp=record["timestamp"],
                        region_type=record["region_type"],
                        region_code=record["region_code"],
                    )
                    .first()
                )

                if existing:
                    for key, value in record.items():
                        if hasattr(existing, key) and value is not None:
                            setattr(existing, key, value)
                else:
                    metric = CloudflareRadarMetrics(**record)
                    session.add(metric)
                    stored_count += 1

            session.commit()
            logger.info(f"Stored {stored_count} new Cloudflare Radar records")
            return stored_count

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store Cloudflare data: {e}")
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
        logger.info("Starting Cloudflare Radar collection")

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
            stored = await self.store_metrics(records)

            logger.info(f"Cloudflare Radar collection complete: {stored} new records")
            return stored

        finally:
            await self.close()
