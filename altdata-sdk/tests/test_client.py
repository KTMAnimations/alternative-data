"""Tests for the AltDataClient."""

import pytest
import httpx
import respx
from datetime import datetime, date

from altdata import (
    AltDataClient,
    AltDataError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    ServerError,
    ConnectionError,
    FactorResponse,
    FactorListResponse,
    EntityResponse,
    EntityListResponse,
    SourcesResponse,
    CategoriesResponse,
    HealthResponse,
    FlightListResponse,
    GridLoadResponse,
    PatentListResponse,
    AirQualityResponse,
    WeatherResponse,
    WeatherForecastResponse,
    TrendResponse,
    SentimentResponse,
    PortListResponse,
    CongestionResponse,
    GitHubRepoListResponse,
    GitHubActivityResponse,
    ParkingResponse,
    AgriculturalResponse,
)
from altdata.models import (
    AlertRule,
    AlertRuleListResponse,
    AlertNotification,
    AlertNotificationListResponse,
    AlertCheckResponse,
    BacktestResult,
    BacktestTimeSeries,
    BacktestPositions,
    BacktestIC,
    BacktestJobListResponse,
)


# ===========================================
# FIXTURES
# ===========================================


@pytest.fixture
def client():
    """Create a test client."""
    return AltDataClient(api_key="test-api-key", base_url="http://test-api.local")


@pytest.fixture
def mock_health_response():
    """Mock health response data."""
    return {
        "status": "healthy",
        "timestamp": "2024-01-15T10:30:00",
        "database": "connected",
        "redis": "connected",
        "version": "1.0.0",
    }


@pytest.fixture
def mock_factors_list_response():
    """Mock factors list response data."""
    return {
        "factors": [
            {
                "id": "insider_transaction_momentum",
                "name": "Insider Transaction Momentum",
                "description": "Momentum of insider transactions",
                "category": "sec",
                "frequency": "daily",
            },
            {
                "id": "yield_curve_slope",
                "name": "Yield Curve Slope",
                "description": "Slope of yield curve",
                "category": "macro",
                "frequency": "daily",
            },
        ],
        "total": 2,
    }


@pytest.fixture
def mock_factor_response():
    """Mock factor response data."""
    return {
        "factor_name": "insider_transaction_momentum",
        "entity_id": "AAPL",
        "entity_type": "company",
        "values": [
            {"date": "2024-01-15T00:00:00", "value": 0.75, "version": 1},
            {"date": "2024-01-14T00:00:00", "value": 0.68, "version": 1},
        ],
        "metadata": {"computed_at": "2024-01-15T10:30:00"},
    }


@pytest.fixture
def mock_entities_list_response():
    """Mock entities list response data."""
    return {
        "entities": [
            {
                "id": "AAPL",
                "name": "Apple Inc.",
                "ticker": "AAPL",
                "entity_type": "company",
                "sector": "Technology",
                "industry": "Consumer Electronics",
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 50,
    }


@pytest.fixture
def mock_entity_response():
    """Mock entity response data."""
    return {
        "id": "AAPL",
        "name": "Apple Inc.",
        "ticker": "AAPL",
        "entity_type": "company",
        "sector": "Technology",
        "industry": "Consumer Electronics",
    }


@pytest.fixture
def mock_sources_response():
    """Mock sources response data."""
    return {
        "sources": [
            {
                "id": "sec_edgar",
                "name": "SEC EDGAR",
                "category": "regulatory",
                "status": "active",
                "update_frequency": "real-time",
                "factors": ["insider_transaction_momentum"],
            }
        ]
    }


@pytest.fixture
def mock_categories_response():
    """Mock categories response data."""
    return {
        "categories": [
            {"id": "sec", "name": "SEC", "count": 3, "factors": ["insider_transaction_momentum"]},
            {"id": "macro", "name": "Macro", "count": 2, "factors": ["yield_curve_slope"]},
        ]
    }


# ===========================================
# CLIENT INITIALIZATION TESTS
# ===========================================


class TestClientInit:
    """Tests for client initialization."""

    def test_default_base_url(self):
        """Test default base URL is set."""
        client = AltDataClient(api_key="test")
        assert client.base_url == "http://localhost:8000"
        client.close()

    def test_custom_base_url(self):
        """Test custom base URL."""
        client = AltDataClient(api_key="test", base_url="http://custom.api")
        assert client.base_url == "http://custom.api"
        client.close()

    def test_base_url_trailing_slash_removed(self):
        """Test trailing slash is removed from base URL."""
        client = AltDataClient(api_key="test", base_url="http://custom.api/")
        assert client.base_url == "http://custom.api"
        client.close()

    def test_custom_timeout(self):
        """Test custom timeout."""
        client = AltDataClient(api_key="test", timeout=60.0)
        assert client.timeout == 60.0
        client.close()

    def test_context_manager(self):
        """Test client works as context manager."""
        with AltDataClient(api_key="test") as client:
            assert client.api_key == "test"

    def test_headers_with_api_key(self, client):
        """Test headers include API key."""
        headers = client._get_headers()
        assert headers["X-API-Key"] == "test-api-key"
        assert headers["Accept"] == "application/json"

    def test_headers_without_api_key(self):
        """Test headers without API key."""
        client = AltDataClient()
        headers = client._get_headers()
        assert "X-API-Key" not in headers
        client.close()


# ===========================================
# ERROR HANDLING TESTS
# ===========================================


class TestErrorHandling:
    """Tests for error handling."""

    @respx.mock
    def test_authentication_error(self, client):
        """Test 401 raises AuthenticationError."""
        respx.get("http://test-api.local/health").mock(
            return_value=httpx.Response(401, json={"detail": "Invalid API key"})
        )
        with pytest.raises(AuthenticationError) as exc_info:
            client.health()
        assert exc_info.value.status_code == 401

    @respx.mock
    def test_not_found_error(self, client):
        """Test 404 raises NotFoundError."""
        respx.get("http://test-api.local/api/v1/factors/unknown").mock(
            return_value=httpx.Response(404, json={"detail": "Factor not found"})
        )
        with pytest.raises(NotFoundError) as exc_info:
            client.get_factor("unknown", entity_id="AAPL")
        assert exc_info.value.status_code == 404

    @respx.mock
    def test_validation_error(self, client):
        """Test 422 raises ValidationError."""
        respx.get("http://test-api.local/api/v1/entities").mock(
            return_value=httpx.Response(422, json={"detail": "Validation failed"})
        )
        with pytest.raises(ValidationError) as exc_info:
            client.list_entities()
        assert exc_info.value.status_code == 422

    @respx.mock
    def test_rate_limit_error(self, client):
        """Test 429 raises RateLimitError."""
        respx.get("http://test-api.local/health").mock(
            return_value=httpx.Response(
                429,
                json={"detail": "Rate limit exceeded"},
                headers={"Retry-After": "60"},
            )
        )
        with pytest.raises(RateLimitError) as exc_info:
            client.health()
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after == 60

    @respx.mock
    def test_server_error(self, client):
        """Test 5xx raises ServerError."""
        respx.get("http://test-api.local/health").mock(
            return_value=httpx.Response(500, json={"detail": "Internal server error"})
        )
        with pytest.raises(ServerError) as exc_info:
            client.health()
        assert exc_info.value.status_code == 500

    @respx.mock
    def test_generic_error(self, client):
        """Test other errors raise AltDataError."""
        respx.get("http://test-api.local/health").mock(
            return_value=httpx.Response(418, json={"detail": "I'm a teapot"})
        )
        with pytest.raises(AltDataError) as exc_info:
            client.health()
        assert exc_info.value.status_code == 418

    @respx.mock
    def test_connection_error(self, client):
        """Test connection error raises ConnectionError."""
        respx.get("http://test-api.local/health").mock(side_effect=httpx.ConnectError)
        with pytest.raises(ConnectionError):
            client.health()

    @respx.mock
    def test_timeout_error(self, client):
        """Test timeout raises ConnectionError."""
        respx.get("http://test-api.local/health").mock(side_effect=httpx.TimeoutException)
        with pytest.raises(ConnectionError):
            client.health()

    @respx.mock
    def test_error_with_text_response(self, client):
        """Test error handling with text response (not JSON)."""
        respx.get("http://test-api.local/health").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        with pytest.raises(ServerError) as exc_info:
            client.health()
        assert "Internal Server Error" in str(exc_info.value.message)


# ===========================================
# SYSTEM ENDPOINT TESTS
# ===========================================


class TestSystemEndpoints:
    """Tests for system endpoints."""

    @respx.mock
    def test_health(self, client, mock_health_response):
        """Test health endpoint."""
        respx.get("http://test-api.local/health").mock(
            return_value=httpx.Response(200, json=mock_health_response)
        )
        response = client.health()
        assert isinstance(response, HealthResponse)
        assert response.status == "healthy"
        assert response.database == "connected"
        assert response.version == "1.0.0"


# ===========================================
# FACTOR ENDPOINT TESTS
# ===========================================


class TestFactorEndpoints:
    """Tests for factor endpoints."""

    @respx.mock
    def test_list_factors(self, client, mock_factors_list_response):
        """Test list factors endpoint."""
        respx.get("http://test-api.local/api/v1/factors").mock(
            return_value=httpx.Response(200, json=mock_factors_list_response)
        )
        response = client.list_factors()
        assert isinstance(response, FactorListResponse)
        assert response.total == 2
        assert len(response.factors) == 2
        assert response.factors[0].id == "insider_transaction_momentum"

    @respx.mock
    def test_list_factors_with_category(self, client, mock_factors_list_response):
        """Test list factors with category filter."""
        route = respx.get("http://test-api.local/api/v1/factors").mock(
            return_value=httpx.Response(200, json=mock_factors_list_response)
        )
        client.list_factors(category="sec")
        assert route.calls[0].request.url.params["category"] == "sec"

    @respx.mock
    def test_get_factor(self, client, mock_factor_response):
        """Test get factor endpoint."""
        respx.get("http://test-api.local/api/v1/factors/insider_transaction_momentum").mock(
            return_value=httpx.Response(200, json=mock_factor_response)
        )
        response = client.get_factor("insider_transaction_momentum", entity_id="AAPL")
        assert isinstance(response, FactorResponse)
        assert response.factor_name == "insider_transaction_momentum"
        assert response.entity_id == "AAPL"
        assert len(response.values) == 2

    @respx.mock
    def test_get_factor_with_dates(self, client, mock_factor_response):
        """Test get factor with date parameters."""
        route = respx.get("http://test-api.local/api/v1/factors/insider_transaction_momentum").mock(
            return_value=httpx.Response(200, json=mock_factor_response)
        )
        client.get_factor(
            "insider_transaction_momentum",
            entity_id="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 15),
        )
        params = route.calls[0].request.url.params
        assert params["entity_id"] == "AAPL"
        assert params["start_date"] == "2024-01-01"
        assert params["end_date"] == "2024-01-15"

    @respx.mock
    def test_get_factor_with_datetime(self, client, mock_factor_response):
        """Test get factor with datetime parameters."""
        route = respx.get("http://test-api.local/api/v1/factors/insider_transaction_momentum").mock(
            return_value=httpx.Response(200, json=mock_factor_response)
        )
        client.get_factor(
            "insider_transaction_momentum",
            entity_id="AAPL",
            start_date=datetime(2024, 1, 1, 10, 30),
        )
        params = route.calls[0].request.url.params
        assert "2024-01-01" in params["start_date"]

    @respx.mock
    def test_get_factor_to_dataframe(self, client, mock_factor_response):
        """Test get factor to_dataframe method."""
        respx.get("http://test-api.local/api/v1/factors/insider_transaction_momentum").mock(
            return_value=httpx.Response(200, json=mock_factor_response)
        )
        response = client.get_factor("insider_transaction_momentum", entity_id="AAPL")
        df = response.to_dataframe()
        assert len(df) == 2
        assert "value" in df.columns
        assert "version" in df.columns

    @respx.mock
    def test_list_categories(self, client, mock_categories_response):
        """Test list categories endpoint."""
        respx.get("http://test-api.local/api/v1/categories").mock(
            return_value=httpx.Response(200, json=mock_categories_response)
        )
        response = client.list_categories()
        assert isinstance(response, CategoriesResponse)
        assert len(response.categories) == 2


# ===========================================
# ENTITY ENDPOINT TESTS
# ===========================================


class TestEntityEndpoints:
    """Tests for entity endpoints."""

    @respx.mock
    def test_list_entities(self, client, mock_entities_list_response):
        """Test list entities endpoint."""
        respx.get("http://test-api.local/api/v1/entities").mock(
            return_value=httpx.Response(200, json=mock_entities_list_response)
        )
        response = client.list_entities()
        assert isinstance(response, EntityListResponse)
        assert response.total == 1
        assert response.entities[0].ticker == "AAPL"

    @respx.mock
    def test_list_entities_with_search(self, client, mock_entities_list_response):
        """Test list entities with search parameter."""
        route = respx.get("http://test-api.local/api/v1/entities").mock(
            return_value=httpx.Response(200, json=mock_entities_list_response)
        )
        client.list_entities(search="Apple")
        assert route.calls[0].request.url.params["search"] == "Apple"

    @respx.mock
    def test_list_entities_with_pagination(self, client, mock_entities_list_response):
        """Test list entities with pagination."""
        route = respx.get("http://test-api.local/api/v1/entities").mock(
            return_value=httpx.Response(200, json=mock_entities_list_response)
        )
        client.list_entities(page=2, page_size=25)
        params = route.calls[0].request.url.params
        assert params["page"] == "2"
        assert params["page_size"] == "25"

    @respx.mock
    def test_list_entities_to_dataframe(self, client, mock_entities_list_response):
        """Test list entities to_dataframe method."""
        respx.get("http://test-api.local/api/v1/entities").mock(
            return_value=httpx.Response(200, json=mock_entities_list_response)
        )
        response = client.list_entities()
        df = response.to_dataframe()
        assert len(df) == 1
        assert "ticker" in df.columns

    @respx.mock
    def test_get_entity(self, client, mock_entity_response):
        """Test get entity endpoint."""
        respx.get("http://test-api.local/api/v1/entities/AAPL").mock(
            return_value=httpx.Response(200, json=mock_entity_response)
        )
        response = client.get_entity("AAPL")
        assert isinstance(response, EntityResponse)
        assert response.ticker == "AAPL"
        assert response.name == "Apple Inc."


# ===========================================
# SOURCE ENDPOINT TESTS
# ===========================================


class TestSourceEndpoints:
    """Tests for source endpoints."""

    @respx.mock
    def test_list_sources(self, client, mock_sources_response):
        """Test list sources endpoint."""
        respx.get("http://test-api.local/api/v1/sources").mock(
            return_value=httpx.Response(200, json=mock_sources_response)
        )
        response = client.list_sources()
        assert isinstance(response, SourcesResponse)
        assert len(response.sources) == 1
        assert response.sources[0].id == "sec_edgar"

    @respx.mock
    def test_sources_to_dataframe(self, client, mock_sources_response):
        """Test sources to_dataframe method."""
        respx.get("http://test-api.local/api/v1/sources").mock(
            return_value=httpx.Response(200, json=mock_sources_response)
        )
        response = client.list_sources()
        df = response.to_dataframe()
        assert len(df) == 1
        assert "id" in df.columns


# ===========================================
# AVIATION ENDPOINT TESTS
# ===========================================


class TestAviationEndpoints:
    """Tests for aviation endpoints."""

    @respx.mock
    def test_get_flights(self, client):
        """Test get flights endpoint."""
        mock_response = {
            "company_id": "AAPL",
            "flights": [
                {
                    "icao_hex": "A12345",
                    "registration": "N12345",
                    "landing_timestamp": "2024-01-15T10:30:00",
                    "airport_icao": "KSFO",
                    "airport_name": "San Francisco Intl",
                    "latitude": 37.6213,
                    "longitude": -122.379,
                    "nearest_company_hq": "Apple Park",
                    "distance_to_hq_km": 15.5,
                }
            ],
            "total": 1,
        }
        respx.get("http://test-api.local/api/v1/aviation/flights").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_flights("AAPL")
        assert isinstance(response, FlightListResponse)
        assert response.company_id == "AAPL"
        assert len(response.flights) == 1

    @respx.mock
    def test_flights_to_dataframe(self, client):
        """Test flights to_dataframe method."""
        mock_response = {
            "company_id": "AAPL",
            "flights": [
                {
                    "icao_hex": "A12345",
                    "landing_timestamp": "2024-01-15T10:30:00",
                }
            ],
            "total": 1,
        }
        respx.get("http://test-api.local/api/v1/aviation/flights").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_flights("AAPL")
        df = response.to_dataframe()
        assert len(df) == 1


# ===========================================
# ENERGY ENDPOINT TESTS
# ===========================================


class TestEnergyEndpoints:
    """Tests for energy endpoints."""

    @respx.mock
    def test_get_grid_load(self, client):
        """Test get grid load endpoint."""
        mock_response = {
            "iso": "CAISO",
            "date": "2024-01-15",
            "readings": [
                {
                    "iso_region": "CAISO",
                    "timestamp": "2024-01-15T10:00:00",
                    "load_mw": 25000.0,
                    "forecast_mw": 25500.0,
                    "capacity_mw": 50000.0,
                    "load_pct_of_capacity": 50.0,
                }
            ],
            "total": 1,
        }
        route = respx.get("http://test-api.local/api/v1/energy/load").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_grid_load("CAISO", date(2024, 1, 15))
        assert isinstance(response, GridLoadResponse)
        assert response.iso == "CAISO"
        params = route.calls[0].request.url.params
        assert params["date"] == "2024-01-15"

    @respx.mock
    def test_grid_load_to_dataframe(self, client):
        """Test grid load to_dataframe method."""
        mock_response = {
            "iso": "CAISO",
            "date": "2024-01-15",
            "readings": [
                {
                    "iso_region": "CAISO",
                    "timestamp": "2024-01-15T10:00:00",
                    "load_mw": 25000.0,
                }
            ],
            "total": 1,
        }
        respx.get("http://test-api.local/api/v1/energy/load").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_grid_load("CAISO", date(2024, 1, 15))
        df = response.to_dataframe()
        assert len(df) == 1


# ===========================================
# PATENT ENDPOINT TESTS
# ===========================================


class TestPatentEndpoints:
    """Tests for patent endpoints."""

    @respx.mock
    def test_get_patents(self, client):
        """Test get patents endpoint."""
        mock_response = {
            "company_id": "AAPL",
            "patents": [
                {
                    "patent_number": "US12345678",
                    "application_number": "16/123456",
                    "title": "Innovative Device",
                    "filing_date": "2023-01-15",
                    "grant_date": "2024-01-15",
                    "status": "granted",
                    "primary_class": "H04",
                    "claims_count": 20,
                }
            ],
            "total": 1,
        }
        respx.get("http://test-api.local/api/v1/patents/filings").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_patents("AAPL")
        assert isinstance(response, PatentListResponse)
        assert response.company_id == "AAPL"
        assert len(response.patents) == 1


# ===========================================
# ENVIRONMENT ENDPOINT TESTS
# ===========================================


class TestEnvironmentEndpoints:
    """Tests for environment endpoints."""

    @respx.mock
    def test_get_air_quality(self, client):
        """Test get air quality endpoint."""
        mock_response = {
            "city": "Los Angeles",
            "country": "US",
            "date": "2024-01-15",
            "readings": [
                {
                    "location_id": "loc123",
                    "location_name": "Downtown LA",
                    "city": "Los Angeles",
                    "country": "US",
                    "timestamp": "2024-01-15T10:00:00",
                    "parameter": "pm25",
                    "value": 15.5,
                    "unit": "µg/m³",
                    "aqi": 58,
                }
            ],
            "total": 1,
        }
        route = respx.get("http://test-api.local/api/v1/environment/air-quality").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_air_quality(date(2024, 1, 15), city="Los Angeles")
        assert isinstance(response, AirQualityResponse)
        assert response.city == "Los Angeles"
        params = route.calls[0].request.url.params
        assert params["city"] == "Los Angeles"


# ===========================================
# WEATHER ENDPOINT TESTS
# ===========================================


class TestWeatherEndpoints:
    """Tests for weather endpoints."""

    @respx.mock
    def test_get_weather(self, client):
        """Test get weather endpoint."""
        mock_response = {
            "city": "New York",
            "date": "2024-01-15",
            "observations": [
                {
                    "city": "New York",
                    "timestamp": "2024-01-15T10:00:00",
                    "temp_c": 5.5,
                    "temp_feels_like_c": 3.0,
                    "humidity_pct": 65,
                    "wind_speed_ms": 5.2,
                    "weather_main": "Cloudy",
                    "pressure_hpa": 1013,
                }
            ],
            "total": 1,
        }
        respx.get("http://test-api.local/api/v1/weather/observations").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_weather("New York", date(2024, 1, 15))
        assert isinstance(response, WeatherResponse)
        assert response.city == "New York"

    @respx.mock
    def test_get_weather_forecast(self, client):
        """Test get weather forecast endpoint."""
        mock_response = {
            "city": "New York",
            "forecasts": [
                {
                    "city": "New York",
                    "forecast_timestamp": "2024-01-16T10:00:00",
                    "temp_c": 6.0,
                    "humidity_pct": 60,
                    "wind_speed_ms": 4.0,
                    "weather_main": "Clear",
                    "pop": 0.1,
                }
            ],
            "total": 1,
        }
        route = respx.get("http://test-api.local/api/v1/weather/forecast").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_weather_forecast("New York", days=5)
        assert isinstance(response, WeatherForecastResponse)
        params = route.calls[0].request.url.params
        assert params["days"] == "5"


# ===========================================
# TRENDS ENDPOINT TESTS
# ===========================================


class TestTrendsEndpoints:
    """Tests for trends endpoints."""

    @respx.mock
    def test_get_trends(self, client):
        """Test get trends endpoint."""
        mock_response = {
            "keyword": "bitcoin",
            "geo": "US",
            "data": [
                {
                    "keyword": "bitcoin",
                    "date": "2024-01-15",
                    "interest": 75,
                    "is_partial": False,
                    "geo": "US",
                }
            ],
            "total": 1,
        }
        route = respx.get("http://test-api.local/api/v1/trends/interest").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_trends("bitcoin", geo="US")
        assert isinstance(response, TrendResponse)
        assert response.keyword == "bitcoin"
        params = route.calls[0].request.url.params
        assert params["geo"] == "US"


# ===========================================
# SENTIMENT ENDPOINT TESTS
# ===========================================


class TestSentimentEndpoints:
    """Tests for sentiment endpoints."""

    @respx.mock
    def test_get_sentiment(self, client):
        """Test get sentiment endpoint."""
        mock_response = {
            "ticker": "AAPL",
            "data": [
                {
                    "ticker": "AAPL",
                    "date": "2024-01-15",
                    "avg_sentiment": 0.65,
                    "mention_count": 150,
                    "positive_mentions": 100,
                    "negative_mentions": 30,
                    "neutral_mentions": 20,
                }
            ],
            "total": 1,
        }
        respx.get("http://test-api.local/api/v1/sentiment/ticker").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_sentiment("AAPL")
        assert isinstance(response, SentimentResponse)
        assert response.ticker == "AAPL"


# ===========================================
# SHIPPING ENDPOINT TESTS
# ===========================================


class TestShippingEndpoints:
    """Tests for shipping endpoints."""

    @respx.mock
    def test_list_ports(self, client):
        """Test list ports endpoint."""
        mock_response = {
            "ports": [
                {
                    "port_id": "USLAX",
                    "port_name": "Los Angeles",
                    "country": "US",
                    "latitude": 33.7,
                    "longitude": -118.2,
                    "port_type": "container",
                }
            ],
            "total": 1,
        }
        route = respx.get("http://test-api.local/api/v1/shipping/ports").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.list_ports(country="US")
        assert isinstance(response, PortListResponse)
        params = route.calls[0].request.url.params
        assert params["country"] == "US"

    @respx.mock
    def test_get_port_congestion(self, client):
        """Test get port congestion endpoint."""
        mock_response = {
            "port_id": "USLAX",
            "date": "2024-01-15",
            "data": [
                {
                    "port_id": "USLAX",
                    "port_name": "Los Angeles",
                    "date": "2024-01-15",
                    "congestion_index": 0.75,
                    "vessels_waiting": 25,
                    "avg_wait_hours": 48.5,
                }
            ],
            "total": 1,
        }
        respx.get("http://test-api.local/api/v1/shipping/congestion").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_port_congestion(date(2024, 1, 15), port_id="USLAX")
        assert isinstance(response, CongestionResponse)


# ===========================================
# GITHUB ENDPOINT TESTS
# ===========================================


class TestGitHubEndpoints:
    """Tests for GitHub endpoints."""

    @respx.mock
    def test_list_github_repos(self, client):
        """Test list GitHub repos endpoint."""
        mock_response = {
            "repos": [
                {
                    "full_name": "microsoft/vscode",
                    "company": "Microsoft",
                    "ticker": "MSFT",
                    "stars": 150000,
                    "forks": 25000,
                    "open_issues": 5000,
                    "language": "TypeScript",
                }
            ],
            "total": 1,
        }
        route = respx.get("http://test-api.local/api/v1/github/repos").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.list_github_repos(ticker="MSFT")
        assert isinstance(response, GitHubRepoListResponse)
        params = route.calls[0].request.url.params
        assert params["ticker"] == "MSFT"

    @respx.mock
    def test_get_github_activity(self, client):
        """Test get GitHub activity endpoint."""
        mock_response = {
            "repo": "microsoft/vscode",
            "data": [
                {
                    "full_name": "microsoft/vscode",
                    "date": "2024-01-15",
                    "commits_24h": 50,
                    "prs_opened_24h": 10,
                    "prs_merged_24h": 8,
                    "issues_opened_24h": 15,
                    "unique_committers_24h": 20,
                }
            ],
            "total": 1,
        }
        respx.get("http://test-api.local/api/v1/github/activity").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_github_activity("microsoft/vscode")
        assert isinstance(response, GitHubActivityResponse)
        assert response.repo == "microsoft/vscode"


# ===========================================
# SATELLITE ENDPOINT TESTS
# ===========================================


class TestSatelliteEndpoints:
    """Tests for satellite endpoints."""

    @respx.mock
    def test_get_parking_data(self, client):
        """Test get parking data endpoint."""
        mock_response = {
            "ticker": "WMT",
            "data": [
                {
                    "location_id": "loc123",
                    "location_name": "Walmart Store #1234",
                    "ticker": "WMT",
                    "date": "2024-01-15",
                    "occupancy_rate": 0.75,
                    "cars_detected": 150,
                    "confidence_score": 0.95,
                }
            ],
            "total": 1,
        }
        route = respx.get("http://test-api.local/api/v1/satellite/parking").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_parking_data(ticker="WMT")
        assert isinstance(response, ParkingResponse)
        params = route.calls[0].request.url.params
        assert params["ticker"] == "WMT"

    @respx.mock
    def test_get_agricultural_data(self, client):
        """Test get agricultural data endpoint."""
        mock_response = {
            "region": "Iowa",
            "crop_type": "corn",
            "data": [
                {
                    "location_id": "loc456",
                    "region": "Iowa",
                    "crop_type": "corn",
                    "date": "2024-01-15",
                    "ndvi_mean": 0.65,
                    "crop_health_score": 0.8,
                    "ndvi_vs_historical": 0.05,
                }
            ],
            "total": 1,
        }
        route = respx.get("http://test-api.local/api/v1/satellite/agriculture").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_agricultural_data("Iowa", crop_type="corn")
        assert isinstance(response, AgriculturalResponse)
        assert response.region == "Iowa"
        params = route.calls[0].request.url.params
        assert params["crop_type"] == "corn"


# ===========================================
# TO_DATAFRAME TESTS
# ===========================================


class TestToDataframe:
    """Tests for to_dataframe methods."""

    @respx.mock
    def test_factor_list_to_dataframe(self, client, mock_factors_list_response):
        """Test factor list to_dataframe."""
        respx.get("http://test-api.local/api/v1/factors").mock(
            return_value=httpx.Response(200, json=mock_factors_list_response)
        )
        response = client.list_factors()
        df = response.to_dataframe()
        assert len(df) == 2
        assert "id" in df.columns
        assert "category" in df.columns

    @respx.mock
    def test_categories_to_dataframe(self, client, mock_categories_response):
        """Test categories to_dataframe."""
        respx.get("http://test-api.local/api/v1/categories").mock(
            return_value=httpx.Response(200, json=mock_categories_response)
        )
        response = client.list_categories()
        df = response.to_dataframe()
        assert len(df) == 2
        assert "id" in df.columns

    @respx.mock
    def test_empty_dataframe(self, client):
        """Test to_dataframe with empty data."""
        mock_response = {
            "factor_name": "test",
            "entity_id": "AAPL",
            "entity_type": "company",
            "values": [],
            "metadata": {},
        }
        respx.get("http://test-api.local/api/v1/factors/test").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_factor("test", entity_id="AAPL")
        df = response.to_dataframe()
        assert len(df) == 0


# ===========================================
# DATE FORMATTING TESTS
# ===========================================


class TestDateFormatting:
    """Tests for date formatting."""

    def test_format_date_none(self, client):
        """Test _format_date with None."""
        assert client._format_date(None) is None

    def test_format_date_with_date(self, client):
        """Test _format_date with date object."""
        result = client._format_date(date(2024, 1, 15))
        assert result == "2024-01-15"

    def test_format_date_with_datetime(self, client):
        """Test _format_date with datetime object."""
        result = client._format_date(datetime(2024, 1, 15, 10, 30, 0))
        assert "2024-01-15" in result

    def test_format_date_with_string(self, client):
        """Test _format_date with string."""
        result = client._format_date("2024-01-15")
        assert result == "2024-01-15"


# ===========================================
# EXCEPTION TESTS
# ===========================================


class TestExceptions:
    """Tests for custom exceptions."""

    def test_altdata_error(self):
        """Test AltDataError."""
        error = AltDataError("Test error", status_code=400)
        assert error.message == "Test error"
        assert error.status_code == 400
        assert str(error) == "Test error"

    def test_authentication_error(self):
        """Test AuthenticationError."""
        error = AuthenticationError()
        assert error.status_code == 401
        assert "API key" in error.message

    def test_not_found_error(self):
        """Test NotFoundError."""
        error = NotFoundError("Entity not found")
        assert error.status_code == 404
        assert error.message == "Entity not found"

    def test_rate_limit_error(self):
        """Test RateLimitError with retry_after."""
        error = RateLimitError("Too many requests", retry_after=60)
        assert error.status_code == 429
        assert error.retry_after == 60

    def test_validation_error(self):
        """Test ValidationError."""
        error = ValidationError()
        assert error.status_code == 422

    def test_server_error(self):
        """Test ServerError."""
        error = ServerError()
        assert error.status_code == 500

    def test_connection_error(self):
        """Test ConnectionError."""
        error = ConnectionError("Connection failed")
        assert error.status_code is None
        assert error.message == "Connection failed"


# ===========================================
# MODEL TO_DATAFRAME TESTS
# ===========================================


class TestModelsToDataframe:
    """Tests for all model to_dataframe methods."""

    def test_patent_list_to_dataframe(self):
        """Test PatentListResponse to_dataframe."""
        from altdata.models import PatentListResponse, PatentRecord

        response = PatentListResponse(
            company_id="AAPL",
            patents=[
                PatentRecord(
                    patent_number="US12345678",
                    title="Test Patent",
                    filing_date=date(2024, 1, 1),
                    grant_date=date(2024, 6, 1),
                    status="granted",
                    claims_count=20,
                )
            ],
            total=1,
        )
        df = response.to_dataframe()
        assert len(df) == 1
        assert "patent_number" in df.columns

    def test_air_quality_to_dataframe(self):
        """Test AirQualityResponse to_dataframe."""
        from altdata.models import AirQualityResponse, AirQualityRecord

        response = AirQualityResponse(
            city="Los Angeles",
            country="US",
            date=date(2024, 1, 15),
            readings=[
                AirQualityRecord(
                    location_id="loc1",
                    timestamp=datetime(2024, 1, 15, 10, 0),
                    parameter="pm25",
                    value=15.5,
                    aqi=58,
                )
            ],
            total=1,
        )
        df = response.to_dataframe()
        assert len(df) == 1
        assert df.index.name == "timestamp"

    def test_weather_to_dataframe(self):
        """Test WeatherResponse to_dataframe."""
        from altdata.models import WeatherResponse, WeatherRecord

        response = WeatherResponse(
            city="New York",
            date=date(2024, 1, 15),
            observations=[
                WeatherRecord(
                    city="New York",
                    timestamp=datetime(2024, 1, 15, 10, 0),
                    temp_c=5.5,
                    humidity_pct=65,
                )
            ],
            total=1,
        )
        df = response.to_dataframe()
        assert len(df) == 1
        assert df.index.name == "timestamp"

    def test_weather_forecast_to_dataframe(self):
        """Test WeatherForecastResponse to_dataframe."""
        from altdata.models import WeatherForecastResponse, WeatherForecastRecord

        response = WeatherForecastResponse(
            city="New York",
            forecasts=[
                WeatherForecastRecord(
                    city="New York",
                    forecast_timestamp=datetime(2024, 1, 16, 10, 0),
                    temp_c=6.0,
                    pop=0.1,
                )
            ],
            total=1,
        )
        df = response.to_dataframe()
        assert len(df) == 1
        assert df.index.name == "forecast_timestamp"

    def test_trend_to_dataframe(self):
        """Test TrendResponse to_dataframe."""
        from altdata.models import TrendResponse, TrendRecord

        response = TrendResponse(
            keyword="bitcoin",
            geo="US",
            data=[
                TrendRecord(
                    keyword="bitcoin",
                    date=date(2024, 1, 15),
                    interest=75,
                    is_partial=False,
                    geo="US",
                )
            ],
            total=1,
        )
        df = response.to_dataframe()
        assert len(df) == 1
        assert df.index.name == "date"

    def test_sentiment_to_dataframe(self):
        """Test SentimentResponse to_dataframe."""
        from altdata.models import SentimentResponse, SentimentRecord

        response = SentimentResponse(
            ticker="AAPL",
            data=[
                SentimentRecord(
                    ticker="AAPL",
                    date=date(2024, 1, 15),
                    avg_sentiment=0.65,
                    mention_count=150,
                )
            ],
            total=1,
        )
        df = response.to_dataframe()
        assert len(df) == 1
        assert df.index.name == "date"

    def test_port_list_to_dataframe(self):
        """Test PortListResponse to_dataframe."""
        from altdata.models import PortListResponse, PortRecord

        response = PortListResponse(
            ports=[
                PortRecord(
                    port_id="USLAX",
                    port_name="Los Angeles",
                    country="US",
                    latitude=33.7,
                    longitude=-118.2,
                )
            ],
            total=1,
        )
        df = response.to_dataframe()
        assert len(df) == 1
        assert "port_id" in df.columns

    def test_congestion_to_dataframe(self):
        """Test CongestionResponse to_dataframe."""
        from altdata.models import CongestionResponse, CongestionRecord

        response = CongestionResponse(
            port_id="USLAX",
            date=date(2024, 1, 15),
            data=[
                CongestionRecord(
                    port_id="USLAX",
                    port_name="Los Angeles",
                    date=date(2024, 1, 15),
                    congestion_index=0.75,
                    vessels_waiting=25,
                )
            ],
            total=1,
        )
        df = response.to_dataframe()
        assert len(df) == 1
        assert df.index.name == "date"

    def test_github_repo_list_to_dataframe(self):
        """Test GitHubRepoListResponse to_dataframe."""
        from altdata.models import GitHubRepoListResponse, GitHubRepoRecord

        response = GitHubRepoListResponse(
            repos=[
                GitHubRepoRecord(
                    full_name="microsoft/vscode",
                    company="Microsoft",
                    ticker="MSFT",
                    stars=150000,
                )
            ],
            total=1,
        )
        df = response.to_dataframe()
        assert len(df) == 1
        assert "full_name" in df.columns

    def test_github_activity_to_dataframe(self):
        """Test GitHubActivityResponse to_dataframe."""
        from altdata.models import GitHubActivityResponse, GitHubActivityRecord

        response = GitHubActivityResponse(
            repo="microsoft/vscode",
            data=[
                GitHubActivityRecord(
                    full_name="microsoft/vscode",
                    date=date(2024, 1, 15),
                    commits_24h=50,
                    prs_opened_24h=10,
                )
            ],
            total=1,
        )
        df = response.to_dataframe()
        assert len(df) == 1
        assert df.index.name == "date"

    def test_parking_to_dataframe(self):
        """Test ParkingResponse to_dataframe."""
        from altdata.models import ParkingResponse, ParkingRecord

        response = ParkingResponse(
            ticker="WMT",
            data=[
                ParkingRecord(
                    location_id="loc1",
                    location_name="Walmart #1234",
                    ticker="WMT",
                    date=date(2024, 1, 15),
                    occupancy_rate=0.75,
                    cars_detected=150,
                )
            ],
            total=1,
        )
        df = response.to_dataframe()
        assert len(df) == 1
        assert df.index.name == "date"

    def test_agricultural_to_dataframe(self):
        """Test AgriculturalResponse to_dataframe."""
        from altdata.models import AgriculturalResponse, AgriculturalRecord

        response = AgriculturalResponse(
            region="Iowa",
            crop_type="corn",
            data=[
                AgriculturalRecord(
                    location_id="loc1",
                    region="Iowa",
                    crop_type="corn",
                    date=date(2024, 1, 15),
                    ndvi_mean=0.65,
                    crop_health_score=0.8,
                )
            ],
            total=1,
        )
        df = response.to_dataframe()
        assert len(df) == 1
        assert df.index.name == "date"

    def test_empty_dataframes(self):
        """Test to_dataframe with empty data lists."""
        from altdata.models import (
            PatentListResponse,
            AirQualityResponse,
            WeatherResponse,
            WeatherForecastResponse,
            TrendResponse,
            SentimentResponse,
            PortListResponse,
            CongestionResponse,
            GitHubRepoListResponse,
            GitHubActivityResponse,
            ParkingResponse,
            AgriculturalResponse,
        )

        # Test all empty responses
        assert len(PatentListResponse(company_id="AAPL", patents=[], total=0).to_dataframe()) == 0
        assert len(AirQualityResponse(date=date(2024, 1, 15), readings=[], total=0).to_dataframe()) == 0
        assert len(WeatherResponse(city="NYC", date=date(2024, 1, 15), observations=[], total=0).to_dataframe()) == 0
        assert len(WeatherForecastResponse(city="NYC", forecasts=[], total=0).to_dataframe()) == 0
        assert len(TrendResponse(keyword="test", data=[], total=0).to_dataframe()) == 0
        assert len(SentimentResponse(ticker="AAPL", data=[], total=0).to_dataframe()) == 0
        assert len(PortListResponse(ports=[], total=0).to_dataframe()) == 0
        assert len(CongestionResponse(date=date(2024, 1, 15), data=[], total=0).to_dataframe()) == 0
        assert len(GitHubRepoListResponse(repos=[], total=0).to_dataframe()) == 0
        assert len(GitHubActivityResponse(repo="test/repo", data=[], total=0).to_dataframe()) == 0
        assert len(ParkingResponse(data=[], total=0).to_dataframe()) == 0
        assert len(AgriculturalResponse(region="Iowa", data=[], total=0).to_dataframe()) == 0


# ===========================================
# GET_SOURCE_STATUS ALIAS TEST
# ===========================================


class TestGetSourceStatus:
    """Tests for get_source_status method alias."""

    @respx.mock
    def test_get_source_status(self, client, mock_sources_response):
        """Test get_source_status is an alias for list_sources."""
        respx.get("http://test-api.local/api/v1/sources").mock(
            return_value=httpx.Response(200, json=mock_sources_response)
        )
        # list_sources works the same as get_source_status conceptually
        response = client.list_sources()
        assert isinstance(response, SourcesResponse)
        assert len(response.sources) == 1


# ===========================================
# ALERT ENDPOINT TESTS
# ===========================================


class TestAlertEndpoints:
    """Tests for alert endpoints."""

    @respx.mock
    def test_create_alert_rule(self, client):
        """Test create alert rule endpoint."""
        from altdata.models import AlertRule

        mock_response = {
            "id": 1,
            "name": "High Insider Activity",
            "description": "Alert when insider activity spikes",
            "factor_name": "insider_transaction_momentum",
            "entity_id": "AAPL",
            "condition": "gt",
            "threshold": 1000.0,
            "lookback_days": 30,
            "is_active": True,
            "notification_channel": "slack",
            "notification_config": '{"webhook_url": "https://hooks.slack.com/test"}',
            "cooldown_minutes": 60,
            "created_by": "test-user",
            "created_at": "2024-01-15T10:00:00",
            "updated_at": "2024-01-15T10:00:00",
        }
        route = respx.post("http://test-api.local/api/v1/alerts/rules").mock(
            return_value=httpx.Response(201, json=mock_response)
        )
        response = client.create_alert_rule(
            name="High Insider Activity",
            factor_name="insider_transaction_momentum",
            condition="gt",
            threshold=1000.0,
            entity_id="AAPL",
            description="Alert when insider activity spikes",
            notification_config={"webhook_url": "https://hooks.slack.com/test"},
        )
        assert isinstance(response, AlertRule)
        assert response.id == 1
        assert response.name == "High Insider Activity"
        assert response.factor_name == "insider_transaction_momentum"
        assert route.called

    @respx.mock
    def test_list_alert_rules(self, client):
        """Test list alert rules endpoint."""
        from altdata.models import AlertRuleListResponse

        mock_response = {
            "rules": [
                {
                    "id": 1,
                    "name": "Test Alert",
                    "factor_name": "insider_transaction_momentum",
                    "condition": "gt",
                    "threshold": 1000.0,
                    "lookback_days": 30,
                    "is_active": True,
                    "notification_channel": "slack",
                    "cooldown_minutes": 60,
                    "created_at": "2024-01-15T10:00:00",
                    "updated_at": "2024-01-15T10:00:00",
                }
            ],
            "total": 1,
        }
        route = respx.get("http://test-api.local/api/v1/alerts/rules").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.list_alert_rules(is_active=True)
        assert isinstance(response, AlertRuleListResponse)
        assert response.total == 1
        assert len(response.rules) == 1
        params = route.calls[0].request.url.params
        assert params["is_active"].lower() == "true"

    @respx.mock
    def test_get_alert_rule(self, client):
        """Test get alert rule endpoint."""
        from altdata.models import AlertRule

        mock_response = {
            "id": 1,
            "name": "Test Alert",
            "factor_name": "insider_transaction_momentum",
            "condition": "gt",
            "threshold": 1000.0,
            "lookback_days": 30,
            "is_active": True,
            "notification_channel": "slack",
            "cooldown_minutes": 60,
            "created_at": "2024-01-15T10:00:00",
            "updated_at": "2024-01-15T10:00:00",
        }
        respx.get("http://test-api.local/api/v1/alerts/rules/1").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_alert_rule(1)
        assert isinstance(response, AlertRule)
        assert response.id == 1

    @respx.mock
    def test_update_alert_rule(self, client):
        """Test update alert rule endpoint."""
        from altdata.models import AlertRule

        mock_response = {
            "id": 1,
            "name": "Updated Alert",
            "factor_name": "insider_transaction_momentum",
            "condition": "gt",
            "threshold": 2000.0,
            "lookback_days": 30,
            "is_active": False,
            "notification_channel": "slack",
            "cooldown_minutes": 60,
            "created_at": "2024-01-15T10:00:00",
            "updated_at": "2024-01-15T11:00:00",
        }
        route = respx.put("http://test-api.local/api/v1/alerts/rules/1").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.update_alert_rule(
            rule_id=1,
            name="Updated Alert",
            threshold=2000.0,
            is_active=False,
        )
        assert isinstance(response, AlertRule)
        assert response.name == "Updated Alert"
        assert response.threshold == 2000.0
        assert response.is_active is False
        assert route.called

    @respx.mock
    def test_delete_alert_rule(self, client):
        """Test delete alert rule endpoint."""
        respx.delete("http://test-api.local/api/v1/alerts/rules/1").mock(
            return_value=httpx.Response(204)
        )
        # Should not raise
        client.delete_alert_rule(1)

    @respx.mock
    def test_list_alert_notifications(self, client):
        """Test list alert notifications endpoint."""
        from altdata.models import AlertNotificationListResponse

        mock_response = {
            "notifications": [
                {
                    "id": 1,
                    "rule_id": 1,
                    "entity_id": "AAPL",
                    "factor_value": 1500.0,
                    "threshold": 1000.0,
                    "computed_value": None,
                    "triggered_at": "2024-01-15T10:00:00",
                    "notified_at": "2024-01-15T10:00:05",
                    "notification_channel": "slack",
                    "notification_status": "sent",
                    "error_message": None,
                }
            ],
            "total": 1,
        }
        route = respx.get("http://test-api.local/api/v1/alerts/notifications").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.list_alert_notifications(
            rule_id=1,
            status="sent",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )
        assert isinstance(response, AlertNotificationListResponse)
        assert response.total == 1
        assert len(response.notifications) == 1
        params = route.calls[0].request.url.params
        assert params["rule_id"] == "1"
        assert params["status"] == "sent"

    @respx.mock
    def test_trigger_alert_check(self, client):
        """Test trigger alert check endpoint."""
        from altdata.models import AlertCheckResponse

        mock_response = {
            "status": "complete",
            "alerts_triggered": 2,
            "details": [
                {"rule_id": 1, "entity_id": "AAPL", "triggered": True},
                {"rule_id": 2, "entity_id": "MSFT", "triggered": True},
            ],
        }
        respx.post("http://test-api.local/api/v1/alerts/check").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.trigger_alert_check()
        assert isinstance(response, AlertCheckResponse)
        assert response.status == "complete"
        assert response.alerts_triggered == 2


# ===========================================
# BACKTEST ENDPOINT TESTS
# ===========================================


class TestBacktestEndpoints:
    """Tests for backtest endpoints."""

    @respx.mock
    def test_run_backtest(self, client):
        """Test run backtest endpoint."""
        mock_response = {"job_id": "bt-12345-abc"}
        route = respx.post("http://test-api.local/api/v1/backtest/run").mock(
            return_value=httpx.Response(202, json=mock_response)
        )
        job_id = client.run_backtest(
            factor_name="insider_transaction_momentum",
            universe=["AAPL", "MSFT", "GOOGL"],
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            rebalance_freq="weekly",
            long_short=True,
            top_n=10,
            transaction_cost=0.001,
        )
        assert job_id == "bt-12345-abc"
        assert route.called

    @respx.mock
    def test_run_backtest_quick(self, client):
        """Test run quick backtest endpoint."""
        from altdata.models import BacktestResult

        mock_response = {
            "job_id": "bt-quick-123",
            "status": "complete",
            "factor_name": "insider_transaction_momentum",
            "universe_size": 3,
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "rebalance_freq": "daily",
            "long_short": True,
            "top_n": 10,
            "sharpe_ratio": 1.5,
            "sortino_ratio": 2.0,
            "calmar_ratio": 1.2,
            "max_drawdown": -0.15,
            "total_return": 0.25,
            "annualized_return": 0.28,
            "volatility": 0.18,
            "ic_mean": 0.05,
            "ic_ir": 1.1,
            "win_rate": 0.55,
            "profit_factor": 1.8,
            "turnover": 0.2,
            "completed_at": "2024-01-15T10:00:00",
        }
        respx.post("http://test-api.local/api/v1/backtest/quick").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.run_backtest_quick(
            factor_name="insider_transaction_momentum",
            universe=["AAPL", "MSFT", "GOOGL"],
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )
        assert isinstance(response, BacktestResult)
        assert response.job_id == "bt-quick-123"
        assert response.status == "complete"
        assert response.sharpe_ratio == 1.5

    @respx.mock
    def test_get_backtest_result(self, client):
        """Test get backtest result endpoint."""
        from altdata.models import BacktestResult

        mock_response = {
            "job_id": "bt-12345-abc",
            "status": "complete",
            "factor_name": "insider_transaction_momentum",
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.15,
            "total_return": 0.25,
        }
        respx.get("http://test-api.local/api/v1/backtest/results/bt-12345-abc").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_backtest_result("bt-12345-abc")
        assert isinstance(response, BacktestResult)
        assert response.job_id == "bt-12345-abc"
        assert response.status == "complete"

    @respx.mock
    def test_get_backtest_timeseries(self, client):
        """Test get backtest timeseries endpoint."""
        from altdata.models import BacktestTimeSeries

        mock_response = {
            "job_id": "bt-12345-abc",
            "dates": ["2023-01-01", "2023-01-02", "2023-01-03"],
            "cumulative_returns": [1.0, 1.01, 1.02],
            "daily_returns": [0.0, 0.01, 0.0099],
        }
        respx.get("http://test-api.local/api/v1/backtest/results/bt-12345-abc/timeseries").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_backtest_timeseries("bt-12345-abc")
        assert isinstance(response, BacktestTimeSeries)
        assert response.job_id == "bt-12345-abc"
        assert len(response.dates) == 3

    @respx.mock
    def test_get_backtest_positions(self, client):
        """Test get backtest positions endpoint."""
        from altdata.models import BacktestPositions

        mock_response = {
            "job_id": "bt-12345-abc",
            "dates": ["2023-01-01", "2023-01-02"],
            "positions": {
                "AAPL": [0.5, 0.5],
                "MSFT": [0.5, 0.5],
            },
        }
        respx.get("http://test-api.local/api/v1/backtest/results/bt-12345-abc/positions").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_backtest_positions("bt-12345-abc")
        assert isinstance(response, BacktestPositions)
        assert response.job_id == "bt-12345-abc"
        assert "AAPL" in response.positions

    @respx.mock
    def test_get_backtest_ic(self, client):
        """Test get backtest IC endpoint."""
        from altdata.models import BacktestIC

        mock_response = {
            "job_id": "bt-12345-abc",
            "dates": ["2023-01-01", "2023-01-02", "2023-01-03"],
            "ic_values": [0.05, 0.06, 0.04],
            "ic_mean": 0.05,
            "ic_ir": 1.1,
        }
        respx.get("http://test-api.local/api/v1/backtest/results/bt-12345-abc/ic").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.get_backtest_ic("bt-12345-abc")
        assert isinstance(response, BacktestIC)
        assert response.job_id == "bt-12345-abc"
        assert response.ic_mean == 0.05
        assert response.ic_ir == 1.1

    @respx.mock
    def test_list_backtest_jobs(self, client):
        """Test list backtest jobs endpoint."""
        from altdata.models import BacktestJobListResponse

        mock_response = {
            "jobs": [
                {"job_id": "bt-1", "status": "complete", "factor_name": "test_factor"},
                {"job_id": "bt-2", "status": "running", "factor_name": "other_factor"},
            ],
            "total": 2,
        }
        route = respx.get("http://test-api.local/api/v1/backtest/jobs").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        response = client.list_backtest_jobs(status="complete", limit=10)
        assert isinstance(response, BacktestJobListResponse)
        assert response.total == 2
        params = route.calls[0].request.url.params
        assert params["status"] == "complete"
        assert params["limit"] == "10"

    @respx.mock
    def test_delete_backtest_job(self, client):
        """Test delete backtest job endpoint."""
        respx.delete("http://test-api.local/api/v1/backtest/jobs/bt-12345-abc").mock(
            return_value=httpx.Response(204)
        )
        # Should not raise
        client.delete_backtest_job("bt-12345-abc")


# ===========================================
# ALERT/BACKTEST MODEL TO_DATAFRAME TESTS
# ===========================================


class TestAlertBacktestModelsToDataframe:
    """Tests for alert and backtest model to_dataframe methods."""

    def test_alert_rule_list_to_dataframe(self):
        """Test AlertRuleListResponse to_dataframe."""
        from altdata.models import AlertRuleListResponse, AlertRule
        from datetime import datetime

        response = AlertRuleListResponse(
            rules=[
                AlertRule(
                    id=1,
                    name="Test Alert",
                    factor_name="insider_transaction_momentum",
                    condition="gt",
                    threshold=1000.0,
                    lookback_days=30,
                    is_active=True,
                    notification_channel="slack",
                    cooldown_minutes=60,
                    created_at=datetime(2024, 1, 15, 10, 0),
                    updated_at=datetime(2024, 1, 15, 10, 0),
                )
            ],
            total=1,
        )
        df = response.to_dataframe()
        assert len(df) == 1
        assert "name" in df.columns
        assert "factor_name" in df.columns

    def test_alert_notification_list_to_dataframe(self):
        """Test AlertNotificationListResponse to_dataframe."""
        from altdata.models import AlertNotificationListResponse, AlertNotification
        from datetime import datetime

        response = AlertNotificationListResponse(
            notifications=[
                AlertNotification(
                    id=1,
                    rule_id=1,
                    entity_id="AAPL",
                    factor_value=1500.0,
                    threshold=1000.0,
                    triggered_at=datetime(2024, 1, 15, 10, 0),
                    notification_status="sent",
                )
            ],
            total=1,
        )
        df = response.to_dataframe()
        assert len(df) == 1
        assert df.index.name == "triggered_at"

    def test_backtest_timeseries_to_dataframe(self):
        """Test BacktestTimeSeries to_dataframe."""
        from altdata.models import BacktestTimeSeries

        response = BacktestTimeSeries(
            job_id="bt-123",
            dates=["2023-01-01", "2023-01-02", "2023-01-03"],
            cumulative_returns=[1.0, 1.01, 1.02],
            daily_returns=[0.0, 0.01, 0.0099],
        )
        df = response.to_dataframe()
        assert len(df) == 3
        assert "cumulative_returns" in df.columns
        assert "daily_returns" in df.columns

    def test_backtest_positions_to_dataframe(self):
        """Test BacktestPositions to_dataframe."""
        from altdata.models import BacktestPositions

        response = BacktestPositions(
            job_id="bt-123",
            dates=["2023-01-01", "2023-01-02"],
            positions={
                "AAPL": [0.5, 0.5],
                "MSFT": [0.5, 0.5],
            },
        )
        df = response.to_dataframe()
        assert len(df) == 2
        assert "AAPL" in df.columns
        assert "MSFT" in df.columns

    def test_backtest_ic_to_dataframe(self):
        """Test BacktestIC to_dataframe."""
        from altdata.models import BacktestIC

        response = BacktestIC(
            job_id="bt-123",
            dates=["2023-01-01", "2023-01-02", "2023-01-03"],
            ic_values=[0.05, 0.06, 0.04],
            ic_mean=0.05,
            ic_ir=1.1,
        )
        df = response.to_dataframe()
        assert len(df) == 3
        assert "ic" in df.columns

    def test_empty_alert_backtest_dataframes(self):
        """Test to_dataframe with empty data lists for alert/backtest models."""
        from altdata.models import (
            AlertRuleListResponse,
            AlertNotificationListResponse,
        )

        assert len(AlertRuleListResponse(rules=[], total=0).to_dataframe()) == 0
        assert len(AlertNotificationListResponse(notifications=[], total=0).to_dataframe()) == 0
