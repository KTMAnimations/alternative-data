"""AltData SDK - Python client for the Alternative Data Platform API.

Example:
    >>> from altdata import AltDataClient
    >>> client = AltDataClient(api_key='your-api-key')
    >>> factors = client.list_factors(category='sec')
    >>> data = client.get_factor('insider_transaction_momentum', entity_id='AAPL')
    >>> df = data.to_dataframe()
"""

from .client import AltDataClient
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
    # Core responses
    HealthResponse,
    FactorResponse,
    FactorListResponse,
    FactorListItem,
    FactorValue,
    EntityResponse,
    EntityListResponse,
    SourcesResponse,
    CategoriesResponse,
    DataSource,
    CategoryInfo,
    # Phase 1 models
    FlightListResponse,
    FlightRecord,
    GridLoadResponse,
    GridLoadRecord,
    PatentListResponse,
    PatentRecord,
    AirQualityResponse,
    AirQualityRecord,
    # Phase 2 models
    WeatherResponse,
    WeatherRecord,
    WeatherForecastResponse,
    WeatherForecastRecord,
    TrendResponse,
    TrendRecord,
    SentimentResponse,
    SentimentRecord,
    PortListResponse,
    PortRecord,
    CongestionResponse,
    CongestionRecord,
    GitHubRepoListResponse,
    GitHubRepoRecord,
    GitHubActivityResponse,
    GitHubActivityRecord,
    ParkingResponse,
    ParkingRecord,
    AgriculturalResponse,
    AgriculturalRecord,
)

__version__ = "0.1.0"
__all__ = [
    # Main client
    "AltDataClient",
    # Exceptions
    "AltDataError",
    "AuthenticationError",
    "NotFoundError",
    "RateLimitError",
    "ValidationError",
    "ServerError",
    "ConnectionError",
    # Core responses
    "HealthResponse",
    "FactorResponse",
    "FactorListResponse",
    "FactorListItem",
    "FactorValue",
    "EntityResponse",
    "EntityListResponse",
    "SourcesResponse",
    "CategoriesResponse",
    "DataSource",
    "CategoryInfo",
    # Phase 1 models
    "FlightListResponse",
    "FlightRecord",
    "GridLoadResponse",
    "GridLoadRecord",
    "PatentListResponse",
    "PatentRecord",
    "AirQualityResponse",
    "AirQualityRecord",
    # Phase 2 models
    "WeatherResponse",
    "WeatherRecord",
    "WeatherForecastResponse",
    "WeatherForecastRecord",
    "TrendResponse",
    "TrendRecord",
    "SentimentResponse",
    "SentimentRecord",
    "PortListResponse",
    "PortRecord",
    "CongestionResponse",
    "CongestionRecord",
    "GitHubRepoListResponse",
    "GitHubRepoRecord",
    "GitHubActivityResponse",
    "GitHubActivityRecord",
    "ParkingResponse",
    "ParkingRecord",
    "AgriculturalResponse",
    "AgriculturalRecord",
]
