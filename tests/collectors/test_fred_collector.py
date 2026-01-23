"""Tests for FRED building permits collector."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import json

import pytest
import pytest_asyncio
import httpx

from src.collectors.fred_collector import (
    FREDCollector,
    FRED_SERIES,
    PRIMARY_ENTITIES,
)
from src.collectors.base import FetchError, ParseError
from src.models.data_sources import BuildingPermitData


class TestFREDCollectorInit:
    """Tests for FREDCollector initialization."""

    def test_default_series(self):
        """Test collector initializes with all configured series."""
        collector = FREDCollector()
        assert set(collector.series_ids) == set(FRED_SERIES.keys())

    def test_custom_series(self):
        """Test collector with custom series list."""
        series = ["PERMIT", "PERMIT1"]
        collector = FREDCollector(series_ids=series)
        assert collector.series_ids == series

    def test_collector_metadata(self):
        """Test collector metadata is set correctly."""
        collector = FREDCollector()
        assert collector.name == "fred_building_permits"
        assert collector.source_id == 5
        assert collector.update_frequency == "monthly"


class TestFREDCollectorFetch:
    """Tests for FRED API fetching."""

    @pytest.fixture
    def mock_fred_response(self):
        """Sample FRED API response."""
        return {
            "realtime_start": "2024-01-01",
            "realtime_end": "2024-01-15",
            "observation_start": "1960-01-01",
            "observation_end": "2024-01-01",
            "units": "Thousands of Units",
            "output_type": 1,
            "file_type": "json",
            "order_by": "observation_date",
            "sort_order": "asc",
            "count": 3,
            "offset": 0,
            "limit": 100000,
            "observations": [
                {
                    "realtime_start": "2024-01-01",
                    "realtime_end": "2024-01-15",
                    "date": "2023-10-01",
                    "value": "1487"
                },
                {
                    "realtime_start": "2024-01-01",
                    "realtime_end": "2024-01-15",
                    "date": "2023-11-01",
                    "value": "1460"
                },
                {
                    "realtime_start": "2024-01-01",
                    "realtime_end": "2024-01-15",
                    "date": "2023-12-01",
                    "value": "1495"
                },
            ]
        }

    @pytest_asyncio.fixture
    async def collector_with_key(self):
        """Create collector with mocked API key."""
        with patch("src.collectors.fred_collector.settings") as mock_settings:
            mock_settings.fred_api_key = "test_api_key"
            mock_settings.collector_timeout_seconds = 60
            mock_settings.app_version = "0.1.0"
            collector = FREDCollector(series_ids=["PERMIT"])
            yield collector
            await collector.close()

    @pytest.mark.asyncio
    async def test_fetch_without_api_key(self):
        """Test fetch fails without API key."""
        with patch("src.collectors.fred_collector.settings") as mock_settings:
            mock_settings.fred_api_key = None
            collector = FREDCollector(series_ids=["PERMIT"])

            with pytest.raises(FetchError, match="API key not configured"):
                await collector.fetch()

    @pytest.mark.asyncio
    async def test_fetch_success(self, collector_with_key, mock_fred_response):
        """Test successful FRED API fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_fred_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            collector_with_key,
            "get_client",
            return_value=AsyncMock(
                get=AsyncMock(return_value=mock_response)
            ),
        ):
            result = await collector_with_key.fetch()

            assert "PERMIT" in result
            assert len(result["PERMIT"]["observations"]) == 3
            assert result["PERMIT"]["metadata"]["permit_type"] == "total"

    @pytest.mark.asyncio
    async def test_fetch_with_date_range(self, collector_with_key, mock_fred_response):
        """Test fetch with specific date range."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_fred_response
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(collector_with_key, "get_client", return_value=mock_client):
            start_date = date(2023, 1, 1)
            end_date = date(2023, 12, 31)

            await collector_with_key.fetch(
                start_date=start_date,
                end_date=end_date,
            )

            # Verify date params were passed
            call_args = mock_client.get.call_args
            params = call_args.kwargs.get("params", call_args.args[1] if len(call_args.args) > 1 else {})
            assert params.get("observation_start") == "2023-01-01"
            assert params.get("observation_end") == "2023-12-31"

    @pytest.mark.asyncio
    async def test_fetch_http_error(self, collector_with_key):
        """Test fetch handles HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=MagicMock(),
            response=mock_response,
        )

        with patch.object(
            collector_with_key,
            "get_client",
            return_value=AsyncMock(
                get=AsyncMock(return_value=mock_response)
            ),
        ):
            with pytest.raises(FetchError, match="FRED API error"):
                await collector_with_key.fetch()


class TestFREDCollectorParse:
    """Tests for FRED data parsing."""

    @pytest.fixture
    def raw_data_sample(self):
        """Sample raw data from fetch."""
        return {
            "PERMIT": {
                "observations": [
                    {"date": "2023-10-01", "value": "1487"},
                    {"date": "2023-11-01", "value": "1460"},
                    {"date": "2023-12-01", "value": "1495"},
                ],
                "metadata": {
                    "geography_level": "national",
                    "geography_code": "US",
                    "geography_name": "United States",
                    "permit_type": "total",
                    "seasonally_adjusted": True,
                },
            }
        }

    @pytest.mark.asyncio
    async def test_parse_success(self, raw_data_sample):
        """Test successful parsing of FRED data."""
        collector = FREDCollector()
        records = await collector.parse(raw_data_sample)

        assert len(records) == 3

        # Check first record
        first = records[0]
        assert first.period == date(2023, 10, 1)
        assert first.geography_level == "national"
        assert first.geography_code == "US"
        assert first.permit_type == "total"
        # Value 1487 (thousands) -> 1,487,000 units
        assert first.units_authorized == 1487000
        assert first.seasonally_adjusted is True

    @pytest.mark.asyncio
    async def test_parse_handles_missing_values(self):
        """Test parsing handles FRED missing value marker."""
        collector = FREDCollector()
        raw_data = {
            "PERMIT": {
                "observations": [
                    {"date": "2023-10-01", "value": "1487"},
                    {"date": "2023-11-01", "value": "."},  # Missing
                    {"date": "2023-12-01", "value": "1495"},
                ],
                "metadata": {
                    "geography_level": "national",
                    "geography_code": "US",
                    "geography_name": "United States",
                    "permit_type": "total",
                    "seasonally_adjusted": True,
                },
            }
        }

        records = await collector.parse(raw_data)
        assert len(records) == 2  # Missing value skipped

    @pytest.mark.asyncio
    async def test_parse_multiple_series(self):
        """Test parsing multiple series."""
        collector = FREDCollector()
        raw_data = {
            "PERMIT": {
                "observations": [{"date": "2023-10-01", "value": "1487"}],
                "metadata": {
                    "geography_level": "national",
                    "geography_code": "US",
                    "geography_name": "United States",
                    "permit_type": "total",
                    "seasonally_adjusted": True,
                },
            },
            "PERMIT1": {
                "observations": [{"date": "2023-10-01", "value": "987"}],
                "metadata": {
                    "geography_level": "national",
                    "geography_code": "US",
                    "geography_name": "United States",
                    "permit_type": "single_family",
                    "seasonally_adjusted": True,
                },
            },
        }

        records = await collector.parse(raw_data)
        assert len(records) == 2

        permit_types = {r.permit_type for r in records}
        assert permit_types == {"total", "single_family"}


class TestFREDCollectorValidate:
    """Tests for FRED data validation."""

    @pytest.mark.asyncio
    async def test_validate_positive_values(self):
        """Test validation passes for reasonable values."""
        collector = FREDCollector()

        records = [
            BuildingPermitData(
                period=date(2023, 10, 1),
                geography_level="national",
                geography_code="US",
                geography_name="United States",
                permit_type="total",
                units_authorized=1487000,
                seasonally_adjusted=True,
            ),
        ]

        valid = await collector.validate(records)
        assert len(valid) == 1

    @pytest.mark.asyncio
    async def test_validate_rejects_negative_values(self):
        """Test validation rejects negative permit values."""
        collector = FREDCollector()

        records = [
            BuildingPermitData(
                period=date(2023, 10, 1),
                geography_level="national",
                geography_code="US",
                geography_name="United States",
                permit_type="total",
                units_authorized=-100,  # Invalid
                seasonally_adjusted=True,
            ),
        ]

        valid = await collector.validate(records)
        assert len(valid) == 0

    @pytest.mark.asyncio
    async def test_validate_rejects_future_dates(self):
        """Test validation rejects future dates."""
        collector = FREDCollector()

        future_date = date(2099, 1, 1)
        records = [
            BuildingPermitData(
                period=future_date,
                geography_level="national",
                geography_code="US",
                geography_name="United States",
                permit_type="total",
                units_authorized=1000000,
                seasonally_adjusted=True,
            ),
        ]

        valid = await collector.validate(records)
        assert len(valid) == 0

    @pytest.mark.asyncio
    async def test_validate_rejects_too_old_dates(self):
        """Test validation rejects dates before 1960."""
        collector = FREDCollector()

        records = [
            BuildingPermitData(
                period=date(1959, 12, 1),  # Before 1960
                geography_level="national",
                geography_code="US",
                geography_name="United States",
                permit_type="total",
                units_authorized=500000,
                seasonally_adjusted=True,
            ),
        ]

        valid = await collector.validate(records)
        assert len(valid) == 0


class TestFREDCollectorComputeChanges:
    """Tests for MoM and YoY change calculations."""

    @pytest.mark.asyncio
    async def test_compute_mom_change(self):
        """Test month-over-month change calculation."""
        collector = FREDCollector()

        records = [
            BuildingPermitData(
                period=date(2023, 10, 1),
                geography_level="national",
                geography_code="US",
                geography_name="United States",
                permit_type="total",
                units_authorized=1000000,
                seasonally_adjusted=True,
            ),
            BuildingPermitData(
                period=date(2023, 11, 1),
                geography_level="national",
                geography_code="US",
                geography_name="United States",
                permit_type="total",
                units_authorized=1100000,  # 10% increase
                seasonally_adjusted=True,
            ),
        ]

        updated = await collector.compute_changes(records)

        # Find November record
        nov_record = next(r for r in updated if r.period.month == 11)
        assert nov_record.mom_change_pct is not None
        assert float(nov_record.mom_change_pct) == pytest.approx(10.0, rel=0.01)

    @pytest.mark.asyncio
    async def test_compute_yoy_change(self):
        """Test year-over-year change calculation."""
        collector = FREDCollector()

        records = [
            BuildingPermitData(
                period=date(2022, 10, 1),
                geography_level="national",
                geography_code="US",
                geography_name="United States",
                permit_type="total",
                units_authorized=1000000,
                seasonally_adjusted=True,
            ),
            BuildingPermitData(
                period=date(2023, 10, 1),
                geography_level="national",
                geography_code="US",
                geography_name="United States",
                permit_type="total",
                units_authorized=1200000,  # 20% increase
                seasonally_adjusted=True,
            ),
        ]

        updated = await collector.compute_changes(records)

        # Find 2023 October record
        oct_2023 = next(r for r in updated if r.period == date(2023, 10, 1))
        assert oct_2023.yoy_change_pct is not None
        assert float(oct_2023.yoy_change_pct) == pytest.approx(20.0, rel=0.01)


class TestFREDCollectorDataFreshness:
    """Tests for monthly data freshness requirements."""

    @pytest.fixture
    def sample_monthly_data(self):
        """Generate sample monthly permit data."""
        from dateutil.relativedelta import relativedelta

        base_date = date(2024, 1, 1)
        records = []

        for i in range(24):  # 24 months of data
            period = base_date - relativedelta(months=i)
            records.append(
                BuildingPermitData(
                    period=period.replace(day=1),
                    geography_level="national",
                    geography_code="US",
                    geography_name="United States",
                    permit_type="total",
                    units_authorized=1400000 + (i * 10000),  # Varying values
                    seasonally_adjusted=True,
                )
            )

        return records

    @pytest.mark.asyncio
    async def test_monthly_data_coverage(self, sample_monthly_data):
        """Test that we have complete monthly coverage."""
        collector = FREDCollector()
        valid = await collector.validate(sample_monthly_data)

        # Should have 24 months of valid data
        assert len(valid) == 24

        # Check all months are present
        periods = sorted([r.period for r in valid])
        for i in range(len(periods) - 1):
            curr = periods[i]
            next_period = periods[i + 1]
            # Each period should be exactly 1 month apart
            if curr.month == 12:
                expected_next = date(curr.year + 1, 1, 1)
            else:
                expected_next = date(curr.year, curr.month + 1, 1)
            assert next_period == expected_next

    @pytest.mark.asyncio
    async def test_reasonable_permit_values(self, sample_monthly_data):
        """Test permit values are within reasonable ranges."""
        collector = FREDCollector()
        valid = await collector.validate(sample_monthly_data)

        for record in valid:
            # US typically issues 1-2 million permits annually
            # Monthly values should be in reasonable range (50K-200K thousands -> 50M-200M)
            # But we convert to actual units, so 1M-2M range is reasonable monthly
            assert record.units_authorized > 0
            assert record.units_authorized < 3000000  # 3 million monthly max


class TestFREDSeriesConfiguration:
    """Tests for FRED series configuration."""

    def test_all_series_have_metadata(self):
        """Test all configured series have required metadata."""
        required_fields = [
            "geography_level",
            "geography_code",
            "geography_name",
            "permit_type",
            "seasonally_adjusted",
        ]

        for series_id, metadata in FRED_SERIES.items():
            for field in required_fields:
                assert field in metadata, f"Series {series_id} missing {field}"

    def test_primary_entities_defined(self):
        """Test primary entities are defined."""
        assert len(PRIMARY_ENTITIES) > 0
        # Should include homebuilders and home improvement
        assert "DHI" in PRIMARY_ENTITIES  # D.R. Horton
        assert "LEN" in PRIMARY_ENTITIES  # Lennar
        assert "PHM" in PRIMARY_ENTITIES  # PulteGroup
        assert "HD" in PRIMARY_ENTITIES   # Home Depot
        assert "LOW" in PRIMARY_ENTITIES  # Lowe's

    def test_regional_series_coverage(self):
        """Test regional series cover all Census regions."""
        regional_series = [
            s for s, m in FRED_SERIES.items()
            if m["geography_level"] == "region"
        ]

        regions = {FRED_SERIES[s]["geography_code"] for s in regional_series}

        # Should have all four Census regions
        expected_regions = {"NE", "MW", "SO", "WE"}
        assert regions == expected_regions
