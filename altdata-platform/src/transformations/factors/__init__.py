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
from src.transformations.factors.weather_factors import (
    HeatingDegreeDays,
    CoolingDegreeDays,
    RetailWeatherIndex,
    AgriculturalStressIndex,
    WeatherYoYAnomaly,
    PrecipitationAnomaly,
)
from src.transformations.factors.trends_factors import (
    SearchMomentum,
    SearchVolatility,
    SearchYoYChange,
    CategoryInterest,
    RetailSentimentIndex,
)
from src.transformations.factors.sentiment_factors import (
    TickerSentiment,
    MentionVelocity,
    SentimentMomentum,
    WSBSentiment,
    RetailAttentionIndex,
    SentimentDispersion,
)
from src.transformations.factors.shipping_factors import (
    PortCongestionIndex,
    PortActivityChange,
    ContainerVesselCount,
    TankerActivityIndex,
    GlobalCongestionIndex,
    ChinaUSTradeFlow,
)
from src.transformations.factors.github_factors import (
    DeveloperVelocity,
    CommitMomentum,
    ReleaseFrequency,
    StarGrowthRate,
    ContributorDiversity,
    TechSectorActivity,
)
from src.transformations.factors.satellite_factors import (
    ParkingOccupancy,
    ParkingTrend,
    ConstructionProgress,
    CropHealthIndex,
    NDVIAnomaly,
    RetailTrafficProxy,
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
    # Weather factors
    "HeatingDegreeDays",
    "CoolingDegreeDays",
    "RetailWeatherIndex",
    "AgriculturalStressIndex",
    "WeatherYoYAnomaly",
    "PrecipitationAnomaly",
    # Trends factors
    "SearchMomentum",
    "SearchVolatility",
    "SearchYoYChange",
    "CategoryInterest",
    "RetailSentimentIndex",
    # Sentiment factors
    "TickerSentiment",
    "MentionVelocity",
    "SentimentMomentum",
    "WSBSentiment",
    "RetailAttentionIndex",
    "SentimentDispersion",
    # Shipping factors
    "PortCongestionIndex",
    "PortActivityChange",
    "ContainerVesselCount",
    "TankerActivityIndex",
    "GlobalCongestionIndex",
    "ChinaUSTradeFlow",
    # GitHub factors
    "DeveloperVelocity",
    "CommitMomentum",
    "ReleaseFrequency",
    "StarGrowthRate",
    "ContributorDiversity",
    "TechSectorActivity",
    # Satellite factors
    "ParkingOccupancy",
    "ParkingTrend",
    "ConstructionProgress",
    "CropHealthIndex",
    "NDVIAnomaly",
    "RetailTrafficProxy",
]
