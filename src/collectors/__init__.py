"""Data collectors package."""

from src.collectors.base import BaseCollector, CollectorResult, FetchError, ParseError
from src.collectors.tsa_checkpoint import (
    TSACheckpointCollector,
    is_holiday_period,
)
from src.collectors.carbon_intensity import (
    CarbonIntensityCollector,
    create_carbon_intensity_collector,
)
from src.collectors.opentable import (
    OpenTableCollector,
    collect_opentable_data,
    EXPECTED_REGIONS as OPENTABLE_REGIONS,
    PRIMARY_ENTITIES as OPENTABLE_ENTITIES,
)
from src.collectors.cloudflare_radar import CloudflareRadarCollector
from src.collectors.fred_collector import FREDCollector, FRED_SERIES
from src.collectors.zillow_rental import ZillowRentalCollector
from src.collectors.usgs_earthquake import USGSEarthquakeCollector
from src.collectors.boxoffice import BoxOfficeCollector

__all__ = [
    "BaseCollector",
    "CollectorResult",
    "FetchError",
    "ParseError",
    "TSACheckpointCollector",
    "is_holiday_period",
    "CarbonIntensityCollector",
    "create_carbon_intensity_collector",
    "OpenTableCollector",
    "collect_opentable_data",
    "OPENTABLE_REGIONS",
    "OPENTABLE_ENTITIES",
    "CloudflareRadarCollector",
    "FREDCollector",
    "FRED_SERIES",
    "ZillowRentalCollector",
    "USGSEarthquakeCollector",
    "BoxOfficeCollector",
]
