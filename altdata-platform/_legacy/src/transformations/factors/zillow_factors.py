"""Zillow rental-derived factor computations.

Factors derived from Zillow rental data for real estate
and housing market analysis.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.zillow_rental import ZillowRentalIndex
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


# Entity mapping for Zillow factors
APARTMENT_REITS = ["EQR", "AVB", "MAA", "UDR", "CPT", "ESS"]
SFR_REITS = ["INVH", "AMH"]
HOMEBUILDERS = ["DHI", "LEN", "PHM", "TOL", "NVR"]


def calc_rent_inflation_index(
    target_date: date,
    region_type: str = "national",
) -> Optional[float]:
    """Calculate rent inflation index (YoY change).

    Args:
        target_date: Reference date
        region_type: Geographic level

    Returns:
        YoY percentage change in rents
    """
    session = SessionLocal()
    try:
        # Get most recent data
        latest = (
            session.query(ZillowRentalIndex.yoy_change)
            .filter(
                ZillowRentalIndex.period <= target_date,
                ZillowRentalIndex.region_type == region_type,
                ZillowRentalIndex.property_type == "all_homes",
            )
            .order_by(ZillowRentalIndex.period.desc())
            .first()
        )

        if latest and latest[0]:
            return float(latest[0])
        return None

    finally:
        session.close()


def calc_sfr_multifamily_spread(
    target_date: date,
) -> Optional[float]:
    """Calculate SFR vs multifamily rent spread.

    Args:
        target_date: Reference date

    Returns:
        SFR premium over multifamily (%)
    """
    session = SessionLocal()
    try:
        # Get latest SFR rent
        sfr = (
            session.query(ZillowRentalIndex.zori_value)
            .filter(
                ZillowRentalIndex.period <= target_date,
                ZillowRentalIndex.region_type == "national",
                ZillowRentalIndex.property_type == "sfr",
            )
            .order_by(ZillowRentalIndex.period.desc())
            .first()
        )

        # Get latest overall rent (includes multifamily)
        all_homes = (
            session.query(ZillowRentalIndex.zori_value)
            .filter(
                ZillowRentalIndex.period <= target_date,
                ZillowRentalIndex.region_type == "national",
                ZillowRentalIndex.property_type == "all_homes",
            )
            .order_by(ZillowRentalIndex.period.desc())
            .first()
        )

        if not sfr or not all_homes or all_homes[0] == 0:
            return None

        # Calculate spread (SFR premium)
        return ((float(sfr[0]) - float(all_homes[0])) / float(all_homes[0])) * 100

    finally:
        session.close()


def calc_rent_momentum(
    target_date: date,
    lookback_months: int = 3,
) -> Optional[float]:
    """Calculate rent momentum (3-month change).

    Args:
        target_date: Reference date
        lookback_months: Comparison period

    Returns:
        Percentage change in rents
    """
    session = SessionLocal()
    try:
        # Current rent level
        current = (
            session.query(ZillowRentalIndex.zori_value)
            .filter(
                ZillowRentalIndex.period <= target_date,
                ZillowRentalIndex.region_type == "national",
                ZillowRentalIndex.property_type == "all_homes",
            )
            .order_by(ZillowRentalIndex.period.desc())
            .first()
        )

        if not current:
            return None

        # Prior period
        prior_date = target_date - timedelta(days=30 * lookback_months)
        prior = (
            session.query(ZillowRentalIndex.zori_value)
            .filter(
                ZillowRentalIndex.period <= prior_date,
                ZillowRentalIndex.region_type == "national",
                ZillowRentalIndex.property_type == "all_homes",
            )
            .order_by(ZillowRentalIndex.period.desc())
            .first()
        )

        if not prior or prior[0] == 0:
            return None

        return ((float(current[0]) - float(prior[0])) / float(prior[0])) * 100

    finally:
        session.close()


def calc_rent_level(
    target_date: date,
    property_type: str = "all_homes",
) -> Optional[float]:
    """Get current national rent level.

    Args:
        target_date: Reference date
        property_type: Property type filter

    Returns:
        Current ZORI value
    """
    session = SessionLocal()
    try:
        latest = (
            session.query(ZillowRentalIndex.zori_value)
            .filter(
                ZillowRentalIndex.period <= target_date,
                ZillowRentalIndex.region_type == "national",
                ZillowRentalIndex.property_type == property_type,
            )
            .order_by(ZillowRentalIndex.period.desc())
            .first()
        )

        if latest and latest[0]:
            return float(latest[0])
        return None

    finally:
        session.close()


def calc_regional_rent_dispersion(
    target_date: date,
) -> Optional[float]:
    """Calculate dispersion in regional rent growth.

    Args:
        target_date: Reference date

    Returns:
        Standard deviation of regional YoY changes
    """
    session = SessionLocal()
    try:
        # Get latest period
        latest_period = (
            session.query(func.max(ZillowRentalIndex.period))
            .filter(ZillowRentalIndex.period <= target_date)
            .scalar()
        )

        if not latest_period:
            return None

        # Get std dev of YoY changes across metros
        std_dev = (
            session.query(func.stddev(ZillowRentalIndex.yoy_change))
            .filter(
                ZillowRentalIndex.period == latest_period,
                ZillowRentalIndex.region_type == "metro",
                ZillowRentalIndex.property_type == "all_homes",
                ZillowRentalIndex.yoy_change.isnot(None),
            )
            .scalar()
        )

        if std_dev:
            return float(std_dev)
        return None

    finally:
        session.close()


@FactorRegistry.register
class RentInflationIndex(BaseFactor):
    """Rent Inflation Index Factor.

    Year-over-year change in national rents.
    Key input for CPI shelter component.

    Target: Apartment REITs, homebuilders
    """

    FACTOR_NAME = "rent_inflation_index"
    FACTOR_DESCRIPTION = "National rent YoY change (%)"
    CATEGORY = "real_estate"
    ENTITY_TYPE = "company"
    FREQUENCY = "monthly"
    LOOKBACK_DAYS = 365

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute rent inflation index."""
        if entity_id not in APARTMENT_REITS + SFR_REITS + HOMEBUILDERS:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_rent_inflation_index(target_date)


@FactorRegistry.register
class SFRMultifamilySpread(BaseFactor):
    """SFR/Multifamily Spread Factor.

    Single-family rent premium over multifamily.
    Higher spread favors SFR REITs.

    Target: INVH, AMH vs EQR, AVB
    """

    FACTOR_NAME = "sfr_multifamily_spread"
    FACTOR_DESCRIPTION = "SFR rent premium over multifamily (%)"
    CATEGORY = "real_estate"
    ENTITY_TYPE = "sector"
    FREQUENCY = "monthly"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute SFR/MF spread."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_sfr_multifamily_spread(target_date)


@FactorRegistry.register
class RentMomentum(BaseFactor):
    """Rent Momentum Factor.

    3-month change in national rents.
    Indicates near-term rent trends.

    Target: Apartment and SFR REITs
    """

    FACTOR_NAME = "rent_momentum"
    FACTOR_DESCRIPTION = "National rent 3-month change (%)"
    CATEGORY = "real_estate"
    ENTITY_TYPE = "company"
    FREQUENCY = "monthly"
    LOOKBACK_DAYS = 90

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute rent momentum."""
        if entity_id not in APARTMENT_REITS + SFR_REITS:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_rent_momentum(target_date)


@FactorRegistry.register
class NationalRentLevel(BaseFactor):
    """National Rent Level Factor.

    Current ZORI value for national rents.
    Absolute level for trend analysis.

    Target: Real estate sector
    """

    FACTOR_NAME = "national_rent_level"
    FACTOR_DESCRIPTION = "National ZORI rent level ($)"
    CATEGORY = "real_estate"
    ENTITY_TYPE = "market"
    FREQUENCY = "monthly"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute national rent level."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_rent_level(target_date)


@FactorRegistry.register
class RegionalRentDispersion(BaseFactor):
    """Regional Rent Dispersion Factor.

    Dispersion of rent growth across metros.
    High dispersion indicates uneven market.

    Target: National REITs vs regional
    """

    FACTOR_NAME = "regional_rent_dispersion"
    FACTOR_DESCRIPTION = "Std dev of metro rent YoY changes"
    CATEGORY = "real_estate"
    ENTITY_TYPE = "market"
    FREQUENCY = "monthly"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute regional rent dispersion."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_regional_rent_dispersion(target_date)
