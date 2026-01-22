"""Satellite imagery-derived factor computations."""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.satellite import (
    SatelliteLocation,
    ParkingLotMetrics,
    ConstructionMetrics,
    AgriculturalMetrics,
    PortActivityMetrics,
)
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


def calc_parking_occupancy(
    ticker: str,
    target_date: date,
    lookback_days: int = 7,
) -> Optional[float]:
    """Calculate average parking lot occupancy for a ticker.

    Args:
        ticker: Stock ticker
        target_date: Reference date
        lookback_days: Days to average

    Returns:
        Average occupancy rate (0-1)
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        avg_occupancy = (
            session.query(func.avg(ParkingLotMetrics.occupancy_rate))
            .filter(
                ParkingLotMetrics.ticker == ticker,
                ParkingLotMetrics.observation_date >= start_date,
                ParkingLotMetrics.observation_date <= target_date,
                ParkingLotMetrics.occupancy_rate.isnot(None),
            )
            .scalar()
        )

        return float(avg_occupancy) if avg_occupancy is not None else None
    finally:
        session.close()


def calc_parking_trend(
    ticker: str,
    target_date: date,
    short_window: int = 7,
    long_window: int = 30,
) -> Optional[float]:
    """Calculate parking occupancy trend.

    Args:
        ticker: Stock ticker
        target_date: Reference date
        short_window: Short-term window
        long_window: Long-term window

    Returns:
        Trend value (positive = increasing)
    """
    session = SessionLocal()
    try:
        short_start = target_date - timedelta(days=short_window)
        long_start = target_date - timedelta(days=long_window)

        short_avg = (
            session.query(func.avg(ParkingLotMetrics.occupancy_rate))
            .filter(
                ParkingLotMetrics.ticker == ticker,
                ParkingLotMetrics.observation_date >= short_start,
                ParkingLotMetrics.observation_date <= target_date,
            )
            .scalar()
        )

        long_avg = (
            session.query(func.avg(ParkingLotMetrics.occupancy_rate))
            .filter(
                ParkingLotMetrics.ticker == ticker,
                ParkingLotMetrics.observation_date >= long_start,
                ParkingLotMetrics.observation_date <= target_date,
            )
            .scalar()
        )

        if short_avg is None or long_avg is None:
            return None

        return float(short_avg) - float(long_avg)
    finally:
        session.close()


def calc_construction_progress(
    location_id: str,
    target_date: date,
) -> Optional[float]:
    """Calculate construction progress score.

    Args:
        location_id: Construction site location ID
        target_date: Reference date

    Returns:
        Estimated completion percentage
    """
    session = SessionLocal()
    try:
        latest = (
            session.query(ConstructionMetrics)
            .filter(
                ConstructionMetrics.location_id == location_id,
                ConstructionMetrics.observation_date <= target_date,
            )
            .order_by(ConstructionMetrics.observation_date.desc())
            .first()
        )

        if not latest:
            return None

        return latest.estimated_completion_pct
    finally:
        session.close()


def calc_crop_health_index(
    region: str,
    target_date: date,
    crop_type: Optional[str] = None,
) -> Optional[float]:
    """Calculate crop health index from NDVI.

    Args:
        region: Agricultural region
        target_date: Reference date
        crop_type: Optional specific crop type

    Returns:
        Crop health score (0-100)
    """
    session = SessionLocal()
    try:
        query = session.query(func.avg(AgriculturalMetrics.crop_health_score)).filter(
            AgriculturalMetrics.region == region,
            AgriculturalMetrics.observation_date == target_date,
        )

        if crop_type:
            query = query.filter(AgriculturalMetrics.crop_type == crop_type)

        result = query.scalar()
        return float(result) if result is not None else None
    finally:
        session.close()


def calc_ndvi_anomaly(
    region: str,
    target_date: date,
) -> Optional[float]:
    """Calculate NDVI anomaly vs historical average.

    Args:
        region: Agricultural region
        target_date: Reference date

    Returns:
        NDVI anomaly (% difference from historical)
    """
    session = SessionLocal()
    try:
        latest = (
            session.query(AgriculturalMetrics.ndvi_vs_historical)
            .filter(
                AgriculturalMetrics.region == region,
                AgriculturalMetrics.observation_date == target_date,
            )
            .first()
        )

        return float(latest[0]) if latest and latest[0] is not None else None
    finally:
        session.close()


def calc_port_container_activity(
    port_id: str,
    target_date: date,
) -> Optional[float]:
    """Calculate port container activity index.

    Args:
        port_id: Port identifier
        target_date: Reference date

    Returns:
        Activity index (0-100)
    """
    session = SessionLocal()
    try:
        latest = (
            session.query(PortActivityMetrics.activity_index)
            .filter(
                PortActivityMetrics.port_id == port_id,
                PortActivityMetrics.observation_date <= target_date,
            )
            .order_by(PortActivityMetrics.observation_date.desc())
            .first()
        )

        return float(latest[0]) if latest and latest[0] is not None else None
    finally:
        session.close()


def calc_retail_foot_traffic_proxy(
    tickers: Optional[List[str]] = None,
    target_date: date = None,
) -> Optional[float]:
    """Calculate retail foot traffic proxy from parking data.

    Args:
        tickers: List of retail tickers to include
        target_date: Reference date

    Returns:
        Average occupancy across retail locations
    """
    if target_date is None:
        target_date = date.today()

    default_tickers = ["WMT", "TGT", "COST", "HD", "LOW"]
    tickers = tickers or default_tickers

    session = SessionLocal()
    try:
        avg_occupancy = (
            session.query(func.avg(ParkingLotMetrics.occupancy_rate))
            .filter(
                ParkingLotMetrics.ticker.in_(tickers),
                ParkingLotMetrics.observation_date == target_date,
                ParkingLotMetrics.occupancy_rate.isnot(None),
            )
            .scalar()
        )

        return float(avg_occupancy) * 100 if avg_occupancy is not None else None
    finally:
        session.close()


@FactorRegistry.register
class ParkingOccupancy(BaseFactor):
    """Parking Lot Occupancy Factor.

    Measures parking lot utilization as proxy for store traffic.
    """

    FACTOR_NAME = "parking_occupancy"
    FACTOR_DESCRIPTION = "Parking lot occupancy rate (0-1)"
    CATEGORY = "satellite"
    ENTITY_TYPE = "ticker"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,  # Ticker
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute parking occupancy."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_parking_occupancy(entity_id, target_date, lookback_days)


@FactorRegistry.register
class ParkingTrend(BaseFactor):
    """Parking Trend Factor.

    Measures change in parking occupancy over time.
    Positive = increasing traffic, Negative = decreasing.
    """

    FACTOR_NAME = "parking_trend"
    FACTOR_DESCRIPTION = "Parking occupancy trend (7d vs 30d)"
    CATEGORY = "satellite"
    ENTITY_TYPE = "ticker"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute parking trend."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_parking_trend(entity_id, target_date)


@FactorRegistry.register
class ConstructionProgress(BaseFactor):
    """Construction Progress Factor.

    Tracks progress of major construction projects.
    """

    FACTOR_NAME = "construction_progress"
    FACTOR_DESCRIPTION = "Construction completion estimate (%)"
    CATEGORY = "satellite"
    ENTITY_TYPE = "location"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,  # Location ID
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute construction progress."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_construction_progress(entity_id, target_date)


@FactorRegistry.register
class CropHealthIndex(BaseFactor):
    """Crop Health Index Factor.

    Measures agricultural health from NDVI analysis.
    Higher = healthier crops.
    """

    FACTOR_NAME = "crop_health_index"
    FACTOR_DESCRIPTION = "Crop health from satellite imagery (0-100)"
    CATEGORY = "satellite"
    ENTITY_TYPE = "region"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,  # Region name
        as_of_date: datetime,
        crop_type: Optional[str] = None,
    ) -> Optional[float]:
        """Compute crop health index."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_crop_health_index(entity_id, target_date, crop_type)


@FactorRegistry.register
class NDVIAnomaly(BaseFactor):
    """NDVI Anomaly Factor.

    Measures vegetation deviation from historical average.
    Negative = below normal (drought/stress), Positive = above normal.
    """

    FACTOR_NAME = "ndvi_anomaly"
    FACTOR_DESCRIPTION = "NDVI anomaly vs historical (%)"
    CATEGORY = "satellite"
    ENTITY_TYPE = "region"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute NDVI anomaly."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_ndvi_anomaly(entity_id, target_date)


@FactorRegistry.register
class RetailTrafficProxy(BaseFactor):
    """Retail Traffic Proxy Factor.

    Aggregate retail foot traffic from parking lot satellite data.
    """

    FACTOR_NAME = "retail_traffic_proxy"
    FACTOR_DESCRIPTION = "Retail traffic proxy from satellite parking data"
    CATEGORY = "satellite"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,  # Ignored
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute retail traffic proxy."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_retail_foot_traffic_proxy(target_date=target_date)
