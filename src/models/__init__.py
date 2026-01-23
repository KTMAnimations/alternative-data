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
    DataSourceRequest,
    RequestPriority,
    RequestStatus,
    CollectorHealthLog,
    CollectorStatus,
)
from src.models.factors import Factor, FactorValue, FactorRelationship
from src.models.alerts import Alert, AlertHistory
from src.models.entity_mappings import (
    EntityMapping,
    MappingSuggestion,
    CorporateAction,
    MappingAuditLog,
    Notification,
    CoverageSnapshot,
    EntityTradingMetrics,
    MappingStatus,
    SuggestionStatus,
    CorporateActionType,
    CorporateActionStatus,
    NotificationType,
    NotificationChannel,
    AuditActionType,
)
from src.models.users import User, APIKey, UserTier
from src.models.experiments import Experiment, ExperimentMetricSnapshot, ExperimentStatus

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
    # US-033: Data Source Requests
    "DataSourceRequest",
    "RequestPriority",
    "RequestStatus",
    # US-034: Collector Health
    "CollectorHealthLog",
    "CollectorStatus",
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
    "CorporateAction",
    "MappingAuditLog",
    "Notification",
    "CoverageSnapshot",
    "EntityTradingMetrics",
    "MappingStatus",
    "SuggestionStatus",
    "CorporateActionType",
    "CorporateActionStatus",
    "NotificationType",
    "NotificationChannel",
    "AuditActionType",
    # Users
    "User",
    "APIKey",
    "UserTier",
    # Experiments (A/B Testing)
    "Experiment",
    "ExperimentMetricSnapshot",
    "ExperimentStatus",
]
