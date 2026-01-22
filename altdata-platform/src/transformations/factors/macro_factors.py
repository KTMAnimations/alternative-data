"""Macroeconomic factor computations derived from FRED data."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from src.models.database import SessionLocal
from src.models.schemas import FREDSeries
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


def calc_yield_curve_slope(gs10: float, gs2: float) -> float:
    """Calculate yield curve slope.

    The slope of the yield curve (10Y - 2Y) is a classic recession indicator.
    Positive = normal curve, Negative = inverted (recession signal).

    Args:
        gs10: 10-Year Treasury yield
        gs2: 2-Year Treasury yield

    Returns:
        Yield spread (10Y - 2Y)
    """
    return gs10 - gs2


def calc_credit_spread(baa_spread: float) -> float:
    """Normalize credit spread.

    BAA10Y is already the spread between BAA corporate bonds and 10Y Treasury.
    Higher values indicate credit stress.

    Args:
        baa_spread: BAA-10Y spread

    Returns:
        Credit spread value
    """
    return baa_spread


@FactorRegistry.register
class YieldCurveSlope(BaseFactor):
    """Yield Curve Slope Factor.

    Difference between 10-Year and 2-Year Treasury yields.
    A classic leading indicator - inversion signals recession risk.
    """

    FACTOR_NAME = "yield_curve_slope"
    FACTOR_DESCRIPTION = "10Y Treasury minus 2Y Treasury yield"
    CATEGORY = "macro"
    ENTITY_TYPE = "market"  # Market-wide factor
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str = "MARKET",
        as_of_date: Optional[datetime] = None,
        **kwargs
    ) -> Optional[float]:
        """Compute yield curve slope.

        Args:
            entity_id: Not used (market-wide factor)
            as_of_date: Date for computation

        Returns:
            Yield spread (10Y - 2Y)
        """
        if as_of_date is None:
            as_of_date = datetime.utcnow()

        session = self._get_session()
        try:
            # Get most recent GS10 value on or before as_of_date
            gs10 = (
                session.query(FREDSeries)
                .filter(
                    FREDSeries.series_id == "GS10",
                    FREDSeries.observation_date <= as_of_date,
                )
                .order_by(FREDSeries.observation_date.desc())
                .first()
            )

            # Get most recent GS2 value
            gs2 = (
                session.query(FREDSeries)
                .filter(
                    FREDSeries.series_id == "GS2",
                    FREDSeries.observation_date <= as_of_date,
                )
                .order_by(FREDSeries.observation_date.desc())
                .first()
            )

            if not gs10 or not gs2:
                logger.warning("Missing yield data for slope calculation")
                return None

            return calc_yield_curve_slope(gs10.value, gs2.value)

        finally:
            self._close_session()


@FactorRegistry.register
class CreditSpreadIndex(BaseFactor):
    """Credit Spread Index Factor.

    BAA corporate bond spread over 10-Year Treasury.
    Higher values indicate credit market stress.
    """

    FACTOR_NAME = "credit_spread_index"
    FACTOR_DESCRIPTION = "BAA corporate bond spread over 10Y Treasury"
    CATEGORY = "macro"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str = "MARKET",
        as_of_date: Optional[datetime] = None,
        **kwargs
    ) -> Optional[float]:
        """Compute credit spread.

        Args:
            entity_id: Not used (market-wide factor)
            as_of_date: Date for computation

        Returns:
            Credit spread value
        """
        if as_of_date is None:
            as_of_date = datetime.utcnow()

        session = self._get_session()
        try:
            # BAA10Y is already the spread
            baa_spread = (
                session.query(FREDSeries)
                .filter(
                    FREDSeries.series_id == "BAA10Y",
                    FREDSeries.observation_date <= as_of_date,
                )
                .order_by(FREDSeries.observation_date.desc())
                .first()
            )

            if not baa_spread:
                logger.warning("Missing BAA10Y data for credit spread")
                return None

            return calc_credit_spread(baa_spread.value)

        finally:
            self._close_session()


@FactorRegistry.register
class InflationExpectations(BaseFactor):
    """Inflation Expectations Factor.

    10-Year Breakeven Inflation Rate derived from TIPS.
    Higher values indicate rising inflation expectations.
    """

    FACTOR_NAME = "inflation_expectations"
    FACTOR_DESCRIPTION = "10-Year Breakeven Inflation Rate from TIPS"
    CATEGORY = "macro"
    ENTITY_TYPE = "market"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 1

    def compute(
        self,
        entity_id: str = "MARKET",
        as_of_date: Optional[datetime] = None,
        **kwargs
    ) -> Optional[float]:
        """Compute inflation expectations.

        Args:
            entity_id: Not used (market-wide factor)
            as_of_date: Date for computation

        Returns:
            Breakeven inflation rate
        """
        if as_of_date is None:
            as_of_date = datetime.utcnow()

        session = self._get_session()
        try:
            t10yie = (
                session.query(FREDSeries)
                .filter(
                    FREDSeries.series_id == "T10YIE",
                    FREDSeries.observation_date <= as_of_date,
                )
                .order_by(FREDSeries.observation_date.desc())
                .first()
            )

            if not t10yie:
                logger.warning("Missing T10YIE data")
                return None

            return t10yie.value

        finally:
            self._close_session()


@FactorRegistry.register
class FinancialConditionsIndex(BaseFactor):
    """Financial Conditions Index Factor.

    Chicago Fed National Financial Conditions Index.
    Positive values indicate tighter than average financial conditions.
    """

    FACTOR_NAME = "financial_conditions_index"
    FACTOR_DESCRIPTION = "Chicago Fed National Financial Conditions Index"
    CATEGORY = "macro"
    ENTITY_TYPE = "market"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str = "MARKET",
        as_of_date: Optional[datetime] = None,
        **kwargs
    ) -> Optional[float]:
        """Compute financial conditions index.

        Args:
            entity_id: Not used (market-wide factor)
            as_of_date: Date for computation

        Returns:
            NFCI value
        """
        if as_of_date is None:
            as_of_date = datetime.utcnow()

        session = self._get_session()
        try:
            nfci = (
                session.query(FREDSeries)
                .filter(
                    FREDSeries.series_id == "NFCI",
                    FREDSeries.observation_date <= as_of_date,
                )
                .order_by(FREDSeries.observation_date.desc())
                .first()
            )

            if not nfci:
                logger.warning("Missing NFCI data")
                return None

            return nfci.value

        finally:
            self._close_session()
