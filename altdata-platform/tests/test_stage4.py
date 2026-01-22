"""Stage 4 Tests: FRED collector verification."""

import pytest
from datetime import datetime


def test_parse_fred_response(sample_fred_response):
    """Test FRED API response parsing."""
    from src.collectors.fred import FREDCollector

    collector = FREDCollector(api_key="test_key")
    result = collector.parse_series_response(sample_fred_response, series_id="GS10")

    assert len(result) == 5
    assert result[0]["series_id"] == "GS10"
    assert result[0]["value"] == 4.12
    assert isinstance(result[0]["date"], datetime)


def test_parse_fred_response_with_missing_values():
    """Test FRED response parsing handles missing values."""
    from src.collectors.fred import FREDCollector

    response = {
        "observations": [
            {"date": "2024-01-19", "value": "4.12"},
            {"date": "2024-01-20", "value": "."},  # Missing value marker
            {"date": "2024-01-21", "value": ""},  # Empty value
            {"date": "2024-01-22", "value": "4.15"},
        ]
    }

    collector = FREDCollector(api_key="test_key")
    result = collector.parse_series_response(response, series_id="GS10")

    # Should only have 2 valid observations
    assert len(result) == 2
    assert result[0]["value"] == 4.12
    assert result[1]["value"] == 4.15


def test_fred_series_configured():
    """Test that key FRED series are configured."""
    from src.collectors.fred import FRED_SERIES

    # Essential series should be present
    assert "GS10" in FRED_SERIES  # 10Y Treasury
    assert "GS2" in FRED_SERIES  # 2Y Treasury
    assert "BAA10Y" in FRED_SERIES  # Credit spread
    assert "ICSA" in FRED_SERIES  # Jobless claims
    assert "T10YIE" in FRED_SERIES  # Inflation expectations


def test_collector_source_name():
    """Test source name is correct."""
    from src.collectors.fred import FREDCollector

    collector = FREDCollector(api_key="test_key")
    assert collector.SOURCE_NAME == "fred"


def test_collector_rate_limit():
    """Test rate limit configuration."""
    from src.collectors.fred import FREDCollector

    collector = FREDCollector(api_key="test_key", rate_limit=5.0)
    assert collector.rate_limiter.min_interval == 0.2


def test_collector_without_api_key():
    """Test collector handles missing API key."""
    from src.collectors.fred import FREDCollector, CollectorError
    import os

    # Temporarily clear the API key
    old_key = os.environ.get("FRED_API_KEY")
    os.environ["FRED_API_KEY"] = ""

    try:
        collector = FREDCollector()
        # Should not raise during init
        assert collector.api_key == "" or collector.api_key is None
    finally:
        if old_key:
            os.environ["FRED_API_KEY"] = old_key


def test_parse_multiple_series():
    """Test parsing multiple series at once."""
    from src.collectors.fred import FREDCollector

    raw_data = {
        "GS10": {
            "observations": [
                {"date": "2024-01-22", "value": "4.15"},
                {"date": "2024-01-23", "value": "4.10"},
            ]
        },
        "GS2": {
            "observations": [
                {"date": "2024-01-22", "value": "4.35"},
                {"date": "2024-01-23", "value": "4.30"},
            ]
        }
    }

    collector = FREDCollector(api_key="test_key")
    result = collector.parse(raw_data)

    assert len(result) == 4
    gs10_obs = [r for r in result if r["series_id"] == "GS10"]
    gs2_obs = [r for r in result if r["series_id"] == "GS2"]
    assert len(gs10_obs) == 2
    assert len(gs2_obs) == 2


def test_yield_curve_data_structure():
    """Test that yield curve data can be used for slope calculation."""
    from src.collectors.fred import FREDCollector

    raw_data = {
        "GS10": {
            "observations": [
                {"date": "2024-01-22", "value": "4.50"},
            ]
        },
        "GS2": {
            "observations": [
                {"date": "2024-01-22", "value": "4.20"},
            ]
        }
    }

    collector = FREDCollector(api_key="test_key")
    result = collector.parse(raw_data)

    gs10 = next(r for r in result if r["series_id"] == "GS10")
    gs2 = next(r for r in result if r["series_id"] == "GS2")

    # Yield curve slope calculation
    slope = gs10["value"] - gs2["value"]
    assert slope == pytest.approx(0.30)  # 4.50 - 4.20


@pytest.mark.asyncio
async def test_collector_context_manager():
    """Test async context manager."""
    from src.collectors.fred import FREDCollector

    async with FREDCollector(api_key="test_key") as collector:
        assert collector is not None
        assert collector.SOURCE_NAME == "fred"


def test_get_series_data_query():
    """Test series data retrieval from database."""
    from src.collectors.fred import FREDCollector
    from src.models.database import SessionLocal
    from src.models.schemas import FREDSeries
    from datetime import datetime

    session = SessionLocal()
    try:
        # Insert test data
        test_obs = FREDSeries(
            series_id="TEST_SERIES",
            observation_date=datetime(2024, 1, 15),
            value=99.99,
        )
        session.add(test_obs)
        session.commit()

        # Query using collector
        collector = FREDCollector(api_key="test_key")
        data = collector.get_series_data("TEST_SERIES")

        assert len(data) == 1
        assert data[0]["value"] == 99.99

        # Cleanup
        session.delete(test_obs)
        session.commit()
    finally:
        session.close()


def test_get_latest_value():
    """Test getting latest value for a series."""
    from src.collectors.fred import FREDCollector
    from src.models.database import SessionLocal
    from src.models.schemas import FREDSeries
    from datetime import datetime

    session = SessionLocal()
    try:
        # Insert test data
        obs1 = FREDSeries(
            series_id="LATEST_TEST",
            observation_date=datetime(2024, 1, 10),
            value=100.0,
        )
        obs2 = FREDSeries(
            series_id="LATEST_TEST",
            observation_date=datetime(2024, 1, 15),
            value=105.0,
        )
        session.add_all([obs1, obs2])
        session.commit()

        # Get latest
        collector = FREDCollector(api_key="test_key")
        latest = collector.get_latest_value("LATEST_TEST")

        assert latest == 105.0  # Should be the Jan 15 value

        # Cleanup
        session.query(FREDSeries).filter_by(series_id="LATEST_TEST").delete()
        session.commit()
    finally:
        session.close()
