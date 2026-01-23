"""USGS Earthquake Data Collector.

Collects earthquake event data from the USGS Earthquake Hazards Program API.
API Documentation: https://earthquake.usgs.gov/fdsnws/event/1/
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.collectors.base import BaseCollector, CollectorResult, FetchError, ParseError
from src.core.database import get_async_session
from src.models.data_sources import EarthquakeEvent


class USGSEarthquakeCollector(BaseCollector):
    """Collector for USGS Earthquake event data.

    Fetches earthquake events from the USGS GeoJSON API with configurable
    magnitude thresholds and time windows. Supports both real-time polling
    (every 15 minutes) and historical backfill.

    Attributes:
        name: Collector identifier
        source_id: Database source ID for this collector
        update_frequency: How often to poll for new data
        base_url: USGS API base URL
        min_magnitude: Minimum magnitude threshold (default 4.0)
    """

    name: str = "usgs_earthquake"
    source_id: int = 6  # Assigned source ID for earthquakes
    update_frequency: str = "continuous"  # Poll every 15 minutes

    # USGS API configuration
    BASE_URL: str = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    DEFAULT_MIN_MAGNITUDE: float = 4.0

    def __init__(self, min_magnitude: float = DEFAULT_MIN_MAGNITUDE):
        """Initialize the USGS earthquake collector.

        Args:
            min_magnitude: Minimum magnitude to fetch (default 4.0)
        """
        super().__init__()
        self.min_magnitude = min_magnitude

    async def fetch(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        min_magnitude: Optional[float] = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Fetch earthquake data from USGS API.

        Args:
            start_time: Start of time window (default: 15 minutes ago)
            end_time: End of time window (default: now)
            min_magnitude: Override minimum magnitude threshold

        Returns:
            Raw GeoJSON response from USGS API

        Raises:
            FetchError: If API request fails
        """
        # Default to last 15 minutes for real-time polling
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        if start_time is None:
            start_time = end_time - timedelta(minutes=15)

        magnitude = min_magnitude if min_magnitude is not None else self.min_magnitude

        params = {
            "format": "geojson",
            "starttime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "endtime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "minmagnitude": magnitude,
            "orderby": "time-asc",
        }

        self.logger.info(
            "Fetching earthquake data",
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            min_magnitude=magnitude,
        )

        try:
            client = await self.get_client()
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise FetchError(
                f"USGS API returned {e.response.status_code}: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise FetchError(f"Network error fetching USGS data: {str(e)}")
        except Exception as e:
            raise FetchError(f"Unexpected error fetching USGS data: {str(e)}")

    async def parse(self, raw_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse GeoJSON response into earthquake event records.

        Args:
            raw_data: GeoJSON FeatureCollection from USGS API

        Returns:
            List of parsed earthquake event dictionaries

        Raises:
            ParseError: If data format is invalid
        """
        try:
            if raw_data.get("type") != "FeatureCollection":
                raise ParseError(
                    f"Expected FeatureCollection, got {raw_data.get('type')}"
                )

            features = raw_data.get("features", [])
            records = []

            for feature in features:
                try:
                    record = self._parse_feature(feature)
                    if record:
                        records.append(record)
                except Exception as e:
                    self.logger.warning(
                        "Failed to parse earthquake feature",
                        feature_id=feature.get("id"),
                        error=str(e),
                    )
                    continue

            self.logger.info(
                "Parsed earthquake features",
                total_features=len(features),
                valid_records=len(records),
            )

            return records

        except ParseError:
            raise
        except Exception as e:
            raise ParseError(f"Error parsing USGS GeoJSON: {str(e)}")

    def _parse_feature(self, feature: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Parse a single GeoJSON feature into an earthquake record.

        Args:
            feature: GeoJSON Feature object

        Returns:
            Parsed earthquake record dictionary, or None if invalid
        """
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        coordinates = geometry.get("coordinates", [])

        if len(coordinates) < 3:
            self.logger.warning("Invalid coordinates", feature_id=feature.get("id"))
            return None

        # Extract timestamp (USGS provides milliseconds since epoch)
        timestamp_ms = properties.get("time")
        if timestamp_ms is None:
            return None

        timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

        # Validate magnitude (should be 0-10 scale)
        magnitude = properties.get("mag")
        if magnitude is None or not (0 <= magnitude <= 10):
            self.logger.warning(
                "Invalid magnitude",
                feature_id=feature.get("id"),
                magnitude=magnitude,
            )
            return None

        # Validate coordinates (latitude: -90 to 90, longitude: -180 to 180)
        longitude, latitude, depth = coordinates[0], coordinates[1], coordinates[2]
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            self.logger.warning(
                "Invalid coordinates",
                feature_id=feature.get("id"),
                latitude=latitude,
                longitude=longitude,
            )
            return None

        return {
            "event_id": feature.get("id"),
            "timestamp": timestamp,
            "latitude": Decimal(str(latitude)),
            "longitude": Decimal(str(longitude)),
            "depth_km": Decimal(str(max(0, depth))),  # Depth can be negative in API
            "magnitude": Decimal(str(magnitude)),
            "magnitude_type": properties.get("magType", "unknown"),
            "place_description": properties.get("place", "Unknown location"),
            "felt_reports": properties.get("felt"),
            "tsunami_flag": bool(properties.get("tsunami", 0)),
            "alert_level": properties.get("alert"),
            "estimated_population_exposure": properties.get("sig"),  # Significance score
            "estimated_economic_impact_usd": None,  # Computed by factor
        }

    async def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate parsed earthquake records.

        Args:
            records: List of parsed earthquake records

        Returns:
            List of valid records
        """
        valid_records = []

        for record in records:
            # Required fields
            if not all([
                record.get("event_id"),
                record.get("timestamp"),
                record.get("latitude") is not None,
                record.get("longitude") is not None,
                record.get("magnitude") is not None,
            ]):
                self.logger.warning(
                    "Record missing required fields",
                    event_id=record.get("event_id"),
                )
                continue

            # Magnitude range validation (0-10 scale)
            magnitude = float(record["magnitude"])
            if not (0 <= magnitude <= 10):
                self.logger.warning(
                    "Magnitude out of range",
                    event_id=record.get("event_id"),
                    magnitude=magnitude,
                )
                continue

            # Coordinate validation
            lat = float(record["latitude"])
            lon = float(record["longitude"])
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                self.logger.warning(
                    "Coordinates out of range",
                    event_id=record.get("event_id"),
                    latitude=lat,
                    longitude=lon,
                )
                continue

            valid_records.append(record)

        return valid_records

    async def store(self, records: list[dict[str, Any]]) -> int:
        """Store earthquake events to database.

        Uses upsert to handle duplicate events (by event_id).

        Args:
            records: List of validated earthquake records

        Returns:
            Number of records stored/updated
        """
        if not records:
            return 0

        stored_count = 0

        async with get_async_session() as session:
            for record in records:
                try:
                    # Use PostgreSQL upsert (INSERT ... ON CONFLICT DO UPDATE)
                    stmt = insert(EarthquakeEvent).values(
                        event_id=record["event_id"],
                        timestamp=record["timestamp"],
                        latitude=record["latitude"],
                        longitude=record["longitude"],
                        depth_km=record["depth_km"],
                        magnitude=record["magnitude"],
                        magnitude_type=record["magnitude_type"],
                        place_description=record["place_description"],
                        felt_reports=record["felt_reports"],
                        tsunami_flag=record["tsunami_flag"],
                        alert_level=record["alert_level"],
                        estimated_population_exposure=record["estimated_population_exposure"],
                        estimated_economic_impact_usd=record["estimated_economic_impact_usd"],
                    )

                    stmt = stmt.on_conflict_do_update(
                        index_elements=["event_id"],
                        set_={
                            "felt_reports": stmt.excluded.felt_reports,
                            "alert_level": stmt.excluded.alert_level,
                            "estimated_population_exposure": stmt.excluded.estimated_population_exposure,
                            "updated_at": datetime.utcnow(),
                        },
                    )

                    await session.execute(stmt)
                    stored_count += 1

                except Exception as e:
                    self.logger.error(
                        "Failed to store earthquake event",
                        event_id=record.get("event_id"),
                        error=str(e),
                    )
                    continue

            await session.commit()

        self.logger.info("Stored earthquake events", count=stored_count)
        return stored_count

    async def backfill(
        self,
        start_date: date,
        end_date: date,
        min_magnitude: Optional[float] = None,
        batch_days: int = 7,
        **kwargs,
    ) -> list[CollectorResult]:
        """Backfill historical earthquake data.

        Fetches data in batches to avoid API limits.

        Args:
            start_date: Start date for backfill
            end_date: End date for backfill
            min_magnitude: Override minimum magnitude threshold
            batch_days: Number of days per API request (default 7)

        Returns:
            List of CollectorResult objects for each batch
        """
        self.logger.info(
            "Starting earthquake backfill",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            min_magnitude=min_magnitude or self.min_magnitude,
        )

        results = []
        current_start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_datetime = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

        while current_start < end_datetime:
            current_end = min(
                current_start + timedelta(days=batch_days),
                end_datetime,
            )

            result = await self.collect(
                start_time=current_start,
                end_time=current_end,
                min_magnitude=min_magnitude,
            )
            results.append(result)

            current_start = current_end

            # Brief pause to be respectful to the API
            if current_start < end_datetime:
                import asyncio
                await asyncio.sleep(0.5)

        total_fetched = sum(r.records_fetched for r in results)
        total_stored = sum(r.records_stored for r in results)
        success_rate = sum(1 for r in results if r.success) / len(results) if results else 0

        self.logger.info(
            "Backfill complete",
            total_fetched=total_fetched,
            total_stored=total_stored,
            success_rate=success_rate,
        )

        return results

    async def get_recent_events(
        self,
        hours: int = 24,
        min_magnitude: Optional[float] = None,
    ) -> list[EarthquakeEvent]:
        """Retrieve recent earthquake events from database.

        Args:
            hours: Number of hours to look back
            min_magnitude: Minimum magnitude filter

        Returns:
            List of EarthquakeEvent objects
        """
        async with get_async_session() as session:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

            query = select(EarthquakeEvent).where(
                EarthquakeEvent.timestamp >= cutoff_time
            )

            if min_magnitude is not None:
                query = query.where(EarthquakeEvent.magnitude >= Decimal(str(min_magnitude)))

            query = query.order_by(EarthquakeEvent.timestamp.desc())

            result = await session.execute(query)
            return list(result.scalars().all())
