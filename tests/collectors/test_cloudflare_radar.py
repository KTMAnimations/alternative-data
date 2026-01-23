"""Tests for Cloudflare Radar API collector."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio

from src.collectors.cloudflare_radar import CloudflareRadarCollector
from src.collectors.base import FetchError, ParseError
from src.models.data_sources import CloudflareRadarMetrics


@pytest.fixture
def collector():
    """Create a CloudflareRadarCollector instance."""
    return CloudflareRadarCollector()


@pytest.fixture
def mock_traffic_response():
    """Mock traffic API response."""
    return {
        "success": True,
        "result": {
            "top_0": [
                {"location": "US", "value": 1000000},
                {"location": "GB", "value": 500000},
                {"location": "DE", "value": 400000},
            ]
        }
    }


@pytest.fixture
def mock_attacks_response():
    """Mock attacks API response."""
    return {
        "success": True,
        "result": {
            "timeseries": [
                {"timestamp": "2024-01-15T10:00:00Z", "value": 5000},
                {"timestamp": "2024-01-15T11:00:00Z", "value": 7500},
            ]
        }
    }


@pytest.fixture
def mock_outages_response():
    """Mock outages API response."""
    return {
        "success": True,
        "result": {
            "timeseries": [
                {"timestamp": "2024-01-15T10:00:00Z", "value": 15},
                {"timestamp": "2024-01-15T11:00:00Z", "value": 12},
            ]
        }
    }


class TestCloudflareRadarCollector:
    """Tests for CloudflareRadarCollector class."""

    def test_collector_attributes(self, collector):
        """Test collector has required attributes."""
        assert collector.name == "cloudflare_radar"
        assert collector.source_id == 7
        assert collector.update_frequency == "hourly"
        assert collector.PRIMARY_ENTITIES == ["NET", "CRWD", "PANW", "ZS"]

    def test_baseline_window_configuration(self, collector):
        """Test baseline window is 7 days (168 hours)."""
        assert collector.BASELINE_WINDOW_HOURS == 168

    @pytest.mark.asyncio
    async def test_get_auth_headers_with_token(self, collector):
        """Test auth headers are generated correctly with API token."""
        with patch("src.collectors.cloudflare_radar.settings") as mock_settings:
            mock_settings.cloudflare_api_token = "test-token-12345"
            headers = collector._get_auth_headers()

            assert headers["Authorization"] == "Bearer test-token-12345"
            assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_get_auth_headers_without_token_raises(self, collector):
        """Test FetchError is raised when API token is not configured."""
        with patch("src.collectors.cloudflare_radar.settings") as mock_settings:
            mock_settings.cloudflare_api_token = None

            with pytest.raises(FetchError, match="Cloudflare API token not configured"):
                collector._get_auth_headers()

    @pytest.mark.asyncio
    async def test_fetch_all_endpoints(
        self,
        collector,
        mock_traffic_response,
        mock_attacks_response,
        mock_outages_response,
    ):
        """Test fetching data from all endpoints."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200

        # Setup responses for each endpoint
        def create_response(data):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = data
            resp.raise_for_status = MagicMock()
            return resp

        mock_client.get = AsyncMock(
            side_effect=[
                create_response(mock_traffic_response),
                create_response(mock_attacks_response),
                create_response(mock_outages_response),
            ]
        )

        with patch("src.collectors.cloudflare_radar.settings") as mock_settings:
            mock_settings.cloudflare_api_token = "test-token"
            collector._client = mock_client

            result = await collector.fetch()

            assert result["traffic"] == mock_traffic_response
            assert result["attacks"] == mock_attacks_response
            assert result["outages"] == mock_outages_response
            assert "timestamp" in result
            assert result["region"] == "global"

    @pytest.mark.asyncio
    async def test_fetch_hourly_data_collection(self, collector):
        """Test that fetch requests hourly data (default 1 hour window)."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "result": {}}
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("src.collectors.cloudflare_radar.settings") as mock_settings:
            mock_settings.cloudflare_api_token = "test-token"
            collector._client = mock_client

            end_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
            await collector.fetch(end_time=end_time)

            # Verify the time window is 1 hour
            call_args = mock_client.get.call_args_list[0]
            params = call_args[1]["params"]
            assert "dateStart" in params
            assert "dateEnd" in params

            # Parse the dates
            start = datetime.strptime(params["dateStart"], "%Y-%m-%dT%H:%M:%SZ")
            end = datetime.strptime(params["dateEnd"], "%Y-%m-%dT%H:%M:%SZ")
            assert (end - start).total_seconds() == 3600  # 1 hour

    @pytest.mark.asyncio
    async def test_fetch_handles_endpoint_failure(self, collector):
        """Test that fetch handles individual endpoint failures gracefully."""
        mock_client = AsyncMock()

        def create_response(data, should_fail=False):
            resp = MagicMock()
            resp.status_code = 200 if not should_fail else 500
            resp.json.return_value = data
            if should_fail:
                resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "Server error", request=MagicMock(), response=resp
                )
            else:
                resp.raise_for_status = MagicMock()
            return resp

        # First endpoint succeeds, second fails, third succeeds
        mock_client.get = AsyncMock(
            side_effect=[
                create_response({"success": True, "result": {}}),
                create_response({}, should_fail=True),
                create_response({"success": True, "result": {}}),
            ]
        )

        with patch("src.collectors.cloudflare_radar.settings") as mock_settings:
            mock_settings.cloudflare_api_token = "test-token"
            collector._client = mock_client

            result = await collector.fetch()

            # Should not raise, but attacks should contain error
            assert result["traffic"]["success"] is True
            assert result["attacks"]["success"] is False
            assert result["outages"]["success"] is True

    @pytest.mark.asyncio
    async def test_parse_traffic_data(self, collector, mock_traffic_response):
        """Test parsing traffic data extracts correct value."""
        raw_data = {
            "timestamp": datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            "region": "global",
            "traffic": mock_traffic_response,
            "attacks": None,
            "outages": None,
        }

        with patch.object(collector, "_get_baseline", return_value=Decimal("1500000")):
            records = await collector.parse(raw_data)

            assert len(records) == 1
            record = records[0]
            assert record.metric_type == "traffic"
            assert record.value == Decimal("1900000")  # 1000000 + 500000 + 400000
            assert record.baseline_value == Decimal("1500000")
            # Deviation: (1900000 - 1500000) / 1500000 * 100 = 26.67%
            assert record.deviation_pct is not None

    @pytest.mark.asyncio
    async def test_parse_attacks_data(self, collector, mock_attacks_response):
        """Test parsing attack data extracts latest value."""
        raw_data = {
            "timestamp": datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            "region": "global",
            "traffic": None,
            "attacks": mock_attacks_response,
            "outages": None,
        }

        with patch.object(collector, "_get_baseline", return_value=Decimal("5000")):
            records = await collector.parse(raw_data)

            assert len(records) == 1
            record = records[0]
            assert record.metric_type == "attacks"
            assert record.value == Decimal("7500")  # Latest timeseries value

    @pytest.mark.asyncio
    async def test_parse_all_metrics(
        self,
        collector,
        mock_traffic_response,
        mock_attacks_response,
        mock_outages_response,
    ):
        """Test parsing all metric types together."""
        raw_data = {
            "timestamp": datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            "region": "global",
            "traffic": mock_traffic_response,
            "attacks": mock_attacks_response,
            "outages": mock_outages_response,
        }

        with patch.object(collector, "_get_baseline", return_value=Decimal("1000")):
            records = await collector.parse(raw_data)

            assert len(records) == 3
            metric_types = {r.metric_type for r in records}
            assert metric_types == {"traffic", "attacks", "outages"}

    def test_calculate_deviation_positive(self, collector):
        """Test positive deviation calculation."""
        value = Decimal("120")
        baseline = Decimal("100")
        deviation = collector._calculate_deviation(value, baseline)
        assert deviation == Decimal("20")  # 20% above baseline

    def test_calculate_deviation_negative(self, collector):
        """Test negative deviation calculation."""
        value = Decimal("80")
        baseline = Decimal("100")
        deviation = collector._calculate_deviation(value, baseline)
        assert deviation == Decimal("-20")  # 20% below baseline

    def test_calculate_deviation_no_baseline(self, collector):
        """Test deviation calculation with no baseline returns None."""
        value = Decimal("100")
        assert collector._calculate_deviation(value, None) is None
        assert collector._calculate_deviation(value, Decimal("0")) is None

    @pytest.mark.asyncio
    async def test_validate_filters_invalid_records(self, collector):
        """Test validation filters out invalid records."""
        valid_record = CloudflareRadarMetrics(
            timestamp=datetime.now(timezone.utc),
            metric_type="traffic",
            region="global",
            value=Decimal("1000"),
        )
        invalid_record_no_timestamp = CloudflareRadarMetrics(
            timestamp=None,
            metric_type="traffic",
            region="global",
            value=Decimal("1000"),
        )
        invalid_record_negative_value = CloudflareRadarMetrics(
            timestamp=datetime.now(timezone.utc),
            metric_type="traffic",
            region="global",
            value=Decimal("-100"),
        )

        records = [valid_record, invalid_record_no_timestamp, invalid_record_negative_value]
        valid_records = await collector.validate(records)

        assert len(valid_records) == 1
        assert valid_records[0] == valid_record

    @pytest.mark.asyncio
    async def test_validate_caps_extreme_deviations(self, collector):
        """Test validation caps extreme deviation values."""
        record = CloudflareRadarMetrics(
            timestamp=datetime.now(timezone.utc),
            metric_type="traffic",
            region="global",
            value=Decimal("1000"),
            deviation_pct=Decimal("5000"),  # Extremely high
        )

        valid_records = await collector.validate([record])

        assert len(valid_records) == 1
        # Should be capped at 1000%
        assert valid_records[0].deviation_pct == Decimal("1000")

    @pytest.mark.asyncio
    async def test_store_records(self, collector, db_session):
        """Test storing records to database."""
        records = [
            CloudflareRadarMetrics(
                timestamp=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
                metric_type="traffic",
                region="global",
                value=Decimal("1000000"),
                baseline_value=Decimal("900000"),
                deviation_pct=Decimal("11.11"),
                metadata={"source": "test"},
            ),
            CloudflareRadarMetrics(
                timestamp=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
                metric_type="attacks",
                region="global",
                value=Decimal("5000"),
                baseline_value=Decimal("4000"),
                deviation_pct=Decimal("25.00"),
                metadata={"source": "test"},
            ),
        ]

        # Mock the database session
        with patch("src.collectors.cloudflare_radar.get_async_session") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.execute = AsyncMock()
            mock_session_instance.commit = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            stored_count = await collector.store(records)

            assert stored_count == 2

    def test_clear_baseline_cache(self, collector):
        """Test clearing baseline cache."""
        collector._baseline_cache["traffic:global"] = Decimal("1000")
        collector._baseline_cache["attacks:global"] = Decimal("500")

        collector.clear_baseline_cache()

        assert len(collector._baseline_cache) == 0


class TestCloudflareRadarEndpoints:
    """Tests for specific API endpoint handling."""

    def test_endpoints_configuration(self, collector):
        """Test all required endpoints are configured."""
        assert "traffic" in collector.ENDPOINTS
        assert "attacks" in collector.ENDPOINTS
        assert "outages" in collector.ENDPOINTS

    def test_base_url_is_correct(self, collector):
        """Test base URL is Cloudflare Radar API."""
        assert "api.cloudflare.com/client/v4/radar" in collector.BASE_URL


class TestCloudflareRadarDataExtraction:
    """Tests for data extraction methods."""

    def test_extract_traffic_value_from_top_locations(self, collector):
        """Test extracting traffic from top locations data."""
        data = {
            "result": {
                "top_0": [
                    {"location": "US", "value": 1000},
                    {"location": "GB", "value": 500},
                ]
            }
        }
        value = collector._extract_traffic_value(data)
        assert value == Decimal("1500")

    def test_extract_traffic_value_from_timeseries(self, collector):
        """Test extracting traffic from timeseries data."""
        data = {
            "result": {
                "timeseries": [
                    {"timestamp": "2024-01-15T10:00:00Z", "value": 800},
                    {"timestamp": "2024-01-15T11:00:00Z", "value": 1000},
                ]
            }
        }
        value = collector._extract_traffic_value(data)
        assert value == Decimal("1000")  # Latest value

    def test_extract_attack_value_from_timeseries(self, collector):
        """Test extracting attack volume from timeseries."""
        data = {
            "result": {
                "timeseries": [
                    {"timestamp": "2024-01-15T10:00:00Z", "value": 5000},
                    {"timestamp": "2024-01-15T11:00:00Z", "value": 7500},
                ]
            }
        }
        value = collector._extract_attack_value(data)
        assert value == Decimal("7500")

    def test_extract_attack_value_from_summary(self, collector):
        """Test extracting attack volume from summary data."""
        data = {"result": {"summary": {"total": 10000}}}
        value = collector._extract_attack_value(data)
        assert value == Decimal("10000")

    def test_extract_outage_value_from_timeseries(self, collector):
        """Test extracting outage count from timeseries."""
        data = {
            "result": {
                "timeseries": [
                    {"timestamp": "2024-01-15T10:00:00Z", "value": 15},
                    {"timestamp": "2024-01-15T11:00:00Z", "value": 12},
                ]
            }
        }
        value = collector._extract_outage_value(data)
        assert value == Decimal("12")

    def test_extract_values_handle_missing_data(self, collector):
        """Test extraction methods handle missing data gracefully."""
        empty_data = {"result": {}}

        assert collector._extract_traffic_value(empty_data) is None
        assert collector._extract_attack_value(empty_data) is None
        assert collector._extract_outage_value(empty_data) is None


class TestCloudflareRadarIntegration:
    """Integration tests for the complete collection pipeline."""

    @pytest.mark.asyncio
    async def test_full_collection_pipeline(
        self,
        collector,
        mock_traffic_response,
        mock_attacks_response,
        mock_outages_response,
    ):
        """Test the complete fetch -> parse -> validate -> store pipeline."""
        mock_client = AsyncMock()

        def create_response(data):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = data
            resp.raise_for_status = MagicMock()
            return resp

        mock_client.get = AsyncMock(
            side_effect=[
                create_response(mock_traffic_response),
                create_response(mock_attacks_response),
                create_response(mock_outages_response),
            ]
        )

        with patch("src.collectors.cloudflare_radar.settings") as mock_settings:
            mock_settings.cloudflare_api_token = "test-token"
            collector._client = mock_client

            with patch.object(collector, "_get_baseline", return_value=Decimal("1000")):
                with patch.object(collector, "store", return_value=3):
                    raw_data = await collector.fetch()
                    records = await collector.parse(raw_data)
                    valid_records = await collector.validate(records)
                    stored = await collector.store(valid_records)

                    assert len(valid_records) == 3
                    assert stored == 3
