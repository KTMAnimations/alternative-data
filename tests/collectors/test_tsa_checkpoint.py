"""Unit tests for TSA Checkpoint collector."""

import pytest
import pytest_asyncio
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.collectors.tsa_checkpoint import (
    TSACheckpointCollector,
    is_holiday_period,
)
from src.collectors.base import FetchError, ParseError
from src.models.data_sources import TSACheckpoint


# Sample HTML responses for testing
SAMPLE_TSA_HTML = """
<!DOCTYPE html>
<html>
<head><title>TSA Passenger Volumes</title></head>
<body>
<table>
    <tr>
        <th>Date</th>
        <th>2024 Throughput</th>
        <th>2023 Throughput</th>
    </tr>
    <tr>
        <td>1/15/2024</td>
        <td>2,500,000</td>
        <td>2,300,000</td>
    </tr>
    <tr>
        <td>1/14/2024</td>
        <td>2,600,000</td>
        <td>2,400,000</td>
    </tr>
    <tr>
        <td>1/13/2024</td>
        <td>2,400,000</td>
        <td>2,200,000</td>
    </tr>
</table>
</body>
</html>
"""

SAMPLE_TSA_HTML_WITH_MISSING = """
<!DOCTYPE html>
<html>
<body>
<table>
    <tr>
        <th>Date</th>
        <th>2024 Throughput</th>
        <th>2023 Throughput</th>
    </tr>
    <tr>
        <td>1/15/2024</td>
        <td>2,500,000</td>
        <td>N/A</td>
    </tr>
    <tr>
        <td>1/14/2024</td>
        <td>2,600,000</td>
        <td>-</td>
    </tr>
</table>
</body>
</html>
"""

SAMPLE_TSA_HTML_EMPTY = """
<!DOCTYPE html>
<html>
<body>
<div>No data available</div>
</body>
</html>
"""


class TestHolidayPeriod:
    """Tests for holiday period detection."""

    def test_christmas_period(self):
        """Test Christmas holiday period detection."""
        assert is_holiday_period(date(2024, 12, 25)) is True
        assert is_holiday_period(date(2024, 12, 20)) is True
        assert is_holiday_period(date(2024, 12, 10)) is False

    def test_thanksgiving_period(self):
        """Test Thanksgiving holiday period detection."""
        assert is_holiday_period(date(2024, 11, 25)) is True
        assert is_holiday_period(date(2024, 11, 28)) is True
        assert is_holiday_period(date(2024, 11, 10)) is False

    def test_summer_non_holiday(self):
        """Test non-holiday summer dates."""
        assert is_holiday_period(date(2024, 8, 15)) is False
        assert is_holiday_period(date(2024, 6, 15)) is False

    def test_new_years_wraparound(self):
        """Test New Year's period that spans year boundary."""
        assert is_holiday_period(date(2024, 12, 31)) is True
        assert is_holiday_period(date(2024, 1, 1)) is True
        assert is_holiday_period(date(2024, 1, 5)) is False

    def test_memorial_day_weekend(self):
        """Test Memorial Day weekend period."""
        assert is_holiday_period(date(2024, 5, 27)) is True
        assert is_holiday_period(date(2024, 5, 15)) is False

    def test_labor_day_weekend(self):
        """Test Labor Day weekend period."""
        assert is_holiday_period(date(2024, 9, 2)) is True
        assert is_holiday_period(date(2024, 9, 15)) is False


class TestTSACheckpointCollector:
    """Tests for TSA Checkpoint collector."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return TSACheckpointCollector()

    def test_collector_properties(self, collector):
        """Test collector has correct properties."""
        assert collector.name == "tsa_checkpoint"
        assert collector.source_id == 1
        assert collector.update_frequency == "daily"
        assert collector.MIN_THROUGHPUT == 1_000_000
        assert collector.MAX_THROUGHPUT == 4_000_000

    @pytest.mark.asyncio
    async def test_fetch_success(self, collector):
        """Test successful HTML fetch."""
        mock_response = MagicMock()
        mock_response.text = SAMPLE_TSA_HTML
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(collector, 'get_client', return_value=mock_client):
            result = await collector.fetch()

        assert result == SAMPLE_TSA_HTML
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_http_error(self, collector):
        """Test fetch handles HTTP errors."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.reason_phrase = "Service Unavailable"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "503 error",
                request=MagicMock(),
                response=mock_response
            )
        )

        with patch.object(collector, 'get_client', return_value=mock_client):
            with pytest.raises(FetchError) as exc_info:
                await collector.fetch()

        assert "503" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_parse_success(self, collector):
        """Test successful HTML parsing."""
        records = await collector.parse(SAMPLE_TSA_HTML)

        assert len(records) == 3

        # Check first record
        record = records[0]
        assert record["date"] == date(2024, 1, 15)
        assert record["current_year_throughput"] == 2_500_000
        assert record["prior_year_throughput"] == 2_300_000
        assert record["yoy_change_pct"] is not None
        assert record["day_of_week"] == 0  # Monday

    @pytest.mark.asyncio
    async def test_parse_with_missing_prior_year(self, collector):
        """Test parsing handles missing prior year data."""
        records = await collector.parse(SAMPLE_TSA_HTML_WITH_MISSING)

        assert len(records) == 2

        for record in records:
            assert record["prior_year_throughput"] is None
            assert record["yoy_change_pct"] is None

    @pytest.mark.asyncio
    async def test_parse_empty_table(self, collector):
        """Test parsing handles missing table."""
        with pytest.raises(ParseError) as exc_info:
            await collector.parse(SAMPLE_TSA_HTML_EMPTY)

        assert "table" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_throughput_range(self, collector):
        """Test throughput values are validated within range."""
        records = [
            {
                "date": date(2024, 1, 15),
                "current_year_throughput": 2_500_000,  # Valid
                "prior_year_throughput": 2_300_000,
                "yoy_change_pct": Decimal("8.7"),
                "day_of_week": 0,
                "is_holiday_period": False,
            },
            {
                "date": date(2024, 1, 14),
                "current_year_throughput": 500_000,  # Below minimum
                "prior_year_throughput": 2_300_000,
                "yoy_change_pct": Decimal("-78.3"),
                "day_of_week": 6,
                "is_holiday_period": False,
            },
            {
                "date": date(2024, 1, 13),
                "current_year_throughput": 5_000_000,  # Above maximum
                "prior_year_throughput": 2_300_000,
                "yoy_change_pct": Decimal("117.4"),
                "day_of_week": 5,
                "is_holiday_period": False,
            },
        ]

        valid_records = await collector.validate(records)

        assert len(valid_records) == 3

        # Check quality scores reflect validation issues
        assert valid_records[0]["data_quality_score"] == Decimal("1.0")
        assert valid_records[1]["data_quality_score"] < Decimal("1.0")
        assert valid_records[2]["data_quality_score"] < Decimal("1.0")

    @pytest.mark.asyncio
    async def test_validate_no_duplicates(self, collector):
        """Test duplicate dates are filtered out."""
        records = [
            {
                "date": date(2024, 1, 15),
                "current_year_throughput": 2_500_000,
                "prior_year_throughput": 2_300_000,
                "yoy_change_pct": Decimal("8.7"),
                "day_of_week": 0,
                "is_holiday_period": False,
            },
            {
                "date": date(2024, 1, 15),  # Duplicate
                "current_year_throughput": 2_500_001,
                "prior_year_throughput": 2_300_000,
                "yoy_change_pct": Decimal("8.7"),
                "day_of_week": 0,
                "is_holiday_period": False,
            },
        ]

        valid_records = await collector.validate(records)

        assert len(valid_records) == 1

    @pytest.mark.asyncio
    async def test_validate_no_future_dates(self, collector):
        """Test future dates are filtered out."""
        from datetime import timedelta

        future_date = date.today() + timedelta(days=1)

        records = [
            {
                "date": date(2024, 1, 15),
                "current_year_throughput": 2_500_000,
                "prior_year_throughput": 2_300_000,
                "yoy_change_pct": Decimal("8.7"),
                "day_of_week": 0,
                "is_holiday_period": False,
            },
            {
                "date": future_date,  # Future date
                "current_year_throughput": 2_600_000,
                "prior_year_throughput": 2_400_000,
                "yoy_change_pct": Decimal("8.3"),
                "day_of_week": 1,
                "is_holiday_period": False,
            },
        ]

        valid_records = await collector.validate(records)

        assert len(valid_records) == 1
        assert valid_records[0]["date"] == date(2024, 1, 15)

    def test_parse_date_formats(self, collector):
        """Test various date format parsing."""
        # MM/DD/YYYY
        assert collector._parse_date("1/15/2024") == date(2024, 1, 15)
        assert collector._parse_date("01/15/2024") == date(2024, 1, 15)

        # MM/DD/YY
        assert collector._parse_date("1/15/24") == date(2024, 1, 15)

        # Month name formats
        assert collector._parse_date("January 15, 2024") == date(2024, 1, 15)
        assert collector._parse_date("Jan 15, 2024") == date(2024, 1, 15)

        # ISO format
        assert collector._parse_date("2024-01-15") == date(2024, 1, 15)

        # Invalid formats
        assert collector._parse_date("invalid") is None
        assert collector._parse_date("") is None

    def test_parse_number_formats(self, collector):
        """Test number parsing with various formats."""
        # With commas
        assert collector._parse_number("2,500,000") == 2_500_000

        # Without commas
        assert collector._parse_number("2500000") == 2_500_000

        # With spaces
        assert collector._parse_number("2 500 000") == 2_500_000

        # Missing/invalid values
        assert collector._parse_number("N/A") is None
        assert collector._parse_number("-") is None
        assert collector._parse_number("") is None
        assert collector._parse_number("   ") is None

    def test_yoy_change_calculation(self, collector):
        """Test YoY change percentage calculation."""
        cells = [
            MagicMock(get_text=MagicMock(return_value="1/15/2024")),
            MagicMock(get_text=MagicMock(return_value="2,500,000")),
            MagicMock(get_text=MagicMock(return_value="2,300,000")),
        ]

        record = collector._parse_row(cells)

        assert record is not None
        # YoY change: (2500000 - 2300000) / 2300000 * 100 = 8.6957%
        expected_yoy = Decimal("8.6957")
        assert abs(record["yoy_change_pct"] - expected_yoy) < Decimal("0.001")


class TestTSACheckpointCollectorIntegration:
    """Integration tests for TSA Checkpoint collector with database."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return TSACheckpointCollector()

    @pytest_asyncio.fixture
    async def populated_db(self, db_session):
        """Populate database with sample TSA data."""
        from src.models.data_sources import TSACheckpoint

        records = [
            TSACheckpoint(
                date=date(2024, 1, 15),
                current_year_throughput=2_500_000,
                prior_year_throughput=2_300_000,
                yoy_change_pct=Decimal("8.6957"),
                day_of_week=0,
                is_holiday_period=False,
                data_quality_score=Decimal("1.0"),
            ),
            TSACheckpoint(
                date=date(2024, 1, 14),
                current_year_throughput=2_600_000,
                prior_year_throughput=2_400_000,
                yoy_change_pct=Decimal("8.3333"),
                day_of_week=6,
                is_holiday_period=False,
                data_quality_score=Decimal("1.0"),
            ),
            TSACheckpoint(
                date=date(2024, 1, 13),
                current_year_throughput=2_400_000,
                prior_year_throughput=2_200_000,
                yoy_change_pct=Decimal("9.0909"),
                day_of_week=5,
                is_holiday_period=False,
                data_quality_score=Decimal("1.0"),
            ),
        ]

        for record in records:
            db_session.add(record)
        await db_session.commit()

        return db_session

    @pytest.mark.asyncio
    async def test_check_data_gaps(self, collector, populated_db):
        """Test data gap detection."""
        with patch('src.collectors.tsa_checkpoint.get_async_session') as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=populated_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            # Check for gaps between 1/10 and 1/15
            gaps = await collector.check_data_gaps(
                start_date=date(2024, 1, 10),
                end_date=date(2024, 1, 15),
            )

            # Should have gaps for 1/10, 1/11, 1/12
            assert len(gaps) == 3
            assert date(2024, 1, 10) in gaps
            assert date(2024, 1, 11) in gaps
            assert date(2024, 1, 12) in gaps


class TestTSACheckpointCollectorEdgeCases:
    """Edge case tests for TSA Checkpoint collector."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return TSACheckpointCollector()

    @pytest.mark.asyncio
    async def test_parse_malformed_html(self, collector):
        """Test parsing handles malformed HTML."""
        malformed_html = """
        <table>
            <tr><td>Bad data</td></tr>
            <tr><td>More bad</td><td>data</td></tr>
        </table>
        """

        # Should not raise, but return empty or minimal results
        with pytest.raises(ParseError):
            await collector.parse(malformed_html)

    @pytest.mark.asyncio
    async def test_validate_empty_records(self, collector):
        """Test validation handles empty record list."""
        valid_records = await collector.validate([])

        assert valid_records == []

    @pytest.mark.asyncio
    async def test_store_empty_records(self, collector):
        """Test store handles empty record list."""
        count = await collector.store([])

        assert count == 0

    def test_parse_row_incomplete_cells(self, collector):
        """Test row parsing with incomplete cells."""
        # Only 2 cells (missing prior year)
        cells = [
            MagicMock(get_text=MagicMock(return_value="1/15/2024")),
            MagicMock(get_text=MagicMock(return_value="2,500,000")),
        ]

        record = collector._parse_row(cells)

        assert record is not None
        assert record["prior_year_throughput"] is None

    def test_parse_row_invalid_date(self, collector):
        """Test row parsing with invalid date."""
        cells = [
            MagicMock(get_text=MagicMock(return_value="not-a-date")),
            MagicMock(get_text=MagicMock(return_value="2,500,000")),
            MagicMock(get_text=MagicMock(return_value="2,300,000")),
        ]

        record = collector._parse_row(cells)

        assert record is None

    def test_parse_row_invalid_throughput(self, collector):
        """Test row parsing with invalid throughput."""
        cells = [
            MagicMock(get_text=MagicMock(return_value="1/15/2024")),
            MagicMock(get_text=MagicMock(return_value="not-a-number")),
            MagicMock(get_text=MagicMock(return_value="2,300,000")),
        ]

        record = collector._parse_row(cells)

        assert record is None


class TestTSACheckpointCollectorBackfill:
    """Tests for TSA Checkpoint collector backfill functionality."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return TSACheckpointCollector()

    @pytest.mark.asyncio
    async def test_backfill_adjusts_start_date(self, collector):
        """Test backfill adjusts start date if before 2019."""
        mock_response = MagicMock()
        mock_response.text = SAMPLE_TSA_HTML
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()

        with patch.object(collector, 'get_client', return_value=mock_client):
            with patch.object(collector, 'store', return_value=3):
                results = await collector.backfill(
                    start_date=date(2018, 1, 1),  # Before 2019
                    end_date=date(2024, 1, 15),
                )

        assert len(results) == 1
        assert results[0].success is True

    @pytest.mark.asyncio
    async def test_backfill_filters_date_range(self, collector):
        """Test backfill filters records to specified date range."""
        mock_response = MagicMock()
        mock_response.text = SAMPLE_TSA_HTML
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()

        with patch.object(collector, 'get_client', return_value=mock_client):
            with patch.object(collector, 'store', return_value=2) as mock_store:
                results = await collector.backfill(
                    start_date=date(2024, 1, 14),
                    end_date=date(2024, 1, 15),
                )

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].records_fetched == 2  # Only 2 dates in range
