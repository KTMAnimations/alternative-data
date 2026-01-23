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


@FactorRegistry.register
class YieldCurveInversion(BaseFactor):
    """Yield Curve Inversion Factor.

    Binary indicator of whether the yield curve is inverted.
    Inversion (10Y < 2Y) is a classic recession signal.
    """

    FACTOR_NAME = "yield_curve_inversion"
    FACTOR_DESCRIPTION = "Binary: 1 if yield curve inverted, 0 otherwise"
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
        """Compute yield curve inversion indicator.

        Args:
            entity_id: Not used (market-wide factor)
            as_of_date: Date for computation

        Returns:
            1.0 if inverted, 0.0 if normal, None if data missing
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
                logger.warning("Missing yield data for inversion calculation")
                return None

            # Return 1 if inverted (10Y < 2Y), 0 otherwise
            return 1.0 if gs10.value < gs2.value else 0.0

        finally:
            self._close_session()


@FactorRegistry.register
class MoneySupplyGrowth(BaseFactor):
    """Money Supply Growth Factor.

    M2 money supply year-over-year percentage change.
    Higher growth may indicate inflationary pressures.
    """

    FACTOR_NAME = "money_supply_growth"
    FACTOR_DESCRIPTION = "M2 money supply year-over-year percentage change"
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
        """Compute M2 money supply YoY growth.

        Args:
            entity_id: Not used (market-wide factor)
            as_of_date: Date for computation

        Returns:
            YoY percentage change in M2
        """
        if as_of_date is None:
            as_of_date = datetime.utcnow()

        session = self._get_session()
        try:
            # Get most recent M2SL value
            current_m2 = (
                session.query(FREDSeries)
                .filter(
                    FREDSeries.series_id == "M2SL",
                    FREDSeries.observation_date <= as_of_date,
                )
                .order_by(FREDSeries.observation_date.desc())
                .first()
            )

            if not current_m2:
                logger.warning("Missing current M2SL data")
                return None

            # Get M2SL from one year ago
            yoy_date = as_of_date - timedelta(days=365)
            prior_m2 = (
                session.query(FREDSeries)
                .filter(
                    FREDSeries.series_id == "M2SL",
                    FREDSeries.observation_date <= yoy_date,
                )
                .order_by(FREDSeries.observation_date.desc())
                .first()
            )

            if not prior_m2 or prior_m2.value == 0:
                logger.warning("Missing prior M2SL data for YoY calculation")
                return None

            # Calculate YoY change
            return ((current_m2.value - prior_m2.value) / prior_m2.value) * 100

        finally:
            self._close_session()


@FactorRegistry.register
class JoblessClaimsMomentum(BaseFactor):
    """Jobless Claims Momentum Factor.

    Compares 4-week average to 12-week average of initial jobless claims.
    Positive momentum indicates worsening labor market.
    """

    FACTOR_NAME = "jobless_claims_momentum"
    FACTOR_DESCRIPTION = "4-week vs 12-week average initial jobless claims ratio"
    CATEGORY = "macro"
    ENTITY_TYPE = "market"
    FREQUENCY = "weekly"
    LOOKBACK_DAYS = 84  # 12 weeks

    def compute(
        self,
        entity_id: str = "MARKET",
        as_of_date: Optional[datetime] = None,
        **kwargs
    ) -> Optional[float]:
        """Compute jobless claims momentum.

        Args:
            entity_id: Not used (market-wide factor)
            as_of_date: Date for computation

        Returns:
            Momentum ratio (4-week avg / 12-week avg - 1) * 100
        """
        if as_of_date is None:
            as_of_date = datetime.utcnow()

        session = self._get_session()
        try:
            # Get claims data for last 12 weeks
            start_12wk = as_of_date - timedelta(weeks=12)
            start_4wk = as_of_date - timedelta(weeks=4)

            # Get all ICSA (Initial Claims) data points
            claims = (
                session.query(FREDSeries)
                .filter(
                    FREDSeries.series_id == "ICSA",
                    FREDSeries.observation_date >= start_12wk,
                    FREDSeries.observation_date <= as_of_date,
                )
                .order_by(FREDSeries.observation_date.desc())
                .all()
            )

            if len(claims) < 4:
                logger.warning("Insufficient ICSA data for momentum calculation")
                return None

            # Separate into 4-week and 12-week periods
            recent_4wk = [c.value for c in claims if c.observation_date >= start_4wk]
            all_12wk = [c.value for c in claims]

            if not recent_4wk or not all_12wk:
                return None

            avg_4wk = sum(recent_4wk) / len(recent_4wk)
            avg_12wk = sum(all_12wk) / len(all_12wk)

            if avg_12wk == 0:
                return None

            # Return momentum as percentage deviation from longer-term average
            return ((avg_4wk / avg_12wk) - 1) * 100

        finally:
            self._close_session()
