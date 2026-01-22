"""Pydantic models for AltData SDK responses."""

from datetime import datetime, date
from typing import Optional, List, Dict, Any

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """API health status response."""

    status: str
    timestamp: datetime
    database: str
    redis: str
    version: str


class FactorValue(BaseModel):
    """A single factor value at a point in time."""

    date: datetime
    value: Optional[float] = None
    version: int = 1


class FactorResponse(BaseModel):
    """Response containing factor values for an entity."""

    factor_name: str
    entity_id: str
    entity_type: str
    values: List[FactorValue]
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert factor values to a pandas DataFrame.

        Returns:
            DataFrame with columns: date, value, version
        """
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [
            {"date": v.date, "value": v.value, "version": v.version}
            for v in self.values
        ]
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.set_index("date").sort_index()
        return df


class FactorListItem(BaseModel):
    """A factor in the factor list."""

    id: str
    name: str
    description: Optional[str] = None
    category: str
    frequency: str


class FactorListResponse(BaseModel):
    """Response containing a list of available factors."""

    factors: List[FactorListItem]
    total: int

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert factor list to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [f.model_dump() for f in self.factors]
        return pd.DataFrame(data)


class EntityResponse(BaseModel):
    """An entity (company, region, etc.)."""

    id: str
    name: str
    ticker: Optional[str] = None
    entity_type: str
    sector: Optional[str] = None
    industry: Optional[str] = None


class EntityListResponse(BaseModel):
    """Response containing a list of entities."""

    entities: List[EntityResponse]
    total: int
    page: int
    page_size: int

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert entity list to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [e.model_dump() for e in self.entities]
        return pd.DataFrame(data)


class DataSource(BaseModel):
    """A data source configuration."""

    id: str
    name: str
    category: str
    status: str
    update_frequency: str
    factors: List[str]


class SourcesResponse(BaseModel):
    """Response containing data sources."""

    sources: List[DataSource]

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert sources to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [s.model_dump() for s in self.sources]
        return pd.DataFrame(data)


class CategoryInfo(BaseModel):
    """Information about a factor category."""

    id: str
    name: str
    count: int
    factors: List[str]


class CategoriesResponse(BaseModel):
    """Response containing factor categories."""

    categories: List[CategoryInfo]

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert categories to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [c.model_dump() for c in self.categories]
        return pd.DataFrame(data)


# Phase 1 Models


class FlightRecord(BaseModel):
    """A corporate flight record."""

    icao_hex: str
    registration: Optional[str] = None
    landing_timestamp: datetime
    airport_icao: Optional[str] = None
    airport_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    nearest_company_hq: Optional[str] = None
    distance_to_hq_km: Optional[float] = None


class FlightListResponse(BaseModel):
    """Response containing corporate flight data."""

    company_id: str
    flights: List[FlightRecord]
    total: int

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert flight data to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [f.model_dump() for f in self.flights]
        df = pd.DataFrame(data)
        if not df.empty and "landing_timestamp" in df.columns:
            df = df.set_index("landing_timestamp").sort_index()
        return df


class GridLoadRecord(BaseModel):
    """A power grid load reading."""

    iso_region: str
    timestamp: datetime
    load_mw: Optional[float] = None
    forecast_mw: Optional[float] = None
    capacity_mw: Optional[float] = None
    load_pct_of_capacity: Optional[float] = None


class GridLoadResponse(BaseModel):
    """Response containing power grid load data."""

    iso: str
    date: date
    readings: List[GridLoadRecord]
    total: int

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert grid load data to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [r.model_dump() for r in self.readings]
        df = pd.DataFrame(data)
        if not df.empty and "timestamp" in df.columns:
            df = df.set_index("timestamp").sort_index()
        return df


class PatentRecord(BaseModel):
    """A patent record."""

    patent_number: str
    application_number: Optional[str] = None
    title: Optional[str] = None
    filing_date: Optional[date] = None
    grant_date: Optional[date] = None
    status: Optional[str] = None
    primary_class: Optional[str] = None
    claims_count: Optional[int] = None


class PatentListResponse(BaseModel):
    """Response containing patent data."""

    company_id: str
    patents: List[PatentRecord]
    total: int

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert patent data to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [p.model_dump() for p in self.patents]
        return pd.DataFrame(data)


class AirQualityRecord(BaseModel):
    """An air quality reading."""

    location_id: Optional[str] = None
    location_name: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    timestamp: datetime
    parameter: str
    value: Optional[float] = None
    unit: Optional[str] = None
    aqi: Optional[int] = None


class AirQualityResponse(BaseModel):
    """Response containing air quality data."""

    city: Optional[str] = None
    country: Optional[str] = None
    date: date
    readings: List[AirQualityRecord]
    total: int

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert air quality data to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [r.model_dump() for r in self.readings]
        df = pd.DataFrame(data)
        if not df.empty and "timestamp" in df.columns:
            df = df.set_index("timestamp").sort_index()
        return df


# Phase 2 Models


class WeatherRecord(BaseModel):
    """A weather observation."""

    city: str
    timestamp: datetime
    temp_c: Optional[float] = None
    temp_feels_like_c: Optional[float] = None
    humidity_pct: Optional[int] = None
    wind_speed_ms: Optional[float] = None
    weather_main: Optional[str] = None
    pressure_hpa: Optional[int] = None


class WeatherResponse(BaseModel):
    """Response containing weather observations."""

    city: str
    date: date
    observations: List[WeatherRecord]
    total: int

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert weather data to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [o.model_dump() for o in self.observations]
        df = pd.DataFrame(data)
        if not df.empty and "timestamp" in df.columns:
            df = df.set_index("timestamp").sort_index()
        return df


class WeatherForecastRecord(BaseModel):
    """A weather forecast record."""

    city: str
    forecast_timestamp: datetime
    temp_c: Optional[float] = None
    humidity_pct: Optional[int] = None
    wind_speed_ms: Optional[float] = None
    weather_main: Optional[str] = None
    pop: Optional[float] = None


class WeatherForecastResponse(BaseModel):
    """Response containing weather forecasts."""

    city: str
    forecasts: List[WeatherForecastRecord]
    total: int

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert forecast data to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [f.model_dump() for f in self.forecasts]
        df = pd.DataFrame(data)
        if not df.empty and "forecast_timestamp" in df.columns:
            df = df.set_index("forecast_timestamp").sort_index()
        return df


class TrendRecord(BaseModel):
    """A Google Trends data point."""

    keyword: str
    date: date
    interest: Optional[int] = None
    is_partial: bool = False
    geo: Optional[str] = None


class TrendResponse(BaseModel):
    """Response containing Google Trends data."""

    keyword: str
    geo: Optional[str] = None
    data: List[TrendRecord]
    total: int

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert trends data to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [t.model_dump() for t in self.data]
        df = pd.DataFrame(data)
        if not df.empty and "date" in df.columns:
            df = df.set_index("date").sort_index()
        return df


class SentimentRecord(BaseModel):
    """A ticker sentiment data point."""

    ticker: str
    date: date
    avg_sentiment: Optional[float] = None
    mention_count: Optional[int] = None
    positive_mentions: Optional[int] = None
    negative_mentions: Optional[int] = None
    neutral_mentions: Optional[int] = None


class SentimentResponse(BaseModel):
    """Response containing ticker sentiment data."""

    ticker: str
    data: List[SentimentRecord]
    total: int

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert sentiment data to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [s.model_dump() for s in self.data]
        df = pd.DataFrame(data)
        if not df.empty and "date" in df.columns:
            df = df.set_index("date").sort_index()
        return df


class PortRecord(BaseModel):
    """A shipping port."""

    port_id: str
    port_name: str
    country: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    port_type: Optional[str] = None


class PortListResponse(BaseModel):
    """Response containing ports list."""

    ports: List[PortRecord]
    total: int

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert ports data to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [p.model_dump() for p in self.ports]
        return pd.DataFrame(data)


class CongestionRecord(BaseModel):
    """A port congestion data point."""

    port_id: str
    port_name: Optional[str] = None
    date: date
    congestion_index: Optional[float] = None
    vessels_waiting: Optional[int] = None
    avg_wait_hours: Optional[float] = None


class CongestionResponse(BaseModel):
    """Response containing port congestion data."""

    port_id: Optional[str] = None
    date: date
    data: List[CongestionRecord]
    total: int

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert congestion data to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [c.model_dump() for c in self.data]
        df = pd.DataFrame(data)
        if not df.empty and "date" in df.columns:
            df = df.set_index("date").sort_index()
        return df


class GitHubRepoRecord(BaseModel):
    """A GitHub repository."""

    full_name: str
    company: Optional[str] = None
    ticker: Optional[str] = None
    stars: Optional[int] = None
    forks: Optional[int] = None
    open_issues: Optional[int] = None
    language: Optional[str] = None


class GitHubRepoListResponse(BaseModel):
    """Response containing GitHub repositories."""

    repos: List[GitHubRepoRecord]
    total: int

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert repos data to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [r.model_dump() for r in self.repos]
        return pd.DataFrame(data)


class GitHubActivityRecord(BaseModel):
    """GitHub repository activity metrics."""

    full_name: str
    date: date
    commits_24h: Optional[int] = None
    prs_opened_24h: Optional[int] = None
    prs_merged_24h: Optional[int] = None
    issues_opened_24h: Optional[int] = None
    unique_committers_24h: Optional[int] = None


class GitHubActivityResponse(BaseModel):
    """Response containing GitHub activity data."""

    repo: str
    data: List[GitHubActivityRecord]
    total: int

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert activity data to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [a.model_dump() for a in self.data]
        df = pd.DataFrame(data)
        if not df.empty and "date" in df.columns:
            df = df.set_index("date").sort_index()
        return df


class ParkingRecord(BaseModel):
    """Satellite parking lot data."""

    location_id: str
    location_name: Optional[str] = None
    ticker: Optional[str] = None
    date: date
    occupancy_rate: Optional[float] = None
    cars_detected: Optional[int] = None
    confidence_score: Optional[float] = None


class ParkingResponse(BaseModel):
    """Response containing parking lot data."""

    ticker: Optional[str] = None
    data: List[ParkingRecord]
    total: int

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert parking data to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [p.model_dump() for p in self.data]
        df = pd.DataFrame(data)
        if not df.empty and "date" in df.columns:
            df = df.set_index("date").sort_index()
        return df


class AgriculturalRecord(BaseModel):
    """Satellite agricultural data."""

    location_id: str
    region: str
    crop_type: Optional[str] = None
    date: date
    ndvi_mean: Optional[float] = None
    crop_health_score: Optional[float] = None
    ndvi_vs_historical: Optional[float] = None


class AgriculturalResponse(BaseModel):
    """Response containing agricultural data."""

    region: str
    crop_type: Optional[str] = None
    data: List[AgriculturalRecord]
    total: int

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert agricultural data to a pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")
        data = [a.model_dump() for a in self.data]
        df = pd.DataFrame(data)
        if not df.empty and "date" in df.columns:
            df = df.set_index("date").sort_index()
        return df
