"""Main client for the Alternative Data Platform API."""

from datetime import datetime, date
from typing import Optional, Union

import httpx

from .exceptions import (
    AltDataError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    ServerError,
    ConnectionError,
)
from .models import (
    HealthResponse,
    FactorResponse,
    FactorListResponse,
    EntityResponse,
    EntityListResponse,
    SourcesResponse,
    CategoriesResponse,
    DataSource,
    CategoryInfo,
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


class AltDataClient:
    """Client for the Alternative Data Platform API.

    Example:
        >>> from altdata import AltDataClient
        >>> client = AltDataClient(api_key='your-api-key')
        >>> factors = client.list_factors(category='sec')
        >>> data = client.get_factor('insider_transaction_momentum', entity_id='AAPL')
        >>> df = data.to_dataframe()
    """

    DEFAULT_BASE_URL = "http://localhost:8000"
    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the AltData client.

        Args:
            api_key: API key for authentication. Can be None for development mode.
            base_url: Base URL for the API. Defaults to http://localhost:8000.
            timeout: Request timeout in seconds. Defaults to 30.
        """
        self.api_key = api_key
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=self.timeout)

    def __enter__(self) -> "AltDataClient":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager."""
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def _get_headers(self) -> dict:
        """Get request headers including authentication."""
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _handle_response(self, response: httpx.Response) -> dict:
        """Handle API response and raise appropriate exceptions.

        Args:
            response: The HTTP response object.

        Returns:
            The parsed JSON response data.

        Raises:
            AuthenticationError: If API key is invalid or missing.
            NotFoundError: If the requested resource doesn't exist.
            RateLimitError: If rate limit is exceeded.
            ValidationError: If request validation fails.
            ServerError: If server returns 5xx error.
            AltDataError: For other HTTP errors.
        """
        if response.status_code == 200:
            return response.json()

        # Try to extract error detail from response
        try:
            error_data = response.json()
            detail = error_data.get("detail", str(error_data))
        except Exception:
            detail = response.text or f"HTTP {response.status_code}"

        if response.status_code == 401:
            raise AuthenticationError(detail)
        elif response.status_code == 404:
            raise NotFoundError(detail)
        elif response.status_code == 422:
            raise ValidationError(detail)
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                detail, retry_after=int(retry_after) if retry_after else None
            )
        elif response.status_code >= 500:
            raise ServerError(detail)
        else:
            raise AltDataError(detail, status_code=response.status_code)

    def _request(
        self, method: str, path: str, params: Optional[dict] = None
    ) -> dict:
        """Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API endpoint path.
            params: Query parameters.

        Returns:
            The parsed JSON response data.

        Raises:
            ConnectionError: If unable to connect to the API.
        """
        url = f"{self.base_url}{path}"

        # Filter out None values from params
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        try:
            response = self._client.request(
                method, url, params=params, headers=self._get_headers()
            )
            return self._handle_response(response)
        except httpx.ConnectError as e:
            raise ConnectionError(f"Unable to connect to {url}: {e}")
        except httpx.TimeoutException as e:
            raise ConnectionError(f"Request timed out: {e}")

    def _format_date(self, d: Optional[Union[datetime, date, str]]) -> Optional[str]:
        """Format a date for API requests.

        Args:
            d: Date as datetime, date, or ISO string.

        Returns:
            ISO formatted date string or None.
        """
        if d is None:
            return None
        if isinstance(d, datetime):
            return d.isoformat()
        if isinstance(d, date):
            return d.isoformat()
        return str(d)

    # ===========================================
    # SYSTEM ENDPOINTS
    # ===========================================

    def health(self) -> HealthResponse:
        """Check API health status.

        Returns:
            HealthResponse with system status information.
        """
        data = self._request("GET", "/health")
        return HealthResponse(**data)

    # ===========================================
    # FACTOR ENDPOINTS
    # ===========================================

    def list_factors(self, category: Optional[str] = None) -> FactorListResponse:
        """List all available factors.

        Args:
            category: Filter by category (e.g., 'sec', 'aviation', 'weather').

        Returns:
            FactorListResponse with list of available factors.
        """
        data = self._request("GET", "/api/v1/factors", params={"category": category})
        return FactorListResponse(**data)

    def get_factor(
        self,
        factor_name: str,
        entity_id: str,
        start_date: Optional[Union[datetime, date, str]] = None,
        end_date: Optional[Union[datetime, date, str]] = None,
    ) -> FactorResponse:
        """Get factor values for an entity.

        Args:
            factor_name: Name of the factor (e.g., 'insider_transaction_momentum').
            entity_id: Entity identifier (e.g., 'AAPL').
            start_date: Start date for data range.
            end_date: End date for data range.

        Returns:
            FactorResponse with factor values.
        """
        params = {
            "entity_id": entity_id,
            "start_date": self._format_date(start_date),
            "end_date": self._format_date(end_date),
        }
        data = self._request("GET", f"/api/v1/factors/{factor_name}", params=params)
        return FactorResponse(**data)

    def list_categories(self) -> CategoriesResponse:
        """List all factor categories.

        Returns:
            CategoriesResponse with list of categories.
        """
        data = self._request("GET", "/api/v1/categories")
        categories = [CategoryInfo(**c) for c in data.get("categories", [])]
        return CategoriesResponse(categories=categories)

    # ===========================================
    # ENTITY ENDPOINTS
    # ===========================================

    def list_entities(
        self,
        search: Optional[str] = None,
        entity_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> EntityListResponse:
        """List and search entities.

        Args:
            search: Search by name or ticker.
            entity_type: Filter by entity type.
            page: Page number (1-indexed).
            page_size: Number of results per page (1-100).

        Returns:
            EntityListResponse with list of entities.
        """
        params = {
            "search": search,
            "entity_type": entity_type,
            "page": page,
            "page_size": page_size,
        }
        data = self._request("GET", "/api/v1/entities", params=params)
        return EntityListResponse(**data)

    def get_entity(self, entity_id: str) -> EntityResponse:
        """Get entity details by ID or ticker.

        Args:
            entity_id: Entity ID or ticker symbol.

        Returns:
            EntityResponse with entity details.
        """
        data = self._request("GET", f"/api/v1/entities/{entity_id}")
        return EntityResponse(**data)

    # ===========================================
    # SOURCE ENDPOINTS
    # ===========================================

    def list_sources(self) -> SourcesResponse:
        """List available data sources.

        Returns:
            SourcesResponse with list of data sources.
        """
        data = self._request("GET", "/api/v1/sources")
        sources = [DataSource(**s) for s in data.get("sources", [])]
        return SourcesResponse(sources=sources)

    def get_source_status(self) -> SourcesResponse:
        """Get status of all data sources.

        This is an alias for list_sources().

        Returns:
            SourcesResponse with list of data sources and their status.
        """
        return self.list_sources()

    # ===========================================
    # AVIATION ENDPOINTS (Phase 1)
    # ===========================================

    def get_flights(
        self,
        company_id: str,
        start_date: Optional[Union[datetime, date, str]] = None,
        end_date: Optional[Union[datetime, date, str]] = None,
    ) -> FlightListResponse:
        """Get corporate flight history for a company.

        Args:
            company_id: Company entity ID.
            start_date: Start date for data range.
            end_date: End date for data range.

        Returns:
            FlightListResponse with flight records.
        """
        params = {
            "company_id": company_id,
            "start_date": self._format_date(start_date),
            "end_date": self._format_date(end_date),
        }
        data = self._request("GET", "/api/v1/aviation/flights", params=params)
        return FlightListResponse(**data)

    # ===========================================
    # ENERGY ENDPOINTS (Phase 1)
    # ===========================================

    def get_grid_load(
        self,
        iso: str,
        query_date: Union[datetime, date, str],
    ) -> GridLoadResponse:
        """Get electricity load data for an ISO region.

        Args:
            iso: ISO region (CAISO, ERCOT, PJM, MISO).
            query_date: Date to query.

        Returns:
            GridLoadResponse with load readings.
        """
        date_str = self._format_date(query_date)
        if isinstance(date_str, str) and "T" in date_str:
            date_str = date_str.split("T")[0]
        params = {"iso": iso, "date": date_str}
        data = self._request("GET", "/api/v1/energy/load", params=params)
        return GridLoadResponse(**data)

    # ===========================================
    # PATENT ENDPOINTS (Phase 1)
    # ===========================================

    def get_patents(
        self,
        company_id: str,
        start_date: Optional[Union[datetime, date, str]] = None,
        end_date: Optional[Union[datetime, date, str]] = None,
    ) -> PatentListResponse:
        """Get patent filing history for a company.

        Args:
            company_id: Company entity ID.
            start_date: Start date for data range.
            end_date: End date for data range.

        Returns:
            PatentListResponse with patent records.
        """
        params = {
            "company_id": company_id,
            "start_date": self._format_date(start_date),
            "end_date": self._format_date(end_date),
        }
        data = self._request("GET", "/api/v1/patents/filings", params=params)
        return PatentListResponse(**data)

    # ===========================================
    # ENVIRONMENT ENDPOINTS (Phase 1)
    # ===========================================

    def get_air_quality(
        self,
        query_date: Union[datetime, date, str],
        city: Optional[str] = None,
        country: Optional[str] = None,
        parameter: str = "pm25",
    ) -> AirQualityResponse:
        """Get air quality readings.

        Args:
            query_date: Date to query.
            city: Filter by city.
            country: Filter by country code.
            parameter: Pollutant parameter (default: pm25).

        Returns:
            AirQualityResponse with air quality readings.
        """
        date_str = self._format_date(query_date)
        if isinstance(date_str, str) and "T" in date_str:
            date_str = date_str.split("T")[0]
        params = {
            "date": date_str,
            "city": city,
            "country": country,
            "parameter": parameter,
        }
        data = self._request("GET", "/api/v1/environment/air-quality", params=params)
        return AirQualityResponse(**data)

    # ===========================================
    # WEATHER ENDPOINTS (Phase 2)
    # ===========================================

    def get_weather(
        self,
        city: str,
        query_date: Union[datetime, date, str],
    ) -> WeatherResponse:
        """Get weather observations for a city.

        Args:
            city: City name.
            query_date: Date to query.

        Returns:
            WeatherResponse with weather observations.
        """
        date_str = self._format_date(query_date)
        if isinstance(date_str, str) and "T" in date_str:
            date_str = date_str.split("T")[0]
        params = {"city": city, "date": date_str}
        data = self._request("GET", "/api/v1/weather/observations", params=params)
        return WeatherResponse(**data)

    def get_weather_forecast(
        self,
        city: str,
        days: int = 7,
    ) -> WeatherForecastResponse:
        """Get weather forecast for a city.

        Args:
            city: City name.
            days: Number of days (1-14, default: 7).

        Returns:
            WeatherForecastResponse with forecasts.
        """
        params = {"city": city, "days": days}
        data = self._request("GET", "/api/v1/weather/forecast", params=params)
        return WeatherForecastResponse(**data)

    # ===========================================
    # TRENDS ENDPOINTS (Phase 2)
    # ===========================================

    def get_trends(
        self,
        keyword: str,
        geo: str = "US",
        start_date: Optional[Union[datetime, date, str]] = None,
        end_date: Optional[Union[datetime, date, str]] = None,
    ) -> TrendResponse:
        """Get Google Trends interest data for a keyword.

        Args:
            keyword: Search keyword.
            geo: Geographic region (default: US).
            start_date: Start date for data range.
            end_date: End date for data range.

        Returns:
            TrendResponse with trends data.
        """
        params = {
            "keyword": keyword,
            "geo": geo,
            "start_date": self._format_date(start_date),
            "end_date": self._format_date(end_date),
        }
        data = self._request("GET", "/api/v1/trends/interest", params=params)
        return TrendResponse(**data)

    # ===========================================
    # SENTIMENT ENDPOINTS (Phase 2)
    # ===========================================

    def get_sentiment(
        self,
        ticker: str,
        start_date: Optional[Union[datetime, date, str]] = None,
        end_date: Optional[Union[datetime, date, str]] = None,
    ) -> SentimentResponse:
        """Get Reddit sentiment data for a ticker.

        Args:
            ticker: Stock ticker.
            start_date: Start date for data range.
            end_date: End date for data range.

        Returns:
            SentimentResponse with sentiment data.
        """
        params = {
            "ticker": ticker,
            "start_date": self._format_date(start_date),
            "end_date": self._format_date(end_date),
        }
        data = self._request("GET", "/api/v1/sentiment/ticker", params=params)
        return SentimentResponse(**data)

    # ===========================================
    # SHIPPING ENDPOINTS (Phase 2)
    # ===========================================

    def list_ports(
        self,
        country: Optional[str] = None,
        port_type: Optional[str] = None,
    ) -> PortListResponse:
        """List tracked ports.

        Args:
            country: Filter by country code.
            port_type: Filter by port type.

        Returns:
            PortListResponse with port records.
        """
        params = {"country": country, "port_type": port_type}
        data = self._request("GET", "/api/v1/shipping/ports", params=params)
        return PortListResponse(**data)

    def get_port_congestion(
        self,
        query_date: Union[datetime, date, str],
        port_id: Optional[str] = None,
    ) -> CongestionResponse:
        """Get port congestion data.

        Args:
            query_date: Date to query.
            port_id: Filter by port ID.

        Returns:
            CongestionResponse with congestion data.
        """
        date_str = self._format_date(query_date)
        if isinstance(date_str, str) and "T" in date_str:
            date_str = date_str.split("T")[0]
        params = {"date": date_str, "port_id": port_id}
        data = self._request("GET", "/api/v1/shipping/congestion", params=params)
        return CongestionResponse(**data)

    # ===========================================
    # GITHUB ENDPOINTS (Phase 2)
    # ===========================================

    def list_github_repos(
        self,
        company: Optional[str] = None,
        ticker: Optional[str] = None,
    ) -> GitHubRepoListResponse:
        """List tracked GitHub repositories.

        Args:
            company: Filter by company name.
            ticker: Filter by ticker symbol.

        Returns:
            GitHubRepoListResponse with repository records.
        """
        params = {"company": company, "ticker": ticker}
        data = self._request("GET", "/api/v1/github/repos", params=params)
        return GitHubRepoListResponse(**data)

    def get_github_activity(
        self,
        repo: str,
        start_date: Optional[Union[datetime, date, str]] = None,
        end_date: Optional[Union[datetime, date, str]] = None,
    ) -> GitHubActivityResponse:
        """Get GitHub activity metrics for a repository.

        Args:
            repo: Repository full name (owner/repo).
            start_date: Start date for data range.
            end_date: End date for data range.

        Returns:
            GitHubActivityResponse with activity metrics.
        """
        params = {
            "repo": repo,
            "start_date": self._format_date(start_date),
            "end_date": self._format_date(end_date),
        }
        data = self._request("GET", "/api/v1/github/activity", params=params)
        return GitHubActivityResponse(**data)

    # ===========================================
    # SATELLITE ENDPOINTS (Phase 2)
    # ===========================================

    def get_parking_data(
        self,
        ticker: Optional[str] = None,
        start_date: Optional[Union[datetime, date, str]] = None,
        end_date: Optional[Union[datetime, date, str]] = None,
    ) -> ParkingResponse:
        """Get satellite parking lot occupancy data.

        Args:
            ticker: Filter by ticker symbol.
            start_date: Start date for data range.
            end_date: End date for data range.

        Returns:
            ParkingResponse with parking data.
        """
        params = {
            "ticker": ticker,
            "start_date": self._format_date(start_date),
            "end_date": self._format_date(end_date),
        }
        data = self._request("GET", "/api/v1/satellite/parking", params=params)
        return ParkingResponse(**data)

    def get_agricultural_data(
        self,
        region: str,
        crop_type: Optional[str] = None,
        start_date: Optional[Union[datetime, date, str]] = None,
        end_date: Optional[Union[datetime, date, str]] = None,
    ) -> AgriculturalResponse:
        """Get satellite agricultural/NDVI data.

        Args:
            region: Agricultural region.
            crop_type: Filter by crop type.
            start_date: Start date for data range.
            end_date: End date for data range.

        Returns:
            AgriculturalResponse with agricultural data.
        """
        params = {
            "region": region,
            "crop_type": crop_type,
            "start_date": self._format_date(start_date),
            "end_date": self._format_date(end_date),
        }
        data = self._request("GET", "/api/v1/satellite/agriculture", params=params)
        return AgriculturalResponse(**data)
