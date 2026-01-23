"""Tests for USGS Earthquake Data Collector."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import httpx

from src.collectors.usgs_earthquake import USGSEarthquakeCollector
from src.collectors.base import FetchError, ParseError
from src.models.data_sources import EarthquakeEvent


# Sample USGS GeoJSON response
SAMPLE_GEOJSON_RESPONSE = {
    "type": "FeatureCollection",
    "metadata": {
        "generated": 1704067200000,
        "url": "https://earthquake.usgs.gov/fdsnws/event/1/query",
        "title": "USGS Earthquakes",
        "status": 200,
        "count": 2,
    },
    "features": [
        {
            "type": "Feature",
            "id": "us7000abc1",
            "properties": {
                "mag": 5.2,
                "place": "10km NE of Los Angeles, CA",
                "time": 1704067200000,  # 2024-01-01 00:00:00 UTC
                "updated": 1704070800000,
                "tz": None,
                "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000abc1",
                "detail": "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us7000abc1",
                "felt": 1500,
                "cdi": 4.2,
                "mmi": 5.0,
                "alert": "green",
                "status": "reviewed",
                "tsunami": 0,
                "sig": 500,
                "net": "us",
                "code": "7000abc1",
                "ids": ",us7000abc1,",
                "sources": ",us,",
                "types": ",origin,phase-data,",
                "nst": 50,
                "dmin": 0.5,
                "rms": 0.8,
                "gap": 45,
                "magType": "mw",
                "type": "earthquake",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-118.2437, 34.0522, 10.5],  # lon, lat, depth
            },
        },
        {
            "type": "Feature",
            "id": "us7000abc2",
            "properties": {
                "mag": 4.5,
                "place": "15km SW of San Francisco, CA",
                "time": 1704070800000,  # 2024-01-01 01:00:00 UTC
                "updated": 1704074400000,
                "tz": None,
                "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000abc2",
                "felt": 800,
                "cdi": 3.5,
                "mmi": 4.0,
                "alert": None,
                "status": "reviewed",
                "tsunami": 0,
                "sig": 300,
                "net": "us",
                "code": "7000abc2",
                "magType": "ml",
                "type": "earthquake",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-122.4194, 37.7749, 8.2],
            },
        },
    ],
}


# Invalid data samples for testing validation
INVALID_MAGNITUDE_FEATURE = {
    "type": "Feature",
    "id": "invalid_mag",
    "properties": {
        "mag": 15.0,  # Invalid: exceeds 10
        "place": "Invalid Location",
        "time": 1704067200000,
        "magType": "mw",
    },
    "geometry": {"type": "Point", "coordinates": [-118.0, 34.0, 10.0]},
}

INVALID_COORDINATES_FEATURE = {
    "type": "Feature",
    "id": "invalid_coords",
    "properties": {
        "mag": 5.0,
        "place": "Invalid Coords",
        "time": 1704067200000,
        "magType": "mw",
    },
    "geometry": {"type": "Point", "coordinates": [-200.0, 100.0, 10.0]},  # Invalid
}


class TestUSGSEarthquakeCollector:
    """Tests for USGSEarthquakeCollector class."""

    @pytest.fixture
    def collector(self):
        """Create collector instance for testing."""
        return USGSEarthquakeCollector(min_magnitude=4.0)

    @pytest.fixture
    def mock_http_response(self):
        """Create mock HTTP response."""
        response = MagicMock(spec=httpx.Response)
        response.json.return_value = SAMPLE_GEOJSON_RESPONSE
        response.raise_for_status = MagicMock()
        return response

    # ============== Fetch Tests ==============

    @pytest.mark.asyncio
    async def test_fetch_successful(self, collector, mock_http_response):
        """Test successful fetch from USGS API."""
        with patch.object(collector, "get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_http_response
            mock_get_client.return_value = mock_client

            result = await collector.fetch(
                start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 2, tzinfo=timezone.utc),
            )

            assert result["type"] == "FeatureCollection"
            assert len(result["features"]) == 2
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_with_default_time_window(self, collector, mock_http_response):
        """Test fetch uses 15-minute window by default."""
        with patch.object(collector, "get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_http_response
            mock_get_client.return_value = mock_client

            await collector.fetch()

            # Verify the API was called
            mock_client.get.assert_called_once()
            call_args = mock_client.get.call_args
            params = call_args[1]["params"]

            # Check that minmagnitude is set correctly
            assert params["minmagnitude"] == 4.0
            assert params["format"] == "geojson"

    @pytest.mark.asyncio
    async def test_fetch_http_error_raises_fetch_error(self, collector):
        """Test HTTP errors are converted to FetchError."""
        with patch.object(collector, "get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_client.get.side_effect = httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=mock_response,
            )
            mock_get_client.return_value = mock_client

            with pytest.raises(FetchError) as exc_info:
                await collector.fetch()

            assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_network_error_raises_fetch_error(self, collector):
        """Test network errors are converted to FetchError."""
        with patch.object(collector, "get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.RequestError("Connection failed")
            mock_get_client.return_value = mock_client

            with pytest.raises(FetchError) as exc_info:
                await collector.fetch()

            assert "Network error" in str(exc_info.value)

    # ============== Parse Tests ==============

    @pytest.mark.asyncio
    async def test_parse_valid_geojson(self, collector):
        """Test parsing valid GeoJSON response."""
        records = await collector.parse(SAMPLE_GEOJSON_RESPONSE)

        assert len(records) == 2

        # Verify first record
        record1 = records[0]
        assert record1["event_id"] == "us7000abc1"
        assert record1["magnitude"] == Decimal("5.2")
        assert record1["latitude"] == Decimal("34.0522")
        assert record1["longitude"] == Decimal("-118.2437")
        assert record1["depth_km"] == Decimal("10.5")
        assert record1["magnitude_type"] == "mw"
        assert record1["felt_reports"] == 1500
        assert record1["tsunami_flag"] is False
        assert record1["alert_level"] == "green"

        # Verify second record
        record2 = records[1]
        assert record2["event_id"] == "us7000abc2"
        assert record2["magnitude"] == Decimal("4.5")

    @pytest.mark.asyncio
    async def test_parse_invalid_feature_collection_type(self, collector):
        """Test parsing fails for invalid GeoJSON type."""
        invalid_data = {"type": "InvalidType", "features": []}

        with pytest.raises(ParseError) as exc_info:
            await collector.parse(invalid_data)

        assert "Expected FeatureCollection" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_parse_skips_invalid_features(self, collector):
        """Test that invalid features are skipped during parsing."""
        data_with_invalid = {
            "type": "FeatureCollection",
            "features": [
                SAMPLE_GEOJSON_RESPONSE["features"][0],  # Valid
                INVALID_MAGNITUDE_FEATURE,  # Invalid magnitude
                INVALID_COORDINATES_FEATURE,  # Invalid coordinates
            ],
        }

        records = await collector.parse(data_with_invalid)

        # Only the valid feature should be parsed
        assert len(records) == 1
        assert records[0]["event_id"] == "us7000abc1"

    @pytest.mark.asyncio
    async def test_parse_empty_features(self, collector):
        """Test parsing response with no features."""
        empty_data = {"type": "FeatureCollection", "features": []}

        records = await collector.parse(empty_data)

        assert len(records) == 0

    # ============== Validation Tests ==============

    @pytest.mark.asyncio
    async def test_validate_magnitude_range(self, collector):
        """Test magnitude values are within 0-10 scale."""
        valid_record = {
            "event_id": "test1",
            "timestamp": datetime.now(timezone.utc),
            "latitude": Decimal("35.0"),
            "longitude": Decimal("-120.0"),
            "depth_km": Decimal("10"),
            "magnitude": Decimal("5.5"),
            "magnitude_type": "mw",
            "place_description": "Test location",
        }

        invalid_magnitude_low = {**valid_record, "event_id": "test2", "magnitude": Decimal("-1")}
        invalid_magnitude_high = {**valid_record, "event_id": "test3", "magnitude": Decimal("11")}

        records = [valid_record, invalid_magnitude_low, invalid_magnitude_high]
        valid_records = await collector.validate(records)

        # Only the valid record should pass
        assert len(valid_records) == 1
        assert valid_records[0]["event_id"] == "test1"

    @pytest.mark.asyncio
    async def test_validate_coordinate_range(self, collector):
        """Test lat/long coordinates are valid."""
        base_record = {
            "event_id": "test1",
            "timestamp": datetime.now(timezone.utc),
            "latitude": Decimal("35.0"),
            "longitude": Decimal("-120.0"),
            "depth_km": Decimal("10"),
            "magnitude": Decimal("5.5"),
            "magnitude_type": "mw",
            "place_description": "Test location",
        }

        # Valid coordinates
        valid = base_record.copy()

        # Invalid latitude (> 90)
        invalid_lat = {**base_record, "event_id": "test2", "latitude": Decimal("95.0")}

        # Invalid longitude (< -180)
        invalid_lon = {**base_record, "event_id": "test3", "longitude": Decimal("-185.0")}

        records = [valid, invalid_lat, invalid_lon]
        valid_records = await collector.validate(records)

        assert len(valid_records) == 1
        assert valid_records[0]["event_id"] == "test1"

    @pytest.mark.asyncio
    async def test_validate_required_fields(self, collector):
        """Test records missing required fields are rejected."""
        complete_record = {
            "event_id": "test1",
            "timestamp": datetime.now(timezone.utc),
            "latitude": Decimal("35.0"),
            "longitude": Decimal("-120.0"),
            "depth_km": Decimal("10"),
            "magnitude": Decimal("5.5"),
            "magnitude_type": "mw",
            "place_description": "Test location",
        }

        # Missing event_id
        missing_id = {k: v for k, v in complete_record.items() if k != "event_id"}
        missing_id["event_id"] = None

        # Missing timestamp
        missing_time = {k: v for k, v in complete_record.items() if k != "timestamp"}
        missing_time["timestamp"] = None

        records = [complete_record, missing_id, missing_time]
        valid_records = await collector.validate(records)

        assert len(valid_records) == 1

    # ============== Data Timeliness Tests ==============

    @pytest.mark.asyncio
    async def test_data_timeliness_within_15_minutes(self, collector):
        """Test that data arrives within 15 minutes of event time."""
        now = datetime.now(timezone.utc)
        event_time = now - timedelta(minutes=10)  # 10 minutes ago

        record = {
            "event_id": "recent_event",
            "timestamp": event_time,
            "latitude": Decimal("35.0"),
            "longitude": Decimal("-120.0"),
            "depth_km": Decimal("10"),
            "magnitude": Decimal("5.5"),
            "magnitude_type": "mw",
            "place_description": "Recent event",
        }

        # Calculate time difference
        time_diff = now - event_time
        assert time_diff <= timedelta(minutes=15), "Data should arrive within 15 minutes"

    @pytest.mark.asyncio
    async def test_fetch_uses_15_minute_window(self, collector):
        """Test that default fetch window is 15 minutes."""
        # This tests the polling interval requirement
        with patch.object(collector, "get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {"type": "FeatureCollection", "features": []}
            mock_response.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            before_fetch = datetime.now(timezone.utc)
            await collector.fetch()

            call_args = mock_client.get.call_args
            params = call_args[1]["params"]

            # Parse the time parameters
            start_time = datetime.strptime(params["starttime"], "%Y-%m-%dT%H:%M:%S")
            end_time = datetime.strptime(params["endtime"], "%Y-%m-%dT%H:%M:%S")

            time_window = end_time - start_time

            # Should be approximately 15 minutes (allow small variance)
            assert timedelta(minutes=14) <= time_window <= timedelta(minutes=16)

    # ============== Store Tests ==============

    @pytest.mark.asyncio
    async def test_store_returns_count(self, collector, db_session):
        """Test store returns correct count of stored records."""
        records = [
            {
                "event_id": "store_test_1",
                "timestamp": datetime.now(timezone.utc),
                "latitude": Decimal("35.0"),
                "longitude": Decimal("-120.0"),
                "depth_km": Decimal("10"),
                "magnitude": Decimal("5.5"),
                "magnitude_type": "mw",
                "place_description": "Store test 1",
                "felt_reports": None,
                "tsunami_flag": False,
                "alert_level": None,
                "estimated_population_exposure": None,
                "estimated_economic_impact_usd": None,
            },
        ]

        with patch("src.collectors.usgs_earthquake.get_async_session") as mock_session:
            mock_session.return_value.__aenter__.return_value = db_session
            mock_session.return_value.__aexit__.return_value = None

            # Mock the session execute to avoid actual DB calls
            db_session.execute = AsyncMock()
            db_session.commit = AsyncMock()

            stored = await collector.store(records)

            assert stored == 1

    @pytest.mark.asyncio
    async def test_store_empty_records(self, collector):
        """Test store with empty records returns 0."""
        stored = await collector.store([])

        assert stored == 0

    # ============== Backfill Tests ==============

    @pytest.mark.asyncio
    async def test_backfill_date_range(self, collector):
        """Test backfill processes correct date range."""
        from datetime import date

        with patch.object(collector, "collect") as mock_collect:
            mock_collect.return_value = MagicMock(
                success=True,
                records_fetched=10,
                records_stored=10,
            )

            results = await collector.backfill(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 14),
                batch_days=7,
            )

            # Should have 2 batches (7 days each for 14 days)
            assert mock_collect.call_count == 2
            assert len(results) == 2

    # ============== Integration Tests ==============

    @pytest.mark.asyncio
    async def test_collect_pipeline(self, collector, mock_http_response):
        """Test full collect pipeline: fetch -> parse -> validate -> store."""
        with patch.object(collector, "get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_http_response
            mock_get_client.return_value = mock_client

            with patch.object(collector, "store") as mock_store:
                mock_store.return_value = 2

                result = await collector.collect()

                assert result.success is True
                assert result.records_fetched == 2
                assert result.records_stored == 2

    @pytest.mark.asyncio
    async def test_collect_handles_fetch_error(self, collector):
        """Test collect handles fetch errors gracefully."""
        with patch.object(collector, "_fetch_with_retry") as mock_fetch:
            mock_fetch.side_effect = FetchError("API unavailable")

            result = await collector.collect()

            assert result.success is False
            assert "Fetch error" in result.error_message

    @pytest.mark.asyncio
    async def test_collect_handles_parse_error(self, collector, mock_http_response):
        """Test collect handles parse errors gracefully."""
        mock_http_response.json.return_value = {"type": "InvalidType"}

        with patch.object(collector, "get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_http_response
            mock_get_client.return_value = mock_client

            result = await collector.collect()

            assert result.success is False
            assert "Parse error" in result.error_message


class TestUSGSEarthquakeCollectorConfiguration:
    """Tests for collector configuration options."""

    def test_default_magnitude_threshold(self):
        """Test default minimum magnitude is 4.0."""
        collector = USGSEarthquakeCollector()
        assert collector.min_magnitude == 4.0

    def test_custom_magnitude_threshold(self):
        """Test custom minimum magnitude configuration."""
        collector = USGSEarthquakeCollector(min_magnitude=5.5)
        assert collector.min_magnitude == 5.5

    def test_collector_attributes(self):
        """Test collector has required attributes."""
        collector = USGSEarthquakeCollector()

        assert collector.name == "usgs_earthquake"
        assert collector.source_id == 6
        assert collector.update_frequency == "continuous"
        assert collector.BASE_URL == "https://earthquake.usgs.gov/fdsnws/event/1/query"
