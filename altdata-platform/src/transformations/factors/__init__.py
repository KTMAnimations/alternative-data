"""Factor implementations."""

from src.transformations.factors.sec_factors import (
    InsiderTransactionMomentum,
    InsiderClusteringScore,
    EventVelocity8K,
)
from src.transformations.factors.macro_factors import (
    YieldCurveSlope,
    CreditSpreadIndex,
)
from src.transformations.factors.aviation_factors import (
    ExecutiveFlightFrequency,
    HQVisitScore,
    UnusualDestinationAlert,
    MultiCompanyColocation,
)
from src.transformations.factors.power_grid_factors import (
    GridLoadSurprise,
    RegionalPowerDemand,
    RenewableShare,
    LoadCapacityRatio,
    YoYDemandChange,
)
from src.transformations.factors.patent_factors import (
    PatentMomentum,
    InnovationVelocity,
    PatentQualityScore,
    TechnologyDiversity,
    TimeToGrant,
)
from src.transformations.factors.air_quality_factors import (
    AirQualityAnomaly,
    IndustrialActivityProxy,
    PollutionTrend,
    RegionalAQI,
)

__all__ = [
    # SEC factors
    "InsiderTransactionMomentum",
    "InsiderClusteringScore",
    "EventVelocity8K",
    # Macro factors
    "YieldCurveSlope",
    "CreditSpreadIndex",
    # Aviation factors
    "ExecutiveFlightFrequency",
    "HQVisitScore",
    "UnusualDestinationAlert",
    "MultiCompanyColocation",
    # Power grid factors
    "GridLoadSurprise",
    "RegionalPowerDemand",
    "RenewableShare",
    "LoadCapacityRatio",
    "YoYDemandChange",
    # Patent factors
    "PatentMomentum",
    "InnovationVelocity",
    "PatentQualityScore",
    "TechnologyDiversity",
    "TimeToGrant",
    # Air quality factors
    "AirQualityAnomaly",
    "IndustrialActivityProxy",
    "PollutionTrend",
    "RegionalAQI",
]
