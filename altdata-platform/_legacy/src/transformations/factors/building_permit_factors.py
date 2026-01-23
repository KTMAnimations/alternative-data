"""Building permit-derived factor computations.

Factors derived from building permit data for construction
and housing market analysis.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.building_permits import BuildingPermit
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


# Entity mapping for building permit factors
HOMEBUILDERS = ["DHI", "LEN", "PHM", "TOL", "NVR", "KBH", "MTH", "TMHC", "MHO"]
HOME_IMPROVEMENT = ["HD", "LOW"]
BUILDING_MATERIALS = ["VMC", "MLM", "EXP", "BLDR", "BLD"]


def calc_permit_momentum(
    target_date: date,
    permit_type: str = "total",
    lookback_months: int = 3,
) -> Optional[float]:
    """Calculate building permit momentum.

    Month-over-month change in permit issuance.

    Args:
        target_date: Reference date
        permit_type: Type of permits (total, single_family, etc.)
        lookback_months: Months to compare

    Returns:
        Percentage change in permits
    """
    session = SessionLocal()
    try:
        # Get most recent data
        current = (
            session.query(BuildingPermit.units_authorized)
            .filter(
                BuildingPermit.period <= target_date,
                BuildingPermit.permit_type == permit_type,
                BuildingPermit.geography_level == "national",
                BuildingPermit.is_seasonally_adjusted == "SA",
            )
            .order_by(BuildingPermit.period.desc())
            .first()
        )

        if not current:
            return None

        # Get prior period
        prior_date = target_date - timedelta(days=30 * lookback_months)
        prior = (
            session.query(BuildingPermit.units_authorized)
            .filter(
                BuildingPermit.period <= prior_date,
                BuildingPermit.permit_type == permit_type,
                BuildingPermit.geography_level == "national",
                BuildingPermit.is_seasonally_adjusted == "SA",
            )
            .order_by(BuildingPermit.period.desc())
            .first()
        )

        if not prior or prior[0] == 0:
            return None

        return ((float(current[0]) - float(prior[0])) / float(prior[0])) * 100

    finally:
        session.close()


def calc_sfr_multifamily_ratio(
    target_date: date,
) -> Optional[float]:
    """Calculate single-family to multi-family permit ratio.

    Args:
        target_date: Reference date

    Returns:
        Ratio of single-family to multi-family permits
    """
    session = SessionLocal()
    try:
        # Get latest single-family permits
        sfr = (
            session.query(BuildingPermit.units_authorized)
            .filter(
                BuildingPermit.period <= target_date,
                BuildingPermit.permit_type == "single_family",
                BuildingPermit.geography_level == "national",
                BuildingPermit.is_seasonally_adjusted == "SA",
            )
            .order_by(BuildingPermit.period.desc())
            .first()
        )

        # Get multi-family (5+ units)
        mf = (
            session.query(BuildingPermit.units_authorized)
            .filter(
                BuildingPermit.period <= target_date,
                BuildingPermit.permit_type == "multi_family_5_plus",
                BuildingPermit.geography_level == "national",
                BuildingPermit.is_seasonally_adjusted == "SA",
            )
            .order_by(BuildingPermit.period.desc())
            .first()
        )

        if not sfr or not mf or mf[0] == 0:
            return None

        return float(sfr[0]) / float(mf[0])

    finally:
        session.close()


def calc_permit_level(
    target_date: date,
    permit_type: str = "total",
) -> Optional[float]:
    """Get current permit issuance level (thousands).

    Args:
        target_date: Reference date
        permit_type: Type of permits

    Returns:
        Permit units in thousands (annualized rate)
    """
    session = SessionLocal()
    try:
        latest = (
            session.query(BuildingPermit.units_authorized)
            .filter(
                BuildingPermit.period <= target_date,
                BuildingPermit.permit_type == permit_type,
                BuildingPermit.geography_level == "national",
                BuildingPermit.is_seasonally_adjusted == "SA",
            )
            .order_by(BuildingPermit.period.desc())
            .first()
        )

        if latest:
            return float(latest[0]) / 1000  # Return in thousands
        return None

    finally:
        session.close()


def calc_permit_yoy_change(
    target_date: date,
    permit_type: str = "total",
) -> Optional[float]:
    """Calculate year-over-year permit change.

    Args:
        target_date: Reference date
        permit_type: Type of permits

    Returns:
        YoY percentage change
    """
    session = SessionLocal()
    try:
        # Current period
        current = (
            session.query(BuildingPermit.units_authorized)
            .filter(
                BuildingPermit.period <= target_date,
                BuildingPermit.permit_type == permit_type,
                BuildingPermit.geography_level == "national",
                BuildingPermit.is_seasonally_adjusted == "SA",
            )
            .order_by(BuildingPermit.period.desc())
            .first()
        )

        if not current:
            return None

        # Prior year
        prior_date = target_date - timedelta(days=365)
        prior = (
            session.query(BuildingPermit.units_authorized)
            .filter(
                BuildingPermit.period <= prior_date,
                BuildingPermit.permit_type == permit_type,
                BuildingPermit.geography_level == "national",
                BuildingPermit.is_seasonally_adjusted == "SA",
            )
            .order_by(BuildingPermit.period.desc())
            .first()
        )

        if not prior or prior[0] == 0:
            return None

        return ((float(current[0]) - float(prior[0])) / float(prior[0])) * 100

    finally:
        session.close()


@FactorRegistry.register
class PermitMomentum(BaseFactor):
    """Building Permit Momentum Factor.

    Month-over-month change in building permits.
    Positive momentum = construction growth.

    Target: DHI, LEN, PHM, HD, LOW
    """

    FACTOR_NAME = "permit_momentum"
    FACTOR_DESCRIPTION = "Building permit MoM change (%)"
    CATEGORY = "construction"
    ENTITY_TYPE = "company"
    FREQUENCY = "monthly"
    LOOKBACK_DAYS = 90

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_months: int = 3,
    ) -> Optional[float]:
        """Compute permit momentum."""
        if entity_id not in HOMEBUILDERS + HOME_IMPROVEMENT + BUILDING_MATERIALS:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_permit_momentum(target_date, "total", lookback_months)


@FactorRegistry.register
class SingleFamilyPermitMomentum(BaseFactor):
    """Single Family Permit Momentum Factor.

    Change in single-family permits specifically.
    Key indicator for homebuilders.

    Target: DHI, LEN, PHM, TOL, NVR
    """

    FACTOR_NAME = "sfr_permit_momentum"
    FACTOR_DESCRIPTION = "Single-family permit MoM change (%)"
    CATEGORY = "construction"
    ENTITY_TYPE = "company"
    FREQUENCY = "monthly"
    LOOKBACK_DAYS = 90

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute single-family permit momentum."""
        if entity_id not in HOMEBUILDERS:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_permit_momentum(target_date, "single_family")


@FactorRegistry.register
class SFRMultifamilyRatio(BaseFactor):
    """SFR to Multifamily Ratio Factor.

    Ratio of single-family to multi-family permits.
    Higher ratio favors homebuilders over apartment REITs.

    Target: Homebuilders vs apartment REITs
    """

    FACTOR_NAME = "sfr_multifamily_ratio"
    FACTOR_DESCRIPTION = "Single-family to multi-family permit ratio"
    CATEGORY = "construction"
    ENTITY_TYPE = "sector"
    FREQUENCY = "monthly"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute SFR/MF ratio."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_sfr_multifamily_ratio(target_date)


@FactorRegistry.register
class BuildingPermitLevel(BaseFactor):
    """Building Permit Level Factor.

    Current permit issuance rate (annualized, thousands).
    Absolute level for trend analysis.

    Target: Construction sector
    """

    FACTOR_NAME = "building_permit_level"
    FACTOR_DESCRIPTION = "Building permits (thousands, annualized)"
    CATEGORY = "construction"
    ENTITY_TYPE = "market"
    FREQUENCY = "monthly"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute permit level."""
        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_permit_level(target_date)


@FactorRegistry.register
class PermitYoYChange(BaseFactor):
    """Building Permit YoY Change Factor.

    Year-over-year change in permits.
    Longer-term construction cycle indicator.

    Target: Homebuilders, building materials
    """

    FACTOR_NAME = "permit_yoy_change"
    FACTOR_DESCRIPTION = "Building permit YoY change (%)"
    CATEGORY = "construction"
    ENTITY_TYPE = "company"
    FREQUENCY = "monthly"
    LOOKBACK_DAYS = 365

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
    ) -> Optional[float]:
        """Compute permit YoY change."""
        if entity_id not in HOMEBUILDERS + HOME_IMPROVEMENT + BUILDING_MATERIALS:
            return None

        target_date = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
        return calc_permit_yoy_change(target_date)
