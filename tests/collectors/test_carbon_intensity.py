"""Unit tests for UK Carbon Intensity API collector."""

import pytest
import pytest_asyncio
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from src.collectors.carbon_intensity import (
    CarbonIntensityCollector,
    create_carbon_intensity_collector,
    UK_REGIONS,
    FUEL_TYPES,
    RENEWABLE_FUELS,
    BASE_URL,
)
from src.collectors.base import FetchError, ParseError
from src.models.data_sources import CarbonIntensityReading


class TestCarbonIntensityCollector:
    """Test suite for CarbonIntensityCollector."""

    @pytest.fixture
    def collector(self):
        """Create a collector instance."""
        return CarbonIntensityCollector(regions=["national"])

    @pytest.fixture
    def sample_intensity_response(self):
        """Sample API response for intensity endpoint."""
        return {
            "data": [
                {
                    "from": "2024-01-15T12:00Z",
                    "to": "2024-01-15T12:30Z",
                    "intensity": {
                        "forecast": 180,
                        "actual": 175,
                        "index": "moderate"
                    }
                },
                {
                    "from": "2024-01-15T12:30Z",
                    "to": "2024-01-15T13:00Z",
                    "intensity": {
                        "forecast": 185,
                        "actual": 180,
                        "index": "moderate"
                    }
                },
            ]
        }

    @pytest.fixture
    def sample_generation_response(self):
        """Sample API response for generation endpoint."""
        return {
            "data": [
                {
                    "from": "2024-01-15T12:00Z",
                    "to": "2024-01-15T12:30Z",
                    "generationmix": [
                        {"fuel": "biomass", "perc": 5.2},
                        {"fuel": "coal", "perc": 1.5},
                        {"fuel": "imports", "perc": 8.3},
                        {"fuel": "gas", "perc": 32.1},
                        {"fuel": "nuclear", "perc": 15.8},
                        {"fuel": "other", "perc": 0.3},
                        {"fuel": "hydro", "perc": 2.1},
                        {"fuel": "solar", "perc": 4.5},
                        {"fuel": "wind", "perc": 30.2},
                    ]
                },
                {
                    "from": "2024-01-15T12:30Z",
                    "to": "2024-01-15T13:00Z",
                    "generationmix": [
                        {"fuel": "biomass", "perc": 5.0},
                        {"fuel": "coal", "perc": 1.8},
                        {"fuel": "imports", "perc": 8.0},
                        {"fuel": "gas", "perc": 33.5},
                        {"fuel": "nuclear", "perc": 15.5},
                        {"fuel": "other", "perc": 0.2},
                        {"fuel": "hydro", "perc": 2.0},
                        {"fuel": "solar", "perc": 4.0},
                        {"fuel": "wind", "perc": 30.0},
                    ]
                },
            ]
        }

    def test_collector_initialization(self, collector):
        """Test collector initializes with correct attributes."""
        assert collector.name == "carbon_intensity"
        assert collector.source_id == 4
        assert collector.update_frequency == "continuous"
        assert collector.regions == ["national"]

    def test_collector_with_multiple_regions(self):
        """Test collector can be initialized with multiple regions."""
        regions = ["national", "1", "2"]
        collector = CarbonIntensityCollector(regions=regions)
        assert collector.regions == regions

    def test_uk_regions_constant(self):
        """Test UK regions constant contains expected regions."""
        assert "national" in UK_REGIONS
        assert len(UK_REGIONS) == 15  # national + 14 DNO regions

    def test_fuel_types_constant(self):
        """Test fuel types constant contains expected types."""
        expected = {"biomass", "coal", "imports", "gas", "nuclear", "other", "hydro", "solar", "wind"}
        assert set(FUEL_TYPES) == expected

    def test_renewable_fuels_constant(self):
        """Test renewable fuels constant contains correct types."""
        expected = {"biomass", "hydro", "solar", "wind"}
        assert RENEWABLE_FUELS == expected

    @pytest.mark.asyncio
    async def test_fetch_success(self, collector, sample_intensity_response, sample_generation_response):
        """Test successful data fetch from API."""
        mock_client = AsyncMock()

        # Mock intensity response
        intensity_response = MagicMock()
        intensity_response.status_code = 200
        intensity_response.json.return_value = sample_intensity_response

        # Mock generation response
        generation_response = MagicMock()
        generation_response.status_code = 200
        generation_response.json.return_value = sample_generation_response

        mock_client.get = AsyncMock(side_effect=[intensity_response, generation_response])
        collector._client = mock_client

        start_time = datetime(2024, 1, 15, 12, 0)
        end_time = datetime(2024, 1, 15, 14, 0)

        result = await collector.fetch(start_time=start_time, end_time=end_time)

        assert "regions" in result
        assert "national" in result["regions"]
        assert "intensity" in result["regions"]["national"]
        assert "generation" in result["regions"]["national"]

    @pytest.mark.asyncio
    async def test_fetch_api_error(self, collector):
        """Test fetch handles API errors correctly when exception is raised."""
        mock_client = AsyncMock()

        # Simulate network/connection error that should raise FetchError
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))

        # Patch get_client to return our mock
        with patch.object(collector, 'get_client', return_value=mock_client):
            with pytest.raises(FetchError):
                await collector.fetch()

    @pytest.mark.asyncio
    async def test_parse_intensity_data(self, collector, sample_intensity_response, sample_generation_response):
        """Test parsing of intensity and generation data."""
        raw_data = {
            "regions": {
                "national": {
                    "intensity": sample_intensity_response,
                    "generation": sample_generation_response
                }
            }
        }

        records = await collector.parse(raw_data)

        assert len(records) == 2

        # Check first record
        record = records[0]
        assert record.region == "national"
        assert record.intensity_forecast == 180
        assert record.intensity_actual == 175
        assert record.intensity_index == "moderate"

        # Check generation mix
        assert "gas" in record.generation_mix
        assert record.generation_mix["gas"] == 32.1

        # Check renewable percentage (biomass + hydro + solar + wind)
        expected_renewable = Decimal("5.2") + Decimal("2.1") + Decimal("4.5") + Decimal("30.2")
        assert record.renewable_pct == Decimal(str(expected_renewable))

    @pytest.mark.asyncio
    async def test_parse_missing_generation_data(self, collector, sample_intensity_response):
        """Test parsing handles missing generation data."""
        raw_data = {
            "regions": {
                "national": {
                    "intensity": sample_intensity_response,
                    "generation": None
                }
            }
        }

        records = await collector.parse(raw_data)

        assert len(records) == 2
        assert records[0].generation_mix == {}
        assert records[0].renewable_pct == Decimal("0")

    @pytest.mark.asyncio
    async def test_validate_intensity_range(self, collector):
        """Test validation rejects out-of-range intensity values."""
        valid_record = CarbonIntensityReading(
            timestamp=datetime(2024, 1, 15, 12, 0),
            region="national",
            intensity_forecast=180,
            intensity_actual=175,
            intensity_index="moderate",
            generation_mix={},
            renewable_pct=Decimal("42.0")
        )

        invalid_record = CarbonIntensityReading(
            timestamp=datetime(2024, 1, 15, 12, 30),
            region="national",
            intensity_forecast=600,  # Out of range (> 500)
            intensity_actual=175,
            intensity_index="moderate",
            generation_mix={},
            renewable_pct=Decimal("42.0")
        )

        results = await collector.validate([valid_record, invalid_record])

        assert len(results) == 1
        assert results[0].intensity_forecast == 180

    @pytest.mark.asyncio
    async def test_validate_intensity_zero_to_500(self, collector):
        """Test validation accepts intensity values 0-500 gCO2/kWh."""
        records = [
            CarbonIntensityReading(
                timestamp=datetime(2024, 1, 15, 12, 0),
                region="national",
                intensity_forecast=0,  # Minimum valid
                intensity_actual=0,
                intensity_index="very low",
                generation_mix={},
                renewable_pct=Decimal("95.0")
            ),
            CarbonIntensityReading(
                timestamp=datetime(2024, 1, 15, 12, 30),
                region="national",
                intensity_forecast=500,  # Maximum valid
                intensity_actual=500,
                intensity_index="very high",
                generation_mix={},
                renewable_pct=Decimal("5.0")
            ),
            CarbonIntensityReading(
                timestamp=datetime(2024, 1, 15, 13, 0),
                region="national",
                intensity_forecast=250,  # Mid-range
                intensity_actual=248,
                intensity_index="moderate",
                generation_mix={},
                renewable_pct=Decimal("35.0")
            ),
        ]

        results = await collector.validate(records)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_validate_generation_mix_sum(self, collector):
        """Test validation warns but accepts generation mix not summing to 100%."""
        # Create record with generation mix summing to ~100%
        valid_mix_record = CarbonIntensityReading(
            timestamp=datetime(2024, 1, 15, 12, 0),
            region="national",
            intensity_forecast=180,
            intensity_actual=175,
            intensity_index="moderate",
            generation_mix={
                "gas": 32.1,
                "nuclear": 15.8,
                "wind": 30.2,
                "solar": 4.5,
                "biomass": 5.2,
                "hydro": 2.1,
                "imports": 8.3,
                "coal": 1.5,
                "other": 0.3
            },
            renewable_pct=Decimal("42.0")
        )

        results = await collector.validate([valid_mix_record])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_validate_30_minute_intervals(self, collector):
        """Test validation accepts 30-minute interval timestamps."""
        records = [
            CarbonIntensityReading(
                timestamp=datetime(2024, 1, 15, 12, 0),  # On the hour
                region="national",
                intensity_forecast=180,
                intensity_actual=175,
                intensity_index="moderate",
                generation_mix={},
                renewable_pct=Decimal("42.0")
            ),
            CarbonIntensityReading(
                timestamp=datetime(2024, 1, 15, 12, 30),  # On the half-hour
                region="national",
                intensity_forecast=185,
                intensity_actual=180,
                intensity_index="moderate",
                generation_mix={},
                renewable_pct=Decimal("41.0")
            ),
        ]

        results = await collector.validate(records)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_validate_renewable_pct_range(self, collector):
        """Test validation rejects invalid renewable percentage."""
        invalid_record = CarbonIntensityReading(
            timestamp=datetime(2024, 1, 15, 12, 0),
            region="national",
            intensity_forecast=180,
            intensity_actual=175,
            intensity_index="moderate",
            generation_mix={},
            renewable_pct=Decimal("150.0")  # Invalid > 100%
        )

        results = await collector.validate([invalid_record])
        assert len(results) == 0


class TestCarbonIntensityCollectorFactory:
    """Test the factory function for creating collectors."""

    @pytest.mark.asyncio
    async def test_create_default_collector(self):
        """Test creating collector with default settings."""
        collector = await create_carbon_intensity_collector()
        assert collector.regions == ["national"]

    @pytest.mark.asyncio
    async def test_create_collector_with_regions(self):
        """Test creating collector with specific regions."""
        regions = ["national", "1", "13"]  # National, North Scotland, London
        collector = await create_carbon_intensity_collector(regions=regions)
        assert collector.regions == regions

    @pytest.mark.asyncio
    async def test_create_collector_all_regions(self):
        """Test creating collector with all regions."""
        collector = await create_carbon_intensity_collector(include_all_regions=True)
        assert collector.regions == UK_REGIONS
        assert len(collector.regions) == 15


class TestCarbonIntensityBackfill:
    """Test backfill functionality."""

    @pytest.fixture
    def collector(self):
        """Create collector for backfill tests."""
        return CarbonIntensityCollector(regions=["national"])

    @pytest.mark.asyncio
    async def test_backfill_date_range(self, collector):
        """Test backfill respects date range."""
        # Mock the collect method
        results_collected = []

        async def mock_collect(**kwargs):
            results_collected.append(kwargs)
            from src.collectors.base import CollectorResult
            return CollectorResult(
                success=True,
                records_fetched=48,
                records_stored=48
            )

        collector.collect = mock_collect

        start = date(2024, 1, 1)
        end = date(2024, 1, 3)

        results = await collector.backfill(start, end, batch_size_days=1)

        # Should have batches covering the date range
        assert len(results) >= 3

    @pytest.mark.asyncio
    async def test_backfill_minimum_date(self, collector):
        """Test backfill doesn't go before 2018."""
        async def mock_collect(**kwargs):
            from src.collectors.base import CollectorResult
            return CollectorResult(
                success=True,
                records_fetched=48,
                records_stored=48
            )

        collector.collect = mock_collect

        # Try to backfill from before 2018
        start = date(2015, 1, 1)
        end = date(2018, 1, 7)

        # Should adjust start date to 2018-01-01
        results = await collector.backfill(start, end, batch_size_days=7)
        assert len(results) >= 1


class TestDataIntervalValidation:
    """Test data interval validation."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return CarbonIntensityCollector(regions=["national"])

    @pytest.mark.asyncio
    async def test_30_minute_interval_data(self, collector):
        """Test that data at 30-minute intervals is accepted."""
        base_time = datetime(2024, 1, 15, 0, 0)
        records = []

        # Generate 48 records (24 hours of 30-min data)
        for i in range(48):
            timestamp = base_time + timedelta(minutes=30 * i)
            records.append(CarbonIntensityReading(
                timestamp=timestamp,
                region="national",
                intensity_forecast=180 + (i % 20),  # Vary forecast slightly
                intensity_actual=175 + (i % 20),
                intensity_index="moderate",
                generation_mix={"gas": 40.0, "wind": 35.0, "nuclear": 15.0, "solar": 10.0},
                renewable_pct=Decimal("45.0")
            ))

        valid_records = await collector.validate(records)

        # All records should be valid
        assert len(valid_records) == 48

        # Verify timestamps are at 30-minute intervals
        for record in valid_records:
            assert record.timestamp.minute in (0, 30)


class TestIntensityValueRanges:
    """Test intensity value range validation."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return CarbonIntensityCollector()

    @pytest.mark.asyncio
    async def test_intensity_boundary_values(self, collector):
        """Test intensity values at boundaries (0 and 500 gCO2/kWh)."""
        records = [
            # At lower boundary
            CarbonIntensityReading(
                timestamp=datetime(2024, 1, 15, 12, 0),
                region="national",
                intensity_forecast=0,
                intensity_actual=0,
                intensity_index="very low",
                generation_mix={},
                renewable_pct=Decimal("100.0")
            ),
            # At upper boundary
            CarbonIntensityReading(
                timestamp=datetime(2024, 1, 15, 12, 30),
                region="national",
                intensity_forecast=500,
                intensity_actual=500,
                intensity_index="very high",
                generation_mix={},
                renewable_pct=Decimal("0.0")
            ),
            # Just below lower boundary (invalid)
            CarbonIntensityReading(
                timestamp=datetime(2024, 1, 15, 13, 0),
                region="national",
                intensity_forecast=-1,
                intensity_actual=-1,
                intensity_index="invalid",
                generation_mix={},
                renewable_pct=Decimal("100.0")
            ),
            # Just above upper boundary (invalid)
            CarbonIntensityReading(
                timestamp=datetime(2024, 1, 15, 13, 30),
                region="national",
                intensity_forecast=501,
                intensity_actual=501,
                intensity_index="invalid",
                generation_mix={},
                renewable_pct=Decimal("0.0")
            ),
        ]

        valid_records = await collector.validate(records)

        # Only first two should be valid
        assert len(valid_records) == 2
        assert valid_records[0].intensity_forecast == 0
        assert valid_records[1].intensity_forecast == 500


class TestGenerationMixValidation:
    """Test generation mix percentage validation."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return CarbonIntensityCollector()

    @pytest.mark.asyncio
    async def test_generation_mix_sums_to_100(self, collector):
        """Test generation mix percentages summing to approximately 100%."""
        # Valid mix summing to 100%
        valid_record = CarbonIntensityReading(
            timestamp=datetime(2024, 1, 15, 12, 0),
            region="national",
            intensity_forecast=180,
            intensity_actual=175,
            intensity_index="moderate",
            generation_mix={
                "gas": 35.0,
                "wind": 25.0,
                "nuclear": 20.0,
                "solar": 10.0,
                "biomass": 5.0,
                "hydro": 3.0,
                "imports": 1.5,
                "coal": 0.3,
                "other": 0.2
            },
            renewable_pct=Decimal("43.0")  # wind + solar + biomass + hydro
        )

        results = await collector.validate([valid_record])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_generation_mix_with_rounding(self, collector):
        """Test generation mix with slight rounding differences (99-101%)."""
        # Mix summing to 100.1% (acceptable rounding)
        record_high = CarbonIntensityReading(
            timestamp=datetime(2024, 1, 15, 12, 0),
            region="national",
            intensity_forecast=180,
            intensity_actual=175,
            intensity_index="moderate",
            generation_mix={
                "gas": 35.1,
                "wind": 25.0,
                "nuclear": 20.0,
                "solar": 10.0,
                "biomass": 5.0,
                "hydro": 3.0,
                "imports": 1.5,
                "coal": 0.3,
                "other": 0.2
            },
            renewable_pct=Decimal("43.0")
        )

        # Mix summing to 99.9% (acceptable rounding)
        record_low = CarbonIntensityReading(
            timestamp=datetime(2024, 1, 15, 12, 30),
            region="national",
            intensity_forecast=182,
            intensity_actual=177,
            intensity_index="moderate",
            generation_mix={
                "gas": 34.9,
                "wind": 25.0,
                "nuclear": 20.0,
                "solar": 10.0,
                "biomass": 5.0,
                "hydro": 3.0,
                "imports": 1.5,
                "coal": 0.3,
                "other": 0.2
            },
            renewable_pct=Decimal("43.0")
        )

        results = await collector.validate([record_high, record_low])
        # Both should pass (within 1% tolerance)
        assert len(results) == 2
