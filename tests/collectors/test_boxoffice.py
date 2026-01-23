"""Unit tests for box office collector."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import Response

from src.collectors.boxoffice import BoxOfficeCollector
from src.collectors.base import FetchError, ParseError
from src.models.data_sources import BoxOfficeDaily


# Sample HTML response from The Numbers
SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Daily Box Office Chart for Tuesday, January 14, 2025</title>
</head>
<body>
<table id="box_office_daily_table">
    <tr>
        <th>Rank</th>
        <th>Movie</th>
        <th>Distributor</th>
        <th>Daily Gross</th>
        <th>Theaters</th>
        <th>Per Theater</th>
        <th>Total Gross</th>
        <th>Days</th>
    </tr>
    <tr>
        <td>1</td>
        <td><a href="/movie/Mufasa-The-Lion-King-(2024)">Mufasa: The Lion King</a></td>
        <td><a href="/studio/Walt-Disney">Walt Disney</a></td>
        <td>$4,250,000</td>
        <td>4,100</td>
        <td>$1,037</td>
        <td>$185,500,000</td>
        <td>25</td>
    </tr>
    <tr>
        <td>2</td>
        <td><a href="/movie/Sonic-3-(2024)">Sonic the Hedgehog 3</a></td>
        <td><a href="/studio/Paramount">Paramount</a></td>
        <td>$3,100,000</td>
        <td>3,800</td>
        <td>$816</td>
        <td>$142,000,000</td>
        <td>24</td>
    </tr>
    <tr>
        <td>3</td>
        <td><a href="/movie/Nosferatu-(2024)">Nosferatu</a></td>
        <td><a href="/studio/Universal">Universal</a></td>
        <td>$2,800,000</td>
        <td>2,900</td>
        <td>$966</td>
        <td>$45,000,000</td>
        <td>18</td>
    </tr>
</table>
</body>
</html>
"""

SAMPLE_OPENING_WEEKEND_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Daily Box Office Chart for Friday, January 17, 2025</title>
</head>
<body>
<table class="data">
    <tr>
        <th>Movie</th>
        <th>Distributor</th>
        <th>Gross</th>
        <th>Theaters</th>
        <th>Total</th>
        <th>Days</th>
    </tr>
    <tr>
        <td><a href="/movie/New-Movie">New Movie</a></td>
        <td><a href="/studio/Sony">Sony</a></td>
        <td>$25,000,000</td>
        <td>4,200</td>
        <td>$25,000,000</td>
        <td>1</td>
    </tr>
</table>
</body>
</html>
"""


class TestBoxOfficeCollector:
    """Tests for BoxOfficeCollector class."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return BoxOfficeCollector()

    def test_collector_initialization(self, collector):
        """Test collector is properly initialized."""
        assert collector.name == "boxoffice"
        assert collector.source_id == 6
        assert collector.update_frequency == "daily"
        assert collector.BACKFILL_START_DATE == date(1995, 1, 1)

    @pytest.mark.asyncio
    async def test_fetch_success(self, collector):
        """Test successful fetch returns HTML."""
        mock_response = MagicMock(spec=Response)
        mock_response.text = SAMPLE_HTML
        mock_response.raise_for_status = MagicMock()

        with patch.object(collector, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await collector.fetch(target_date=date(2025, 1, 14))

            assert result == SAMPLE_HTML
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_http_error(self, collector):
        """Test fetch raises FetchError on HTTP error."""
        import httpx

        with patch.object(collector, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Not Found",
                    request=MagicMock(),
                    response=mock_response
                )
            )
            mock_get_client.return_value = mock_client

            with pytest.raises(FetchError):
                await collector.fetch(target_date=date(2025, 1, 14))

    @pytest.mark.asyncio
    async def test_parse_daily_chart(self, collector):
        """Test parsing daily box office chart."""
        records = await collector.parse(SAMPLE_HTML)

        assert len(records) == 3

        # Check first record (Disney movie)
        record = records[0]
        assert record["movie_title"] == "Mufasa: The Lion King"
        assert record["distributor"] == "Walt Disney"
        assert record["distributor_ticker"] == "DIS"
        assert record["daily_gross"] == Decimal("4250000")
        assert record["theater_count"] == 4100
        assert record["cumulative_gross"] == Decimal("185500000")
        assert record["days_in_release"] == 25
        assert record["rank"] == 1

        # Check second record (Paramount movie)
        record = records[1]
        assert record["movie_title"] == "Sonic the Hedgehog 3"
        assert record["distributor_ticker"] == "PARA"
        assert record["daily_gross"] == Decimal("3100000")

        # Check third record (Universal movie)
        record = records[2]
        assert record["movie_title"] == "Nosferatu"
        assert record["distributor_ticker"] == "CMCSA"

    @pytest.mark.asyncio
    async def test_parse_opening_weekend(self, collector):
        """Test parsing with opening weekend detection."""
        records = await collector.parse(SAMPLE_OPENING_WEEKEND_HTML)

        assert len(records) >= 1
        record = records[0]
        assert record["movie_title"] == "New Movie"
        assert record["distributor_ticker"] == "SONY"
        assert record["days_in_release"] == 1
        # Opening weekend flag depends on the date being Friday-Sunday

    @pytest.mark.asyncio
    async def test_parse_empty_html(self, collector):
        """Test parsing empty or invalid HTML returns empty list."""
        records = await collector.parse("<html><body>No data</body></html>")
        assert records == []

    @pytest.mark.asyncio
    async def test_validate_positive_gross(self, collector):
        """Test validation ensures gross values are positive."""
        records = [
            {
                "movie_title": "Good Movie",
                "daily_gross": Decimal("1000000"),
                "theater_count": 3000,
            },
            {
                "movie_title": "Bad Movie",
                "daily_gross": Decimal("-500000"),  # Invalid
                "theater_count": 2000,
            },
        ]

        valid_records = await collector.validate(records)

        assert len(valid_records) == 1
        assert valid_records[0]["movie_title"] == "Good Movie"

    @pytest.mark.asyncio
    async def test_validate_positive_theaters(self, collector):
        """Test validation ensures theater count is positive."""
        records = [
            {
                "movie_title": "Good Movie",
                "daily_gross": Decimal("1000000"),
                "theater_count": 3000,
            },
            {
                "movie_title": "Bad Movie",
                "daily_gross": Decimal("500000"),
                "theater_count": 0,  # Invalid
            },
        ]

        valid_records = await collector.validate(records)

        assert len(valid_records) == 1
        assert valid_records[0]["movie_title"] == "Good Movie"

    @pytest.mark.asyncio
    async def test_validate_requires_title(self, collector):
        """Test validation requires movie title."""
        records = [
            {
                "movie_title": "Good Movie",
                "daily_gross": Decimal("1000000"),
                "theater_count": 3000,
            },
            {
                "movie_title": "",  # Invalid
                "daily_gross": Decimal("500000"),
                "theater_count": 2000,
            },
        ]

        valid_records = await collector.validate(records)

        assert len(valid_records) == 1
        assert valid_records[0]["movie_title"] == "Good Movie"

    def test_parse_money(self, collector):
        """Test money parsing."""
        assert collector._parse_money("$4,250,000") == Decimal("4250000")
        assert collector._parse_money("$1,037") == Decimal("1037")
        assert collector._parse_money("$185,500,000") == Decimal("185500000")
        assert collector._parse_money("($500,000)") == Decimal("-500000")
        assert collector._parse_money("invalid") is None

    def test_extract_date_from_page(self, collector):
        """Test date extraction from page."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
        extracted_date = collector._extract_date_from_page(soup)

        assert extracted_date == date(2025, 1, 14)


class TestBoxOfficeDataFreshness:
    """Tests for data freshness validation."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return BoxOfficeCollector()

    @pytest.mark.asyncio
    async def test_daily_data_freshness(self, collector):
        """Test that collector targets recent daily data."""
        # Default fetch should target yesterday
        target_date = date.today() - timedelta(days=1)

        with patch.object(collector, 'get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.text = SAMPLE_HTML
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            await collector.fetch()

            # Verify the URL contains yesterday's date
            call_args = mock_client.get.call_args
            url = call_args[0][0]
            assert str(target_date.year) in url
            assert f"{target_date.month:02d}" in url
            assert f"{target_date.day:02d}" in url


class TestBoxOfficeBackfill:
    """Tests for historical backfill functionality."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return BoxOfficeCollector()

    @pytest.mark.asyncio
    async def test_backfill_enforces_minimum_date(self, collector):
        """Test backfill enforces minimum start date."""
        # Try to backfill from before 1995
        start_date = date(1990, 1, 1)
        end_date = date(1995, 1, 5)

        with patch.object(collector, 'collect') as mock_collect:
            mock_collect.return_value = MagicMock(success=True)

            results = await collector.backfill(
                start_date=start_date,
                end_date=end_date,
                delay_seconds=0,
            )

            # Should start from 1995-01-01, not 1990
            first_call_date = mock_collect.call_args_list[0][1]['target_date']
            assert first_call_date >= date(1995, 1, 1)

    @pytest.mark.asyncio
    async def test_backfill_date_range(self, collector):
        """Test backfill processes correct date range."""
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 3)

        with patch.object(collector, 'collect') as mock_collect:
            mock_collect.return_value = MagicMock(success=True)

            results = await collector.backfill(
                start_date=start_date,
                end_date=end_date,
                delay_seconds=0,
            )

            # Should have 3 results (Jan 1, 2, 3)
            assert len(results) == 3
            assert mock_collect.call_count == 3


class TestBoxOfficeStoreIntegration:
    """Integration tests for database storage."""

    @pytest_asyncio.fixture
    async def db_collector(self, db_session):
        """Create collector with test database session."""
        collector = BoxOfficeCollector()
        return collector

    @pytest.mark.asyncio
    async def test_store_records(self, db_session, db_collector):
        """Test storing records to database."""
        records = [
            {
                "date": date(2025, 1, 14),
                "movie_title": "Test Movie",
                "distributor": "Walt Disney",
                "distributor_ticker": "DIS",
                "daily_gross": Decimal("5000000"),
                "cumulative_gross": Decimal("50000000"),
                "theater_count": 4000,
                "per_theater_avg": Decimal("1250"),
                "days_in_release": 10,
                "rank": 1,
                "is_opening_weekend": False,
            }
        ]

        # Mock the database session
        with patch('src.collectors.boxoffice.get_async_session') as mock_session:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.return_value = db_session
            mock_ctx.__aexit__.return_value = None
            mock_session.return_value = mock_ctx

            stored = await db_collector.store(records)

            # Note: Full integration test would verify database state
            # This test verifies the store method runs without error
            assert stored >= 0
