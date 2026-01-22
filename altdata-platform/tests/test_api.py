"""Tests for Alternative Data Platform API endpoints."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


# =============================================================================
# Test Setup
# =============================================================================

@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch("src.api.main.settings") as mock:
        mock.is_development = True
        mock.redis_url = "redis://localhost:6379"
        mock.api_key_admin = "test-admin-key"
        mock.api_key_default = "test-key"
        yield mock


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    with patch("src.api.main.SessionLocal") as mock:
        session = MagicMock()
        mock.return_value = session
        yield session


@pytest.fixture
def mock_db_check():
    """Mock database connection check."""
    with patch("src.api.main.check_database_connection") as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def client(mock_settings, mock_db_check):
    """Create test client."""
    from src.api.main import app
    return TestClient(app)


# =============================================================================
# Health Check Tests
# =============================================================================

class TestHealthCheck:
    """Test health check endpoint."""

    def test_health_check_returns_200(self, client):
        """Test health endpoint returns 200."""
        with patch("src.api.main.get_redis") as mock_redis:
            mock_redis.return_value = None
            response = client.get("/health")
            assert response.status_code == 200

    def test_health_check_response_fields(self, client):
        """Test health response contains required fields."""
        with patch("src.api.main.get_redis") as mock_redis:
            mock_redis.return_value = None
            response = client.get("/health")
            data = response.json()
            assert "status" in data
            assert "timestamp" in data
            assert "database" in data
            assert "redis" in data
            assert "version" in data


# =============================================================================
# Factors API Tests
# =============================================================================

class TestFactorsAPI:
    """Test factors endpoints."""

    def test_list_factors(self, client, mock_db_session):
        """Test listing all factors."""
        response = client.get("/api/v1/factors")
        assert response.status_code == 200
        data = response.json()
        assert "factors" in data
        assert "total" in data
        assert data["total"] > 0

    def test_list_factors_by_category(self, client, mock_db_session):
        """Test filtering factors by category."""
        response = client.get("/api/v1/factors?category=weather")
        assert response.status_code == 200
        data = response.json()
        assert "factors" in data
        for f in data["factors"]:
            assert f["category"] == "weather"

    def test_get_factor_not_found(self, client, mock_db_session):
        """Test getting non-existent factor."""
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        response = client.get("/api/v1/factors/nonexistent_factor?entity_id=TEST")
        assert response.status_code == 404

    def test_list_categories(self, client):
        """Test listing factor categories."""
        response = client.get("/api/v1/categories")
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        # Should include Phase 2 categories
        category_ids = [c["id"] for c in data["categories"]]
        assert "weather" in category_ids
        assert "satellite" in category_ids


# =============================================================================
# Sources API Tests
# =============================================================================

class TestSourcesAPI:
    """Test sources endpoint."""

    def test_list_sources(self, client):
        """Test listing data sources."""
        response = client.get("/api/v1/sources")
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data

        source_ids = [s["id"] for s in data["sources"]]
        # Phase 1 sources
        assert "sec_edgar" in source_ids
        assert "fred" in source_ids
        # Phase 2 sources
        assert "openweathermap" in source_ids
        assert "google_trends" in source_ids
        assert "reddit" in source_ids
        assert "marine_traffic" in source_ids
        assert "github" in source_ids
        assert "sentinel" in source_ids

    def test_sources_have_factors(self, client):
        """Test each source lists its factors."""
        response = client.get("/api/v1/sources")
        data = response.json()
        for source in data["sources"]:
            assert "factors" in source
            assert len(source["factors"]) > 0


# =============================================================================
# Weather API Tests
# =============================================================================

class TestWeatherAPI:
    """Test weather endpoints."""

    def test_get_weather_observations(self, client, mock_db_session):
        """Test getting weather observations."""
        mock_observation = MagicMock()
        mock_observation.city = "New York"
        mock_observation.timestamp = datetime(2024, 6, 15, 12, 0, 0)
        mock_observation.temp_c = 25.0
        mock_observation.temp_feels_like_c = 27.0
        mock_observation.humidity_pct = 65
        mock_observation.wind_speed_ms = 5.0
        mock_observation.weather_main = "Clear"
        mock_observation.pressure_hpa = 1013

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_observation]

        response = client.get("/api/v1/weather/observations?city=New York&date=2024-06-15")
        assert response.status_code == 200
        data = response.json()
        assert data["city"] == "New York"
        assert "observations" in data

    def test_get_weather_forecast(self, client, mock_db_session):
        """Test getting weather forecast."""
        mock_forecast = MagicMock()
        mock_forecast.city = "Chicago"
        mock_forecast.forecast_timestamp = datetime(2024, 6, 16, 12, 0, 0)
        mock_forecast.temp_c = 23.0
        mock_forecast.humidity_pct = 55
        mock_forecast.wind_speed_ms = 4.0
        mock_forecast.weather_main = "Partly Cloudy"
        mock_forecast.pop = 0.2

        # Chain: query().filter().order_by().all()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_forecast]
        mock_db_session.query.return_value = mock_query

        response = client.get("/api/v1/weather/forecast?city=Chicago&days=7")
        assert response.status_code == 200
        data = response.json()
        assert data["city"] == "Chicago"
        assert "forecasts" in data


# =============================================================================
# Trends API Tests
# =============================================================================

class TestTrendsAPI:
    """Test Google Trends endpoints."""

    def test_get_trend_interest(self, client, mock_db_session):
        """Test getting trend interest data."""
        mock_interest = MagicMock()
        mock_interest.keyword = "iPhone"
        mock_interest.date = date(2024, 6, 15)
        mock_interest.interest = 75
        mock_interest.is_partial = False
        mock_interest.geo = "US"

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_interest]
        mock_db_session.query.return_value = mock_query

        response = client.get("/api/v1/trends/interest?keyword=iPhone")
        assert response.status_code == 200
        data = response.json()
        assert data["keyword"] == "iPhone"
        assert "data" in data

    def test_get_trend_interest_no_keyword(self, client, mock_db_session):
        """Test trend interest returns empty for unknown keyword."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        response = client.get("/api/v1/trends/interest?keyword=unknownxyz123")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0


# =============================================================================
# Sentiment API Tests
# =============================================================================

class TestSentimentAPI:
    """Test sentiment endpoints."""

    def test_get_ticker_sentiment(self, client, mock_db_session):
        """Test getting ticker sentiment."""
        mock_sentiment = MagicMock()
        mock_sentiment.ticker = "AAPL"
        mock_sentiment.date = date(2024, 6, 15)
        mock_sentiment.avg_sentiment = 0.65
        mock_sentiment.mention_count = 150
        mock_sentiment.positive_mentions = 85
        mock_sentiment.negative_mentions = 25
        mock_sentiment.neutral_mentions = 40

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_sentiment]

        response = client.get("/api/v1/sentiment/ticker?ticker=AAPL")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert "data" in data

    def test_get_ticker_sentiment_with_date_range(self, client, mock_db_session):
        """Test filtering sentiment by date range."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_db_session.query.return_value = mock_query

        response = client.get("/api/v1/sentiment/ticker?ticker=GME&start_date=2024-06-01&end_date=2024-06-15")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "GME"


# =============================================================================
# Shipping API Tests
# =============================================================================

class TestShippingAPI:
    """Test shipping endpoints."""

    def test_list_ports(self, client, mock_db_session):
        """Test listing ports."""
        mock_port = MagicMock()
        mock_port.port_id = "USLAX"
        mock_port.port_name = "Los Angeles"
        mock_port.country = "US"
        mock_port.latitude = 33.74
        mock_port.longitude = -118.27
        mock_port.port_type = "container"

        mock_db_session.query.return_value.all.return_value = [mock_port]

        response = client.get("/api/v1/shipping/ports")
        assert response.status_code == 200
        data = response.json()
        assert "ports" in data
        assert data["total"] >= 0

    def test_list_ports_by_country(self, client, mock_db_session):
        """Test filtering ports by country."""
        mock_db_session.query.return_value.filter.return_value.all.return_value = []

        response = client.get("/api/v1/shipping/ports?country=US")
        assert response.status_code == 200

    def test_get_port_congestion(self, client, mock_db_session):
        """Test getting port congestion data."""
        mock_congestion = MagicMock()
        mock_congestion.port_id = "USLAX"
        mock_congestion.port = MagicMock()
        mock_congestion.port.port_name = "Los Angeles"
        mock_congestion.date = date(2024, 6, 15)
        mock_congestion.congestion_index = 72.5
        mock_congestion.vessels_waiting = 15
        mock_congestion.avg_wait_hours = 48.0

        mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_congestion]

        response = client.get("/api/v1/shipping/congestion?date=2024-06-15")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data


# =============================================================================
# GitHub API Tests
# =============================================================================

class TestGitHubAPI:
    """Test GitHub endpoints."""

    def test_list_repos(self, client, mock_db_session):
        """Test listing GitHub repos."""
        mock_repo = MagicMock()
        mock_repo.full_name = "facebook/react"
        mock_repo.company = "Meta"
        mock_repo.ticker = "META"
        mock_repo.language = "JavaScript"

        mock_db_session.query.return_value.all.return_value = [mock_repo]

        response = client.get("/api/v1/github/repos")
        assert response.status_code == 200
        data = response.json()
        assert "repos" in data

    def test_list_repos_by_ticker(self, client, mock_db_session):
        """Test filtering repos by ticker."""
        mock_db_session.query.return_value.filter.return_value.all.return_value = []

        response = client.get("/api/v1/github/repos?ticker=MSFT")
        assert response.status_code == 200

    def test_get_github_activity(self, client, mock_db_session):
        """Test getting GitHub activity."""
        mock_activity = MagicMock()
        mock_activity.full_name = "microsoft/vscode"
        mock_activity.date = date(2024, 6, 15)
        mock_activity.commits_24h = 50
        mock_activity.prs_opened_24h = 20
        mock_activity.prs_merged_24h = 15
        mock_activity.issues_opened_24h = 30
        mock_activity.unique_committers_24h = 25

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_activity]
        mock_db_session.query.return_value = mock_query

        response = client.get("/api/v1/github/activity?repo=microsoft/vscode")
        assert response.status_code == 200
        data = response.json()
        assert data["repo"] == "microsoft/vscode"
        assert "data" in data


# =============================================================================
# Satellite API Tests
# =============================================================================

class TestSatelliteAPI:
    """Test satellite endpoints."""

    def test_get_parking_data(self, client, mock_db_session):
        """Test getting parking data."""
        mock_parking = MagicMock()
        mock_parking.location_id = "walmart_bentonville"
        mock_parking.location = MagicMock()
        mock_parking.location.name = "Walmart HQ"
        mock_parking.ticker = "WMT"
        mock_parking.observation_date = date(2024, 6, 15)
        mock_parking.occupancy_rate = 0.75
        mock_parking.cars_detected = 750
        mock_parking.confidence_score = 0.92

        mock_db_session.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_parking]

        response = client.get("/api/v1/satellite/parking?ticker=WMT")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "WMT"
        assert "data" in data

    def test_get_agricultural_data(self, client, mock_db_session):
        """Test getting agricultural data."""
        mock_agri = MagicMock()
        mock_agri.location_id = "iowa_corn"
        mock_agri.region = "iowa"
        mock_agri.crop_type = "corn"
        mock_agri.observation_date = date(2024, 6, 15)
        mock_agri.ndvi_mean = 0.72
        mock_agri.crop_health_score = 85.0
        mock_agri.ndvi_vs_historical = 5.2

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_agri]

        response = client.get("/api/v1/satellite/agriculture?region=iowa")
        assert response.status_code == 200
        data = response.json()
        assert data["region"] == "iowa"
        assert "data" in data

    def test_get_agricultural_data_with_crop_type(self, client, mock_db_session):
        """Test filtering agricultural data by crop type."""
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        response = client.get("/api/v1/satellite/agriculture?region=california&crop_type=almond")
        assert response.status_code == 200
        data = response.json()
        assert data["crop_type"] == "almond"


# =============================================================================
# API Authentication Tests
# =============================================================================

class TestAPIAuthentication:
    """Test API authentication."""

    def test_development_mode_no_key_required(self, client):
        """Test development mode allows requests without API key."""
        response = client.get("/api/v1/factors")
        # Should work in development mode without API key
        assert response.status_code == 200

    def test_valid_api_key_accepted(self, client):
        """Test valid API key is accepted."""
        response = client.get(
            "/api/v1/factors",
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code == 200


# =============================================================================
# API Response Format Tests
# =============================================================================

class TestAPIResponseFormats:
    """Test API response formats."""

    def test_factor_list_response_format(self, client):
        """Test factor list response format."""
        response = client.get("/api/v1/factors")
        data = response.json()

        assert isinstance(data["factors"], list)
        assert isinstance(data["total"], int)

        if data["factors"]:
            factor = data["factors"][0]
            assert "id" in factor
            assert "name" in factor
            assert "category" in factor
            assert "frequency" in factor

    def test_sources_response_format(self, client):
        """Test sources response format."""
        response = client.get("/api/v1/sources")
        data = response.json()

        assert isinstance(data["sources"], list)

        for source in data["sources"]:
            assert "id" in source
            assert "name" in source
            assert "category" in source
            assert "status" in source
            assert "update_frequency" in source
            assert "factors" in source

    def test_categories_response_format(self, client):
        """Test categories response format."""
        response = client.get("/api/v1/categories")
        data = response.json()

        assert isinstance(data["categories"], list)

        for cat in data["categories"]:
            assert "id" in cat
            assert "name" in cat
            assert "count" in cat
            assert "factors" in cat
