"""SQLAlchemy models package."""

from src.models.base import Base, TimestampMixin
from src.models.data_sources import (
    TSACheckpoint,
    OpenTableMetrics,
    EarthquakeEvent,
    CarbonIntensityReading,
    BuildingPermitData,
    BoxOfficeDaily,
    CloudflareRadarMetrics,
    ZillowRentalIndex,
    DataSource,
)
from src.models.factors import Factor, FactorValue, FactorRelationship
from src.models.alerts import Alert, AlertHistory
from src.models.entity_mappings import EntityMapping, MappingSuggestion
from src.models.users import User, APIKey, UserTier

__all__ = [
    "Base",
    "TimestampMixin",
    # Data Sources
    "TSACheckpoint",
    "OpenTableMetrics",
    "EarthquakeEvent",
    "CarbonIntensityReading",
    "BuildingPermitData",
    "BoxOfficeDaily",
    "CloudflareRadarMetrics",
    "ZillowRentalIndex",
    "DataSource",
    # Factors
    "Factor",
    "FactorValue",
    "FactorRelationship",
    # Alerts
    "Alert",
    "AlertHistory",
    # Entity Mapping
    "EntityMapping",
    "MappingSuggestion",
    # Users
    "User",
    "APIKey",
    "UserTier",
]
