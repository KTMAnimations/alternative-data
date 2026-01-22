"""SEC-derived factor computations."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func

from src.models.database import SessionLocal
from src.models.schemas import SECForm4Transaction, SECFiling
from src.transformations.base import BaseFactor, FactorRegistry

logger = logging.getLogger(__name__)


def calc_insider_momentum(transactions: List[Dict]) -> float:
    """Calculate insider transaction momentum.

    Net buy/sell value over the period.

    Args:
        transactions: List of transaction dicts with type, shares, price

    Returns:
        Net dollar value (positive = net buying, negative = net selling)
    """
    net_value = 0.0

    for txn in transactions:
        shares = txn.get("shares", 0) or 0
        price = txn.get("price", 0) or 0
        txn_type = txn.get("type", "")

        value = shares * price

        if txn_type in ("P", "A"):  # Purchase or Award (treated as buy signal)
            net_value += value
        elif txn_type == "S":  # Sale
            net_value -= value

    return net_value


@FactorRegistry.register
class InsiderTransactionMomentum(BaseFactor):
    """Insider Transaction Momentum Factor.

    Measures net insider buying/selling activity over a rolling window.
    Positive values indicate net insider buying (bullish signal).
    """

    FACTOR_NAME = "insider_transaction_momentum"
    FACTOR_DESCRIPTION = "Net insider buying/selling from Form 4 filings over 30 days"
    CATEGORY = "sec"
    ENTITY_TYPE = "company"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: Optional[int] = None,
    ) -> Optional[float]:
        """Compute insider momentum for an entity.

        Args:
            entity_id: Ticker symbol
            as_of_date: Date for computation
            lookback_days: Override default lookback period

        Returns:
            Net dollar value of insider transactions
        """
        lookback = lookback_days or self.LOOKBACK_DAYS
        start_date = as_of_date - timedelta(days=lookback)

        session = self._get_session()
        try:
            # Query Form 4 transactions for this ticker
            transactions = (
                session.query(SECForm4Transaction)
                .filter(
                    SECForm4Transaction.ticker == entity_id,
                    SECForm4Transaction.transaction_date >= start_date,
                    SECForm4Transaction.transaction_date <= as_of_date,
                )
                .all()
            )

            if not transactions:
                return 0.0

            # Convert to dicts for calculation
            txn_dicts = [
                {
                    "type": t.transaction_type,
                    "shares": t.shares,
                    "price": t.price_per_share,
                }
                for t in transactions
            ]

            return calc_insider_momentum(txn_dicts)

        finally:
            self._close_session()


def calc_clustering_score(transactions: List[Dict], window_days: int = 7) -> int:
    """Calculate insider clustering score.

    Count unique insiders trading in the same direction within window.

    Args:
        transactions: List of transaction dicts
        window_days: Window to consider for clustering

    Returns:
        Number of unique insiders in dominant direction
    """
    buyers = set()
    sellers = set()

    for txn in transactions:
        insider = txn.get("insider_name") or txn.get("insider_cik")
        if not insider:
            continue

        txn_type = txn.get("type", "")

        if txn_type in ("P", "A"):
            buyers.add(insider)
        elif txn_type == "S":
            sellers.add(insider)

    # Return count of dominant direction
    if len(buyers) >= len(sellers):
        return len(buyers)
    else:
        return -len(sellers)  # Negative indicates selling dominance


@FactorRegistry.register
class InsiderClusteringScore(BaseFactor):
    """Insider Clustering Score Factor.

    Measures coordinated insider activity - when multiple insiders
    trade in the same direction, it may signal stronger conviction.
    """

    FACTOR_NAME = "insider_clustering_score"
    FACTOR_DESCRIPTION = "Number of unique insiders trading in same direction within 7 days"
    CATEGORY = "sec"
    ENTITY_TYPE = "company"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        window_days: Optional[int] = None,
    ) -> Optional[float]:
        """Compute insider clustering for an entity.

        Args:
            entity_id: Ticker symbol
            as_of_date: Date for computation
            window_days: Override default window

        Returns:
            Clustering score (positive=buying, negative=selling)
        """
        window = window_days or self.LOOKBACK_DAYS
        start_date = as_of_date - timedelta(days=window)

        session = self._get_session()
        try:
            transactions = (
                session.query(SECForm4Transaction)
                .filter(
                    SECForm4Transaction.ticker == entity_id,
                    SECForm4Transaction.transaction_date >= start_date,
                    SECForm4Transaction.transaction_date <= as_of_date,
                )
                .all()
            )

            if not transactions:
                return 0.0

            txn_dicts = [
                {
                    "type": t.transaction_type,
                    "insider_name": t.insider_name,
                    "insider_cik": t.insider_cik,
                }
                for t in transactions
            ]

            return float(calc_clustering_score(txn_dicts, window))

        finally:
            self._close_session()


@FactorRegistry.register
class EventVelocity8K(BaseFactor):
    """8-K Event Velocity Factor.

    Measures the frequency of 8-K filings, which report material events.
    Higher velocity may indicate corporate uncertainty or transition.
    """

    FACTOR_NAME = "8k_event_velocity"
    FACTOR_DESCRIPTION = "Number of 8-K filings in rolling 30-day window"
    CATEGORY = "sec"
    ENTITY_TYPE = "company"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 30

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: Optional[int] = None,
    ) -> Optional[float]:
        """Compute 8-K filing velocity for an entity.

        Args:
            entity_id: Ticker symbol or CIK
            as_of_date: Date for computation
            lookback_days: Override default lookback

        Returns:
            Count of 8-K filings in window
        """
        lookback = lookback_days or self.LOOKBACK_DAYS
        start_date = as_of_date - timedelta(days=lookback)

        session = self._get_session()
        try:
            count = (
                session.query(func.count(SECFiling.id))
                .filter(
                    SECFiling.ticker == entity_id,
                    SECFiling.form_type.like("8-K%"),
                    SECFiling.filed_date >= start_date,
                    SECFiling.filed_date <= as_of_date,
                )
                .scalar()
            )

            return float(count or 0)

        finally:
            self._close_session()
