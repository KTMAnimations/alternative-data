"""Tests for Zillow Rental Index collector."""

import csv
import io
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio

from src.collectors.zillow_rental import ZillowRentalCollector, ZillowRentalRecord
from src.collectors.base import FetchError, ParseError
from src.models.data_sources import ZillowRentalIndex


@pytest.fixture
def collector():
    """Create a ZillowRentalCollector instance."""
    return ZillowRentalCollector()


@pytest.fixture
def sample_csv_content():
    """Generate sample Zillow CSV content."""
    header = [
        "RegionID",
        "RegionName",
        "RegionType",
        "StateName",
        "2023-01-31",
        "2023-02-28",
        "2023-03-31",
        "2024-01-31",
        "2024-02-29",
        "2024-03-31",
    ]
    rows = [
        ["102001", "United States", "country", "", "1800.00", "1810.50", "1825.00", "1900.00", "1915.00", "1930.00"],
        ["394913", "New York, NY", "metro", "NY", "2500.00", "2520.00", "2550.00", "2650.00", "2680.00", "2710.00"],
        ["753899", "Los Angeles, CA", "metro", "CA", "2800.00", "2820.00", "2850.00", "2950.00", "2980.00", "3010.00"],
        ["394463", "Chicago, IL", "metro", "IL", "1600.00", "1610.00", "1625.00", "1700.00", "1715.00", "1730.00"],
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerows(rows)
    return output.getvalue()


@pytest.fixture
def sample_fetch_response(sample_csv_content):
    """Create sample fetch response."""
    return {
        "csv_content": sample_csv_content,
        "geography_level": "metro",
        "property_type": "all",
        "source_url": "https://example.com/zori.csv",
        "fetch_timestamp": datetime.utcnow(),
    }


class TestZillowRentalCollectorInit:
    """Tests for collector initialization."""

    def test_collector_name(self, collector):
        """Test collector has correct name."""
        assert collector.name == "zillow_rental"

    def test_collector_source_id(self, collector):
        """Test collector has correct source ID."""
        assert collector.source_id == 8

    def test_collector_update_frequency(self, collector):
        """Test collector has monthly update frequency."""
        assert collector.update_frequency == "monthly"

    def test_csv_urls_configured(self, collector):
        """Test CSV URLs are properly configured."""
        assert len(collector.CSV_URLS) > 0
        assert ("all", "metro") in collector.CSV_URLS
        assert ("single_family", "metro") in collector.CSV_URLS
        assert ("multi_family", "metro") in collector.CSV_URLS


class TestZillowRentalCollectorFetch:
    """Tests for fetch functionality."""

    @pytest.mark.asyncio
    async def test_fetch_success(self, collector, sample_csv_content):
        """Test successful CSV fetch."""
        mock_response = MagicMock()
        mock_response.text = sample_csv_content
        mock_response.raise_for_status = MagicMock()

        with patch.object(collector, "get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await collector.fetch(
                geography_level="metro",
                property_type="all",
            )

            assert result["csv_content"] == sample_csv_content
            assert result["geography_level"] == "metro"
            assert result["property_type"] == "all"
            assert "fetch_timestamp" in result

    @pytest.mark.asyncio
    async def test_fetch_http_error(self, collector):
        """Test fetch handles HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=mock_response,
            )
        )

        with patch.object(collector, "get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(FetchError) as exc_info:
                await collector.fetch(geography_level="metro", property_type="all")

            assert "HTTP error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_invalid_url_key(self, collector):
        """Test fetch handles invalid geography/property combination."""
        # Remove the fallback to trigger error
        original_fallback = collector.FALLBACK_URLS
        collector.FALLBACK_URLS = {}

        with pytest.raises(FetchError) as exc_info:
            await collector.fetch(
                geography_level="invalid",
                property_type="invalid",
            )

        assert "No URL configured" in str(exc_info.value)
        collector.FALLBACK_URLS = original_fallback


class TestZillowRentalCollectorParse:
    """Tests for CSV parsing functionality."""

    @pytest.mark.asyncio
    async def test_parse_success(self, collector, sample_fetch_response):
        """Test successful CSV parsing."""
        records = await collector.parse(sample_fetch_response)

        assert len(records) > 0
        assert all(isinstance(r, ZillowRentalRecord) for r in records)

    @pytest.mark.asyncio
    async def test_parse_extracts_zori_values(self, collector, sample_fetch_response):
        """Test ZORI values are correctly extracted."""
        records = await collector.parse(sample_fetch_response)

        # Find New York record for 2024-01
        ny_records = [
            r for r in records
            if r.geography_name == "New York, NY" and r.period == date(2024, 1, 1)
        ]

        assert len(ny_records) == 1
        assert ny_records[0].zori_value == Decimal("2650.00")

    @pytest.mark.asyncio
    async def test_parse_calculates_yoy_change(self, collector, sample_fetch_response):
        """Test YoY change is calculated correctly."""
        records = await collector.parse(sample_fetch_response)

        # Find United States record for 2024-01
        us_records = [
            r for r in records
            if r.geography_name == "United States" and r.period == date(2024, 1, 1)
        ]

        assert len(us_records) == 1
        # YoY change: (1900 - 1800) / 1800 * 100 = 5.5556%
        expected_yoy = ((Decimal("1900") - Decimal("1800")) / Decimal("1800")) * 100
        assert abs(us_records[0].yoy_change_pct - expected_yoy) < Decimal("0.01")

    @pytest.mark.asyncio
    async def test_parse_calculates_mom_change(self, collector, sample_fetch_response):
        """Test MoM change is calculated correctly."""
        records = await collector.parse(sample_fetch_response)

        # Find United States record for 2024-02
        us_feb_records = [
            r for r in records
            if r.geography_name == "United States" and r.period == date(2024, 2, 1)
        ]

        assert len(us_feb_records) == 1
        # MoM change: (1915 - 1900) / 1900 * 100 = 0.789%
        expected_mom = ((Decimal("1915") - Decimal("1900")) / Decimal("1900")) * 100
        assert abs(us_feb_records[0].mom_change_pct - expected_mom) < Decimal("0.01")

    @pytest.mark.asyncio
    async def test_parse_handles_empty_values(self, collector):
        """Test parsing handles empty ZORI values."""
        csv_content = """RegionID,RegionName,2024-01-31,2024-02-29
102001,United States,1800.00,
394913,New York NY,2500.00,2520.00"""

        fetch_response = {
            "csv_content": csv_content,
            "geography_level": "metro",
            "property_type": "all",
            "source_url": "https://example.com/zori.csv",
            "fetch_timestamp": datetime.utcnow(),
        }

        records = await collector.parse(fetch_response)

        # Should have records for both dates for NY, only one for US
        us_records = [r for r in records if r.geography_name == "United States"]
        assert len(us_records) == 1  # Only Jan has value

    @pytest.mark.asyncio
    async def test_parse_no_date_columns_raises_error(self, collector):
        """Test parsing raises error when no date columns found."""
        csv_content = """RegionID,RegionName,SomeOtherColumn
102001,United States,value"""

        fetch_response = {
            "csv_content": csv_content,
            "geography_level": "metro",
            "property_type": "all",
            "source_url": "https://example.com/zori.csv",
            "fetch_timestamp": datetime.utcnow(),
        }

        with pytest.raises(ParseError) as exc_info:
            await collector.parse(fetch_response)

        assert "No date columns found" in str(exc_info.value)


class TestZillowRentalCollectorValidate:
    """Tests for record validation."""

    @pytest.mark.asyncio
    async def test_validate_accepts_valid_records(self, collector):
        """Test validation accepts valid records."""
        records = [
            ZillowRentalRecord(
                period=date(2024, 1, 1),
                geography_level="metro",
                geography_id="394913",
                geography_name="New York, NY",
                property_type="all",
                zori_value=Decimal("2500.00"),
                mom_change_pct=Decimal("0.5"),
                yoy_change_pct=Decimal("5.0"),
            )
        ]

        valid_records = await collector.validate(records)
        assert len(valid_records) == 1

    @pytest.mark.asyncio
    async def test_validate_rejects_negative_zori(self, collector):
        """Test validation rejects negative ZORI values."""
        records = [
            ZillowRentalRecord(
                period=date(2024, 1, 1),
                geography_level="metro",
                geography_id="394913",
                geography_name="New York, NY",
                property_type="all",
                zori_value=Decimal("-100.00"),
            )
        ]

        valid_records = await collector.validate(records)
        assert len(valid_records) == 0

    @pytest.mark.asyncio
    async def test_validate_rejects_unreasonable_zori(self, collector):
        """Test validation rejects ZORI outside reasonable range."""
        records = [
            ZillowRentalRecord(
                period=date(2024, 1, 1),
                geography_level="metro",
                geography_id="394913",
                geography_name="Test",
                property_type="all",
                zori_value=Decimal("50.00"),  # Too low
            ),
            ZillowRentalRecord(
                period=date(2024, 1, 1),
                geography_level="metro",
                geography_id="394914",
                geography_name="Test2",
                property_type="all",
                zori_value=Decimal("50000.00"),  # Too high
            ),
        ]

        valid_records = await collector.validate(records)
        assert len(valid_records) == 0

    @pytest.mark.asyncio
    async def test_validate_rejects_pre_2015_data(self, collector):
        """Test validation rejects data before 2015."""
        records = [
            ZillowRentalRecord(
                period=date(2014, 12, 1),
                geography_level="metro",
                geography_id="394913",
                geography_name="New York, NY",
                property_type="all",
                zori_value=Decimal("2000.00"),
            )
        ]

        valid_records = await collector.validate(records)
        assert len(valid_records) == 0

    @pytest.mark.asyncio
    async def test_validate_rejects_future_data(self, collector):
        """Test validation rejects future dates."""
        future_date = date(2030, 1, 1)
        records = [
            ZillowRentalRecord(
                period=future_date,
                geography_level="metro",
                geography_id="394913",
                geography_name="New York, NY",
                property_type="all",
                zori_value=Decimal("2500.00"),
            )
        ]

        valid_records = await collector.validate(records)
        assert len(valid_records) == 0

    @pytest.mark.asyncio
    async def test_validate_rejects_missing_geography_id(self, collector):
        """Test validation rejects records without geography ID."""
        records = [
            ZillowRentalRecord(
                period=date(2024, 1, 1),
                geography_level="metro",
                geography_id="",
                geography_name="Test",
                property_type="all",
                zori_value=Decimal("2000.00"),
            )
        ]

        valid_records = await collector.validate(records)
        assert len(valid_records) == 0


class TestZillowRentalCollectorStore:
    """Tests for database storage."""

    @pytest_asyncio.fixture
    async def db_session_with_zillow(self, db_session):
        """Database session with Zillow table created."""
        return db_session

    @pytest.mark.asyncio
    async def test_store_inserts_records(self, collector, db_session_with_zillow):
        """Test store inserts new records."""
        records = [
            ZillowRentalRecord(
                period=date(2024, 1, 1),
                geography_level="metro",
                geography_id="394913",
                geography_name="New York, NY",
                property_type="all",
                zori_value=Decimal("2500.00"),
                mom_change_pct=Decimal("0.5"),
                yoy_change_pct=Decimal("5.0"),
            )
        ]

        with patch("src.collectors.zillow_rental.get_async_session") as mock_session:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=db_session_with_zillow)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_ctx

            stored_count = await collector.store(records)

            # Should attempt to store 1 record
            assert stored_count == 1

    @pytest.mark.asyncio
    async def test_store_empty_list(self, collector):
        """Test store handles empty list."""
        stored_count = await collector.store([])
        assert stored_count == 0


class TestZillowRentalCollectorIntegration:
    """Integration tests for the full collection pipeline."""

    @pytest.mark.asyncio
    async def test_collect_full_pipeline(self, collector, sample_csv_content):
        """Test full collect pipeline."""
        mock_response = MagicMock()
        mock_response.text = sample_csv_content
        mock_response.raise_for_status = MagicMock()

        with patch.object(collector, "get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with patch.object(collector, "store", new_callable=AsyncMock) as mock_store:
                mock_store.return_value = 10

                result = await collector.collect(
                    geography_level="metro",
                    property_type="all",
                )

                assert result.success is True
                assert result.records_fetched > 0
                mock_store.assert_called_once()


class TestDataFreshness:
    """Tests for data freshness requirements."""

    @pytest.mark.asyncio
    async def test_monthly_data_freshness(self, collector, sample_csv_content):
        """Test that data is available for recent months."""
        # The sample CSV has data through 2024-03
        fetch_response = {
            "csv_content": sample_csv_content,
            "geography_level": "metro",
            "property_type": "all",
            "source_url": "https://example.com/zori.csv",
            "fetch_timestamp": datetime.utcnow(),
        }

        records = await collector.parse(fetch_response)

        # Get all unique periods
        periods = {r.period for r in records}

        # Should have multiple months
        assert len(periods) >= 6  # At least 6 months of data

    @pytest.mark.asyncio
    async def test_data_covers_all_sample_metros(self, collector, sample_csv_content):
        """Test geographic coverage includes major metros."""
        fetch_response = {
            "csv_content": sample_csv_content,
            "geography_level": "metro",
            "property_type": "all",
            "source_url": "https://example.com/zori.csv",
            "fetch_timestamp": datetime.utcnow(),
        }

        records = await collector.parse(fetch_response)

        # Get all unique regions
        regions = {r.geography_name for r in records}

        # Should include major metros from sample
        assert "New York, NY" in regions
        assert "Los Angeles, CA" in regions
        assert "Chicago, IL" in regions


class TestZORIValueReasonableness:
    """Tests for ZORI value reasonableness."""

    @pytest.mark.asyncio
    async def test_zori_values_positive(self, collector, sample_csv_content):
        """Test all ZORI values are positive."""
        fetch_response = {
            "csv_content": sample_csv_content,
            "geography_level": "metro",
            "property_type": "all",
            "source_url": "https://example.com/zori.csv",
            "fetch_timestamp": datetime.utcnow(),
        }

        records = await collector.parse(fetch_response)

        for record in records:
            assert record.zori_value > 0, f"ZORI should be positive, got {record.zori_value}"

    @pytest.mark.asyncio
    async def test_zori_values_reasonable_range(self, collector, sample_csv_content):
        """Test ZORI values are within reasonable range."""
        fetch_response = {
            "csv_content": sample_csv_content,
            "geography_level": "metro",
            "property_type": "all",
            "source_url": "https://example.com/zori.csv",
            "fetch_timestamp": datetime.utcnow(),
        }

        records = await collector.parse(fetch_response)

        # Validate after parse (before store)
        valid_records = await collector.validate(records)

        for record in valid_records:
            assert Decimal("200") <= record.zori_value <= Decimal("10000"), \
                f"ZORI {record.zori_value} outside reasonable range for {record.geography_name}"

    @pytest.mark.asyncio
    async def test_yoy_change_reasonable(self, collector, sample_csv_content):
        """Test YoY changes are within reasonable bounds."""
        fetch_response = {
            "csv_content": sample_csv_content,
            "geography_level": "metro",
            "property_type": "all",
            "source_url": "https://example.com/zori.csv",
            "fetch_timestamp": datetime.utcnow(),
        }

        records = await collector.parse(fetch_response)

        for record in records:
            if record.yoy_change_pct is not None:
                # YoY rent changes typically -20% to +30%
                assert Decimal("-50") <= record.yoy_change_pct <= Decimal("50"), \
                    f"YoY change {record.yoy_change_pct}% seems unreasonable"
