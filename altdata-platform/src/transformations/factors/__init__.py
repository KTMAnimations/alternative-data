"""Factor implementations."""

from src.transformations.factors.sec_factors import (
    InsiderTransactionMomentum,
    InsiderClusteringScore,
    EventVelocity8K,
    InsiderBuyRatio,
    FilingSentimentScore,
    InsiderSizePercentile,
    CXOTransactionFlag,
    Form4TimingScore,
)
from src.transformations.factors.macro_factors import (
    YieldCurveSlope,
    CreditSpreadIndex,
    InflationExpectations,
    FinancialConditionsIndex,
    YieldCurveInversion,
    MoneySupplyGrowth,
    JoblessClaimsMomentum,
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
    IndustrialLoadIndex,
    WeatherAdjustedDemand,
    PeakDemandRatio,
    GridStressIndicator,
    CrossISOFlow,
)
from src.transformations.factors.patent_factors import (
    PatentMomentum,
    InnovationVelocity,
    PatentQualityScore,
    TechnologyDiversity,
    TimeToGrant,
    PatentGrantRate,
    PatentBreadthIndex,
    RAndDIntensityProxy,
    InventorRetention,
)
from src.transformations.factors.air_quality_factors import (
    AirQualityAnomaly,
    IndustrialActivityProxy,
    PollutionTrend,
    RegionalAQI,
    PollutionYoYChange,
    SeasonalAdjustedAQI,
    CrossBorderPollution,
)
from src.transformations.factors.weather_factors import (
    HeatingDegreeDays,
    CoolingDegreeDays,
    RetailWeatherIndex,
    AgriculturalStressIndex,
    WeatherYoYAnomaly,
    PrecipitationAnomaly,
    SevereWeatherExposure,
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
    # SEC factors (8)
    "InsiderTransactionMomentum",
    "InsiderClusteringScore",
    "EventVelocity8K",
    "InsiderBuyRatio",
    "FilingSentimentScore",
    "InsiderSizePercentile",
    "CXOTransactionFlag",
    "Form4TimingScore",
    # Macro factors (7)
    "YieldCurveSlope",
    "CreditSpreadIndex",
    "InflationExpectations",
    "FinancialConditionsIndex",
    "YieldCurveInversion",
    "MoneySupplyGrowth",
    "JoblessClaimsMomentum",
    # Aviation factors (4)
    "ExecutiveFlightFrequency",
    "HQVisitScore",
    "UnusualDestinationAlert",
    "MultiCompanyColocation",
    # Power grid factors (10)
    "GridLoadSurprise",
    "RegionalPowerDemand",
    "RenewableShare",
    "LoadCapacityRatio",
    "YoYDemandChange",
    "IndustrialLoadIndex",
    "WeatherAdjustedDemand",
    "PeakDemandRatio",
    "GridStressIndicator",
    "CrossISOFlow",
    # Patent factors (9)
    "PatentMomentum",
    "InnovationVelocity",
    "PatentQualityScore",
    "TechnologyDiversity",
    "TimeToGrant",
    "PatentGrantRate",
    "PatentBreadthIndex",
    "RAndDIntensityProxy",
    "InventorRetention",
    # Air quality factors (7)
    "AirQualityAnomaly",
    "IndustrialActivityProxy",
    "PollutionTrend",
    "RegionalAQI",
    "PollutionYoYChange",
    "SeasonalAdjustedAQI",
    "CrossBorderPollution",
    # Weather factors (7)
    "HeatingDegreeDays",
    "CoolingDegreeDays",
    "RetailWeatherIndex",
    "AgriculturalStressIndex",
    "WeatherYoYAnomaly",
    "PrecipitationAnomaly",
    "SevereWeatherExposure",
    # Trends factors (5)
    "SearchMomentum",
    "SearchVolatility",
    "SearchYoYChange",
    "CategoryInterest",
    "RetailSentimentIndex",
    # Sentiment factors (6)
    "TickerSentiment",
    "MentionVelocity",
    "SentimentMomentum",
    "WSBSentiment",
    "RetailAttentionIndex",
    "SentimentDispersion",
    # Shipping factors (6)
    "PortCongestionIndex",
    "PortActivityChange",
    "ContainerVesselCount",
    "TankerActivityIndex",
    "GlobalCongestionIndex",
    "ChinaUSTradeFlow",
    # GitHub factors (6)
    "DeveloperVelocity",
    "CommitMomentum",
    "ReleaseFrequency",
    "StarGrowthRate",
    "ContributorDiversity",
    "TechSectorActivity",
    # Satellite factors (6)
    "ParkingOccupancy",
    "ParkingTrend",
    "ConstructionProgress",
    "CropHealthIndex",
    "NDVIAnomaly",
    "RetailTrafficProxy",
]
