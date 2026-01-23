"""Cloudflare Radar API collector for internet traffic and security metrics."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.collectors.base import BaseCollector, CollectorResult, FetchError, ParseError
from src.core.config import settings
from src.core.database import get_async_session
from src.models.data_sources import CloudflareRadarMetrics


class CloudflareRadarCollector(BaseCollector):
    """Collector for Cloudflare Radar API data.

    Fetches global internet traffic, attack trends, and outage data.
    Primary entities: NET, CRWD, PANW, ZS (cybersecurity companies)

    API Documentation: https://developers.cloudflare.com/radar/
    """

    name = "cloudflare_radar"
    source_id = 7  # F-007
    update_frequency = "hourly"

    # Cloudflare Radar API endpoints
    BASE_URL = "https://api.cloudflare.com/client/v4/radar"
    ENDPOINTS = {
        "traffic": "/traffic/top/locations",
        "attacks": "/attacks/layer3/timeseries",
        "outages": "/connection_tampering/timeseries",
    }

    # Primary entities affected by internet/security metrics
    PRIMARY_ENTITIES = ["NET", "CRWD", "PANW", "ZS"]

    # Baseline calculation window (hours)
    BASELINE_WINDOW_HOURS = 168  # 7 days

    def __init__(self):
        super().__init__()
        self._baseline_cache: dict[str, Decimal] = {}

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for Cloudflare API."""
        if not settings.cloudflare_api_token:
            raise FetchError("Cloudflare API token not configured")
        return {
            "Authorization": f"Bearer {settings.cloudflare_api_token}",
            "Content-Type": "application/json",
        }

    async def fetch(self, **kwargs) -> dict[str, Any]:
        """Fetch data from Cloudflare Radar API endpoints.

        Args:
            start_time: Optional start time for data range (defaults to 1 hour ago)
            end_time: Optional end time for data range (defaults to now)
            region: Optional region filter (defaults to "global")

        Returns:
            Dictionary with data from all endpoints

        Raises:
            FetchError: If API request fails
        """
        client = await self.get_client()
        headers = self._get_auth_headers()

        end_time = kwargs.get("end_time", datetime.now(timezone.utc))
        start_time = kwargs.get("start_time", end_time - timedelta(hours=1))
        region = kwargs.get("region", "global")

        params = {
            "dateStart": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "dateEnd": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "format": "json",
        }

        results = {
            "timestamp": end_time,
            "region": region,
            "traffic": None,
            "attacks": None,
            "outages": None,
        }

        # Fetch traffic data
        try:
            traffic_url = f"{self.BASE_URL}{self.ENDPOINTS['traffic']}"
            traffic_params = {**params, "limit": 10}
            response = await client.get(
                traffic_url, headers=headers, params=traffic_params
            )
            response.raise_for_status()
            results["traffic"] = response.json()
            self.logger.debug("Traffic data fetched", status_code=response.status_code)
        except httpx.HTTPStatusError as e:
            self.logger.warning("Traffic endpoint failed", error=str(e))
            results["traffic"] = {"success": False, "error": str(e)}
        except httpx.RequestError as e:
            raise FetchError(f"Traffic request failed: {e}")

        # Fetch attack data (Layer 3 DDoS)
        try:
            attacks_url = f"{self.BASE_URL}{self.ENDPOINTS['attacks']}"
            attacks_params = {**params, "aggInterval": "1h"}
            response = await client.get(
                attacks_url, headers=headers, params=attacks_params
            )
            response.raise_for_status()
            results["attacks"] = response.json()
            self.logger.debug("Attack data fetched", status_code=response.status_code)
        except httpx.HTTPStatusError as e:
            self.logger.warning("Attacks endpoint failed", error=str(e))
            results["attacks"] = {"success": False, "error": str(e)}
        except httpx.RequestError as e:
            raise FetchError(f"Attacks request failed: {e}")

        # Fetch outage data
        try:
            outages_url = f"{self.BASE_URL}{self.ENDPOINTS['outages']}"
            outages_params = {**params, "aggInterval": "1h"}
            response = await client.get(
                outages_url, headers=headers, params=outages_params
            )
            response.raise_for_status()
            results["outages"] = response.json()
            self.logger.debug("Outage data fetched", status_code=response.status_code)
        except httpx.HTTPStatusError as e:
            self.logger.warning("Outages endpoint failed", error=str(e))
            results["outages"] = {"success": False, "error": str(e)}
        except httpx.RequestError as e:
            raise FetchError(f"Outages request failed: {e}")

        return results

    async def _get_baseline(
        self, metric_type: str, region: str, current_time: datetime
    ) -> Optional[Decimal]:
        """Calculate baseline value from historical data.

        Uses rolling average of last 7 days at same hour.
        """
        cache_key = f"{metric_type}:{region}"
        if cache_key in self._baseline_cache:
            return self._baseline_cache[cache_key]

        async with get_async_session() as session:
            # Get data from same hour over past week
            start_time = current_time - timedelta(hours=self.BASELINE_WINDOW_HOURS)
            current_hour = current_time.hour

            stmt = select(CloudflareRadarMetrics.value).where(
                CloudflareRadarMetrics.metric_type == metric_type,
                CloudflareRadarMetrics.region == region,
                CloudflareRadarMetrics.timestamp >= start_time,
                CloudflareRadarMetrics.timestamp < current_time,
            )
            result = await session.execute(stmt)
            values = [row[0] for row in result.fetchall()]

            if not values:
                return None

            baseline = Decimal(str(sum(values) / len(values)))
            self._baseline_cache[cache_key] = baseline
            return baseline

    def _calculate_deviation(
        self, value: Decimal, baseline: Optional[Decimal]
    ) -> Optional[Decimal]:
        """Calculate percentage deviation from baseline."""
        if baseline is None or baseline == 0:
            return None
        return ((value - baseline) / baseline) * 100

    async def parse(self, raw_data: dict[str, Any]) -> list[CloudflareRadarMetrics]:
        """Parse raw API response into CloudflareRadarMetrics records.

        Args:
            raw_data: Dictionary with traffic, attacks, and outages data

        Returns:
            List of CloudflareRadarMetrics records

        Raises:
            ParseError: If data parsing fails
        """
        records = []
        timestamp = raw_data.get("timestamp", datetime.now(timezone.utc))
        region = raw_data.get("region", "global")

        try:
            # Parse traffic data
            traffic_data = raw_data.get("traffic")
            if traffic_data and traffic_data.get("success", True):
                traffic_value = self._extract_traffic_value(traffic_data)
                if traffic_value is not None:
                    baseline = await self._get_baseline("traffic", region, timestamp)
                    deviation = self._calculate_deviation(traffic_value, baseline)
                    records.append(
                        CloudflareRadarMetrics(
                            timestamp=timestamp,
                            metric_type="traffic",
                            region=region,
                            value=traffic_value,
                            baseline_value=baseline,
                            deviation_pct=deviation,
                            metadata={"source": "traffic/top/locations"},
                        )
                    )

            # Parse attack data
            attacks_data = raw_data.get("attacks")
            if attacks_data and attacks_data.get("success", True):
                attack_value = self._extract_attack_value(attacks_data)
                if attack_value is not None:
                    baseline = await self._get_baseline("attacks", region, timestamp)
                    deviation = self._calculate_deviation(attack_value, baseline)
                    records.append(
                        CloudflareRadarMetrics(
                            timestamp=timestamp,
                            metric_type="attacks",
                            region=region,
                            value=attack_value,
                            baseline_value=baseline,
                            deviation_pct=deviation,
                            metadata={"source": "attacks/layer3/timeseries"},
                        )
                    )

            # Parse outage data
            outages_data = raw_data.get("outages")
            if outages_data and outages_data.get("success", True):
                outage_value = self._extract_outage_value(outages_data)
                if outage_value is not None:
                    baseline = await self._get_baseline("outages", region, timestamp)
                    deviation = self._calculate_deviation(outage_value, baseline)
                    records.append(
                        CloudflareRadarMetrics(
                            timestamp=timestamp,
                            metric_type="outages",
                            region=region,
                            value=outage_value,
                            baseline_value=baseline,
                            deviation_pct=deviation,
                            metadata={"source": "connection_tampering/timeseries"},
                        )
                    )

        except (KeyError, TypeError, ValueError) as e:
            raise ParseError(f"Failed to parse Cloudflare data: {e}")

        self.logger.info("Parsed records", count=len(records))
        return records

    def _extract_traffic_value(self, traffic_data: dict) -> Optional[Decimal]:
        """Extract aggregate traffic value from API response."""
        try:
            result = traffic_data.get("result", {})
            # Sum traffic from top locations as aggregate metric
            top_locations = result.get("top_0", [])
            if top_locations:
                total_value = sum(
                    loc.get("value", 0) for loc in top_locations if isinstance(loc, dict)
                )
                return Decimal(str(total_value))

            # Alternative: check for timeseries data
            timeseries = result.get("timeseries", [])
            if timeseries:
                latest = timeseries[-1]
                return Decimal(str(latest.get("value", 0)))
        except (KeyError, TypeError, ValueError):
            pass
        return None

    def _extract_attack_value(self, attacks_data: dict) -> Optional[Decimal]:
        """Extract attack volume from API response."""
        try:
            result = attacks_data.get("result", {})
            timeseries = result.get("timeseries", [])
            if timeseries:
                # Get most recent data point
                latest = timeseries[-1]
                # Use bandwidth or packet count as attack volume metric
                value = latest.get("value", latest.get("bandwidth", 0))
                return Decimal(str(value))

            # Alternative: aggregate data
            summary = result.get("summary", {})
            if summary:
                return Decimal(str(summary.get("total", 0)))
        except (KeyError, TypeError, ValueError):
            pass
        return None

    def _extract_outage_value(self, outages_data: dict) -> Optional[Decimal]:
        """Extract outage count/severity from API response."""
        try:
            result = outages_data.get("result", {})
            timeseries = result.get("timeseries", [])
            if timeseries:
                latest = timeseries[-1]
                return Decimal(str(latest.get("value", 0)))

            # Alternative: summary data
            summary = result.get("summary", {})
            if summary:
                return Decimal(str(summary.get("total", 0)))
        except (KeyError, TypeError, ValueError):
            pass
        return None

    async def store(self, records: list[CloudflareRadarMetrics]) -> int:
        """Store parsed records to database with upsert logic.

        Args:
            records: List of CloudflareRadarMetrics to store

        Returns:
            Number of records stored/updated
        """
        if not records:
            return 0

        async with get_async_session() as session:
            stored_count = 0
            for record in records:
                # Use PostgreSQL upsert (ON CONFLICT)
                stmt = pg_insert(CloudflareRadarMetrics).values(
                    timestamp=record.timestamp,
                    metric_type=record.metric_type,
                    region=record.region,
                    value=record.value,
                    baseline_value=record.baseline_value,
                    deviation_pct=record.deviation_pct,
                    metadata=record.metadata,
                )
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_cloudflare_timestamp_metric_region",
                    set_={
                        "value": stmt.excluded.value,
                        "baseline_value": stmt.excluded.baseline_value,
                        "deviation_pct": stmt.excluded.deviation_pct,
                        "metadata": stmt.excluded.metadata,
                        "updated_at": datetime.now(timezone.utc),
                    },
                )
                await session.execute(stmt)
                stored_count += 1

            await session.commit()
            self.logger.info("Stored records", count=stored_count)
            return stored_count

    async def validate(
        self, records: list[CloudflareRadarMetrics]
    ) -> list[CloudflareRadarMetrics]:
        """Validate records before storing.

        Args:
            records: List of records to validate

        Returns:
            List of valid records
        """
        valid_records = []
        for record in records:
            # Validate required fields
            if not record.timestamp:
                self.logger.warning("Record missing timestamp", record=record)
                continue
            if not record.metric_type:
                self.logger.warning("Record missing metric_type", record=record)
                continue
            if record.value is None:
                self.logger.warning("Record missing value", record=record)
                continue

            # Validate value is non-negative
            if record.value < 0:
                self.logger.warning("Record has negative value", value=record.value)
                continue

            # Validate deviation percentage is reasonable (-1000% to +1000%)
            if record.deviation_pct is not None:
                if record.deviation_pct < -1000 or record.deviation_pct > 1000:
                    self.logger.warning(
                        "Deviation out of range",
                        deviation=record.deviation_pct,
                    )
                    # Keep record but cap deviation
                    record.deviation_pct = max(
                        min(record.deviation_pct, Decimal("1000")), Decimal("-1000")
                    )

            valid_records.append(record)

        return valid_records

    def clear_baseline_cache(self):
        """Clear the baseline cache to force recalculation."""
        self._baseline_cache.clear()
