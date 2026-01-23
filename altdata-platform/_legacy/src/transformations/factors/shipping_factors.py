"""Shipping and port activity-derived factor computations."""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.shipping import (
    VesselPosition,
    PortCall,
    PortCongestion,
    GlobalShippingIndex,
    Vessel,
)
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


def calc_port_congestion_index(
    port_id: str,
    target_date: date,
) -> Optional[float]:
    """Calculate port congestion index.

    Args:
        port_id: Port identifier
        target_date: Reference date

    Returns:
        Congestion index (0-100)
    """
    session = SessionLocal()
    try:
        congestion = (
            session.query(PortCongestion)
            .filter(
                PortCongestion.port_id == port_id,
                PortCongestion.date == target_date,
            )
            .first()
        )

        if not congestion:
            return None

        # Calculate index from vessels and wait time
        vessel_count = congestion.vessels_in_port or 0
        wait_time = congestion.avg_wait_time_hours or 0

        # Normalize: assume 100 vessels and 48h wait = max congestion
        vessel_factor = min(vessel_count / 100, 1) * 50
        wait_factor = min(wait_time / 48, 1) * 50

        return vessel_factor + wait_factor
    finally:
        session.close()


def calc_port_activity_change(
    port_id: str,
    target_date: date,
    lookback_days: int = 7,
    comparison_days: int = 30,
) -> Optional[float]:
    """Calculate change in port activity.

    Args:
        port_id: Port identifier
        target_date: Reference date
        lookback_days: Recent period
        comparison_days: Comparison period

    Returns:
        Percentage change in activity
    """
    session = SessionLocal()
    try:
        recent_start = target_date - timedelta(days=lookback_days)
        comparison_start = target_date - timedelta(days=comparison_days)

        # Recent arrivals
        recent_count = (
            session.query(func.count(PortCall.id))
            .filter(
                PortCall.port_id == port_id,
                PortCall.call_type == "arrival",
                func.date(PortCall.timestamp) >= recent_start,
                func.date(PortCall.timestamp) <= target_date,
            )
            .scalar()
        ) or 0

        # Comparison period arrivals (before recent)
        comparison_count = (
            session.query(func.count(PortCall.id))
            .filter(
                PortCall.port_id == port_id,
                PortCall.call_type == "arrival",
                func.date(PortCall.timestamp) >= comparison_start,
                func.date(PortCall.timestamp) < recent_start,
            )
            .scalar()
        ) or 0

        if comparison_count == 0:
            return None

        # Normalize by period length
        recent_rate = recent_count / lookback_days
        comparison_rate = comparison_count / (comparison_days - lookback_days)

        if comparison_rate == 0:
            return None

        return ((recent_rate - comparison_rate) / comparison_rate) * 100
    finally:
        session.close()


def calc_container_vessel_count(
    region: str,
    target_date: date,
) -> Optional[int]:
    """Count container vessels in a region.

    Args:
        region: Region name (asia, europe, americas)
        target_date: Reference date

    Returns:
        Number of container vessels
    """
    REGION_PORTS = {
        "asia": ["CNSHA", "SGSIN", "CNSZN", "HKHKG", "KRPUS"],
        "europe": ["NLRTM", "DEHAM", "BEANR", "GBFXT"],
        "americas": ["USLAX", "USLGB", "USNYC", "USSAV"],
    }

    ports = REGION_PORTS.get(region.lower(), [])
    if not ports:
        return None

    session = SessionLocal()
    try:
        count = (
            session.query(func.sum(PortCongestion.container_vessels))
            .filter(
                PortCongestion.port_id.in_(ports),
                PortCongestion.date == target_date,
            )
            .scalar()
        )

        return int(count) if count else 0
    finally:
        session.close()


def calc_tanker_activity_index(
    target_date: date,
    lookback_days: int = 7,
) -> Optional[float]:
    """Calculate global tanker activity index.

    Args:
        target_date: Reference date
        lookback_days: Analysis window

    Returns:
        Tanker activity index
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        # Count tanker positions
        tanker_count = (
            session.query(func.count(VesselPosition.id))
            .join(Vessel, VesselPosition.mmsi == Vessel.mmsi)
            .filter(
                Vessel.vessel_type.like("%Tanker%"),
                func.date(VesselPosition.timestamp) >= start_date,
                func.date(VesselPosition.timestamp) <= target_date,
            )
            .scalar()
        )

        if tanker_count is None:
            return None

        # Normalize to index (assume 10000 positions/week = index 100)
        return min(float(tanker_count) / 10000 * 100, 150)
    finally:
        session.close()


def calc_shipping_route_traffic(
    origin_port: str,
    dest_port: str,
    target_date: date,
    lookback_days: int = 7,
) -> Optional[int]:
    """Calculate traffic on a shipping route.

    Args:
        origin_port: Origin port ID
        dest_port: Destination port ID
        target_date: Reference date
        lookback_days: Analysis window

    Returns:
        Number of vessels on route
    """
    session = SessionLocal()
    try:
        start_date = target_date - timedelta(days=lookback_days)

        # Count departures from origin with destination matching
        count = (
            session.query(func.count(PortCall.id))
            .join(VesselPosition, PortCall.mmsi == VesselPosition.mmsi)
            .filter(
                PortCall.port_id == origin_port,
                PortCall.call_type == "departure",
                func.date(PortCall.timestamp) >= start_date,
                func.date(PortCall.timestamp) <= target_date,
                VesselPosition.destination.like(f"%{dest_port}%"),
            )
            .scalar()
        )

        return int(count) if count else 0
    finally:
        session.close()


def calc_global_congestion_index(
    target_date: date,
) -> Optional[float]:
    """Calculate global port congestion index.

    Args:
        target_date: Reference date

    Returns:
        Global congestion index (0-100)
    """
    session = SessionLocal()
    try:
        congestion_data = (
            session.query(
                func.avg(PortCongestion.vessels_in_port),
                func.avg(PortCongestion.avg_wait_time_hours),
            )
            .filter(PortCongestion.date == target_date)
            .first()
        )

        if not congestion_data or congestion_data[0] is None:
            return None

        avg_vessels = float(congestion_data[0])
        avg_wait = float(congestion_data[1]) if congestion_data[1] else 0

        # Normalize
        vessel_factor = min(avg_vessels / 50, 1) * 50
        wait_factor = min(avg_wait / 24, 1) * 50

        return vessel_factor + wait_factor
    finally:
        session.close()


@FactorRegistry.register
class PortCongestionIndex(BaseFactor):
    """Port Congestion Index Factor.

    Measures congestion level at a specific port.
    Higher = more congested = potential supply chain issues.
    """

    FACTOR_NAME = "port_congestion_index"
    FACTOR_DESCRIPTION = "Port congestion level (0-100)"
    CATEGORY = "shipping"
    ENTITY_TYPE = "port"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,  # Port ID
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute port congestion index."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_port_congestion_index(entity_id, target_date)


@FactorRegistry.register
class PortActivityChange(BaseFactor):
    """Port Activity Change Factor.

    Measures change in port arrivals vs historical average.
    Positive = increased activity, Negative = decreased.
    """

    FACTOR_NAME = "port_activity_change"
    FACTOR_DESCRIPTION = "Port activity change vs historical (%)"
    CATEGORY = "shipping"
    ENTITY_TYPE = "port"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute port activity change."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_port_activity_change(entity_id, target_date, lookback_days)


@FactorRegistry.register
class ContainerVesselCount(BaseFactor):
    """Container Vessel Count Factor.

    Number of container vessels in a region.
    Proxy for trade activity.
    """

    FACTOR_NAME = "container_vessel_count"
    FACTOR_DESCRIPTION = "Container vessels in region"
    CATEGORY = "shipping"
    ENTITY_TYPE = "region"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,  # Region: asia, europe, americas
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute container vessel count."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        result = calc_container_vessel_count(entity_id, target_date)
        return float(result) if result is not None else None


@FactorRegistry.register
class TankerActivityIndex(BaseFactor):
    """Tanker Activity Index Factor.

    Global tanker activity as oil demand proxy.
    """

    FACTOR_NAME = "tanker_activity_index"
    FACTOR_DESCRIPTION = "Global tanker activity index"
    CATEGORY = "shipping"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,  # Ignored
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute tanker activity index."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_tanker_activity_index(target_date, lookback_days)


@FactorRegistry.register
class GlobalCongestionIndex(BaseFactor):
    """Global Congestion Index Factor.

    Average congestion across major ports.
    Higher = supply chain stress.
    """

    FACTOR_NAME = "global_congestion_index"
    FACTOR_DESCRIPTION = "Global port congestion index (0-100)"
    CATEGORY = "shipping"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str,  # Ignored
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute global congestion index."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_global_congestion_index(target_date)


@FactorRegistry.register
class ChinaUSTradeFlow(BaseFactor):
    """China-US Trade Flow Factor.

    Shipping activity between China and US ports.
    """

    FACTOR_NAME = "china_us_trade_flow"
    FACTOR_DESCRIPTION = "China to US shipping activity"
    CATEGORY = "shipping"
    ENTITY_TYPE = "route"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    CHINA_PORTS = ["CNSHA", "CNSZN", "CNNGB"]
    US_PORTS = ["USLAX", "USLGB", "USNYC"]

    def compute(
        self,
        entity_id: str,  # Ignored
        as_of_date: datetime,
        lookback_days: int = 7,
    ) -> Optional[float]:
        """Compute China-US trade flow."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        start_date = target_date - timedelta(days=lookback_days)

        session = SessionLocal()
        try:
            # Count port calls from China ports heading to US
            count = (
                session.query(func.count(PortCall.id))
                .filter(
                    PortCall.port_id.in_(self.CHINA_PORTS),
                    PortCall.call_type == "departure",
                    func.date(PortCall.timestamp) >= start_date,
                    func.date(PortCall.timestamp) <= target_date,
                )
                .scalar()
            )

            return float(count) if count else 0
        finally:
            session.close()
