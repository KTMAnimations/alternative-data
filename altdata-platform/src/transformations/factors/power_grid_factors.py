"""Power grid-derived factor computations."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.power_grid import GridLoad, GenerationMix, ISORegion
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


def calc_grid_load_surprise(
    iso_region: str,
    timestamp: datetime,
    lookback_hours: int = 24,
) -> Optional[float]:
    """Calculate surprise in grid load vs forecast.

    High positive surprise may indicate unexpected industrial activity.

    Args:
        iso_region: ISO region code
        timestamp: Reference timestamp
        lookback_hours: Hours of data to analyze

    Returns:
        Load surprise as percentage (actual - forecast) / forecast * 100
    """
    session = SessionLocal()
    try:
        start = timestamp - timedelta(hours=lookback_hours)

        loads = (
            session.query(GridLoad)
            .filter(
                GridLoad.iso_region == iso_region,
                GridLoad.timestamp >= start,
                GridLoad.timestamp <= timestamp,
                GridLoad.load_mw.isnot(None),
                GridLoad.forecast_mw.isnot(None),
            )
            .all()
        )

        if not loads:
            return None

        # Calculate average surprise
        surprises = []
        for load in loads:
            if load.forecast_mw and load.forecast_mw > 0:
                surprise = (load.load_mw - load.forecast_mw) / load.forecast_mw * 100
                surprises.append(surprise)

        if not surprises:
            return None

        return sum(surprises) / len(surprises)
    finally:
        session.close()


def calc_regional_power_demand(
    iso_region: str,
    timestamp: datetime,
    lookback_hours: int = 168,  # 1 week
) -> Optional[float]:
    """Calculate average regional power demand.

    Proxy for industrial and economic activity level.

    Args:
        iso_region: ISO region code
        timestamp: Reference timestamp
        lookback_hours: Hours of data to average

    Returns:
        Average load in MW
    """
    session = SessionLocal()
    try:
        start = timestamp - timedelta(hours=lookback_hours)

        avg_load = (
            session.query(func.avg(GridLoad.load_mw))
            .filter(
                GridLoad.iso_region == iso_region,
                GridLoad.timestamp >= start,
                GridLoad.timestamp <= timestamp,
                GridLoad.load_mw.isnot(None),
            )
            .scalar()
        )

        return float(avg_load) if avg_load else None
    finally:
        session.close()


def calc_renewable_share(
    iso_region: str,
    timestamp: datetime,
    lookback_hours: int = 24,
) -> Optional[float]:
    """Calculate renewable energy share of generation.

    Useful for tracking green energy adoption trends.

    Args:
        iso_region: ISO region code
        timestamp: Reference timestamp
        lookback_hours: Hours of data to average

    Returns:
        Renewable percentage (0-100)
    """
    session = SessionLocal()
    try:
        start = timestamp - timedelta(hours=lookback_hours)

        gen_records = (
            session.query(GenerationMix)
            .filter(
                GenerationMix.iso_region == iso_region,
                GenerationMix.timestamp >= start,
                GenerationMix.timestamp <= timestamp,
            )
            .all()
        )

        if not gen_records:
            return None

        total_renewable = 0
        total_generation = 0

        for gen in gen_records:
            renewable = (gen.wind_mw or 0) + (gen.solar_mw or 0) + (gen.hydro_mw or 0)
            total = gen.total_generation_mw or 0

            total_renewable += renewable
            total_generation += total

        if total_generation == 0:
            return None

        return (total_renewable / total_generation) * 100
    finally:
        session.close()


def calc_load_capacity_ratio(
    iso_region: str,
    timestamp: datetime,
) -> Optional[float]:
    """Calculate load as percentage of available capacity.

    High ratios may indicate grid stress and potential reliability issues.

    Args:
        iso_region: ISO region code
        timestamp: Reference timestamp

    Returns:
        Load/Capacity ratio as percentage
    """
    session = SessionLocal()
    try:
        load = (
            session.query(GridLoad)
            .filter(
                GridLoad.iso_region == iso_region,
                GridLoad.timestamp <= timestamp,
                GridLoad.load_mw.isnot(None),
                GridLoad.capacity_mw.isnot(None),
            )
            .order_by(GridLoad.timestamp.desc())
            .first()
        )

        if not load or not load.capacity_mw:
            return None

        return (load.load_mw / load.capacity_mw) * 100
    finally:
        session.close()


def calc_yoy_demand_change(
    iso_region: str,
    timestamp: datetime,
    comparison_days: int = 7,
) -> Optional[float]:
    """Calculate year-over-year demand change.

    Useful for identifying secular growth or decline in economic activity.

    Args:
        iso_region: ISO region code
        timestamp: Current reference timestamp
        comparison_days: Days of data to compare

    Returns:
        YoY change as percentage
    """
    session = SessionLocal()
    try:
        # Current period
        current_start = timestamp - timedelta(days=comparison_days)
        current_avg = (
            session.query(func.avg(GridLoad.load_mw))
            .filter(
                GridLoad.iso_region == iso_region,
                GridLoad.timestamp >= current_start,
                GridLoad.timestamp <= timestamp,
            )
            .scalar()
        )

        # Year ago period
        yoy_timestamp = timestamp - timedelta(days=365)
        yoy_start = yoy_timestamp - timedelta(days=comparison_days)
        yoy_avg = (
            session.query(func.avg(GridLoad.load_mw))
            .filter(
                GridLoad.iso_region == iso_region,
                GridLoad.timestamp >= yoy_start,
                GridLoad.timestamp <= yoy_timestamp,
            )
            .scalar()
        )

        if not current_avg or not yoy_avg or yoy_avg == 0:
            return None

        return ((current_avg - yoy_avg) / yoy_avg) * 100
    finally:
        session.close()


@FactorRegistry.register
class GridLoadSurprise(BaseFactor):
    """Grid Load Surprise Factor.

    Measures deviation of actual load from forecast,
    indicating unexpected industrial activity.
    """

    FACTOR_NAME = "grid_load_surprise"
    FACTOR_DESCRIPTION = "Actual grid load vs forecast deviation percentage"
    CATEGORY = "power_grid"
    ENTITY_TYPE = "iso_region"
    FREQUENCY = "hourly"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,  # ISO region code
        as_of_date: datetime,
        lookback_hours: int = 24,
    ) -> Optional[float]:
        """Compute grid load surprise.

        Args:
            entity_id: ISO region code (CAISO, ERCOT, PJM, MISO)
            as_of_date: Timestamp for computation
            lookback_hours: Hours of data to analyze

        Returns:
            Surprise percentage
        """
        return calc_grid_load_surprise(entity_id, as_of_date, lookback_hours)


@FactorRegistry.register
class RegionalPowerDemand(BaseFactor):
    """Regional Power Demand Factor.

    Average power demand as proxy for economic activity.
    """

    FACTOR_NAME = "regional_power_demand"
    FACTOR_DESCRIPTION = "Average regional power demand in MW"
    CATEGORY = "power_grid"
    ENTITY_TYPE = "iso_region"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_hours: int = 168,
    ) -> Optional[float]:
        """Compute regional power demand.

        Args:
            entity_id: ISO region code
            as_of_date: Date for computation
            lookback_hours: Hours to average

        Returns:
            Average load in MW
        """
        return calc_regional_power_demand(entity_id, as_of_date, lookback_hours)


@FactorRegistry.register
class RenewableShare(BaseFactor):
    """Renewable Energy Share Factor.

    Percentage of generation from renewable sources.
    """

    FACTOR_NAME = "renewable_share"
    FACTOR_DESCRIPTION = "Renewable energy percentage of total generation"
    CATEGORY = "power_grid"
    ENTITY_TYPE = "iso_region"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_hours: int = 24,
    ) -> Optional[float]:
        """Compute renewable share.

        Args:
            entity_id: ISO region code
            as_of_date: Date for computation
            lookback_hours: Hours to average

        Returns:
            Renewable percentage (0-100)
        """
        return calc_renewable_share(entity_id, as_of_date, lookback_hours)


@FactorRegistry.register
class LoadCapacityRatio(BaseFactor):
    """Load Capacity Ratio Factor.

    Current load as percentage of available capacity.
    High values indicate grid stress.
    """

    FACTOR_NAME = "load_capacity_ratio"
    FACTOR_DESCRIPTION = "Grid load as percentage of available capacity"
    CATEGORY = "power_grid"
    ENTITY_TYPE = "iso_region"
    FREQUENCY = "hourly"
    LOOKBACK_DAYS = 0

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute load capacity ratio.

        Args:
            entity_id: ISO region code
            as_of_date: Timestamp for computation

        Returns:
            Load/Capacity ratio percentage
        """
        return calc_load_capacity_ratio(entity_id, as_of_date)


@FactorRegistry.register
class YoYDemandChange(BaseFactor):
    """Year-over-Year Demand Change Factor.

    YoY change in power demand indicating economic growth/decline.
    """

    FACTOR_NAME = "yoy_demand_change"
    FACTOR_DESCRIPTION = "Year-over-year change in power demand percentage"
    CATEGORY = "power_grid"
    ENTITY_TYPE = "iso_region"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        comparison_days: int = 7,
    ) -> Optional[float]:
        """Compute YoY demand change.

        Args:
            entity_id: ISO region code
            as_of_date: Date for computation
            comparison_days: Days to compare

        Returns:
            YoY change percentage
        """
        return calc_yoy_demand_change(entity_id, as_of_date, comparison_days)
