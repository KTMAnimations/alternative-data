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


def calc_insider_buy_ratio(transactions: List[Dict]) -> Optional[float]:
    """Calculate insider buy ratio.

    Ratio of buy transactions to total (buy + sell) transactions.
    Higher ratios indicate bullish insider sentiment.

    Args:
        transactions: List of transaction dicts with type field

    Returns:
        Buy ratio (0.0 to 1.0) or None if no transactions
    """
    buys = 0
    sells = 0

    for txn in transactions:
        txn_type = txn.get("type", "")

        if txn_type in ("P", "A"):  # Purchase or Award
            buys += 1
        elif txn_type == "S":  # Sale
            sells += 1

    total = buys + sells
    if total == 0:
        return None

    return buys / total


@FactorRegistry.register
class InsiderBuyRatio(BaseFactor):
    """Insider Buy Ratio Factor.

    Ratio of buy transactions to total transactions (buy + sell).
    Values closer to 1.0 indicate more bullish insider sentiment.
    """

    FACTOR_NAME = "insider_buy_ratio"
    FACTOR_DESCRIPTION = "Ratio of insider buys to total (buys + sells)"
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
        """Compute insider buy ratio for an entity.

        Args:
            entity_id: Ticker symbol
            as_of_date: Date for computation
            lookback_days: Override default lookback period

        Returns:
            Buy ratio (0.0 to 1.0)
        """
        lookback = lookback_days or self.LOOKBACK_DAYS
        start_date = as_of_date - timedelta(days=lookback)

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
                return None

            txn_dicts = [{"type": t.transaction_type} for t in transactions]
            return calc_insider_buy_ratio(txn_dicts)

        finally:
            self._close_session()


@FactorRegistry.register
class FilingSentimentScore(BaseFactor):
    """Filing Sentiment Score Factor.

    NLP-derived sentiment score from SEC filing text.
    Positive values indicate positive sentiment.
    """

    FACTOR_NAME = "filing_sentiment_score"
    FACTOR_DESCRIPTION = "NLP sentiment score from SEC filing text"
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
        """Compute average filing sentiment for an entity.

        Args:
            entity_id: Ticker symbol
            as_of_date: Date for computation
            lookback_days: Override default lookback period

        Returns:
            Average sentiment score
        """
        lookback = lookback_days or self.LOOKBACK_DAYS
        start_date = as_of_date - timedelta(days=lookback)

        session = self._get_session()
        try:
            # Get average sentiment from filings with sentiment scores
            avg_sentiment = (
                session.query(func.avg(SECFiling.sentiment_score))
                .filter(
                    SECFiling.ticker == entity_id,
                    SECFiling.filed_date >= start_date,
                    SECFiling.filed_date <= as_of_date,
                    SECFiling.sentiment_score.isnot(None),
                )
                .scalar()
            )

            return float(avg_sentiment) if avg_sentiment else None

        finally:
            self._close_session()


def calc_insider_size_percentile(
    current_value: float,
    historical_values: List[float],
) -> Optional[float]:
    """Calculate transaction size percentile vs historical.

    Args:
        current_value: Current transaction value
        historical_values: List of historical transaction values

    Returns:
        Percentile (0-100) or None
    """
    if not historical_values or current_value is None:
        return None

    sorted_values = sorted(historical_values)
    count_below = sum(1 for v in sorted_values if v < current_value)

    return (count_below / len(sorted_values)) * 100


@FactorRegistry.register
class InsiderSizePercentile(BaseFactor):
    """Insider Size Percentile Factor.

    Transaction size compared to historical transactions.
    Higher percentiles indicate unusually large transactions.
    """

    FACTOR_NAME = "insider_size_percentile"
    FACTOR_DESCRIPTION = "Transaction size percentile vs historical"
    CATEGORY = "sec"
    ENTITY_TYPE = "company"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 365

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: Optional[int] = None,
    ) -> Optional[float]:
        """Compute insider transaction size percentile.

        Args:
            entity_id: Ticker symbol
            as_of_date: Date for computation
            lookback_days: Historical period for comparison

        Returns:
            Percentile (0-100)
        """
        lookback = lookback_days or self.LOOKBACK_DAYS
        historical_start = as_of_date - timedelta(days=lookback)
        recent_start = as_of_date - timedelta(days=7)

        session = self._get_session()
        try:
            # Get recent transactions
            recent_txns = (
                session.query(SECForm4Transaction)
                .filter(
                    SECForm4Transaction.ticker == entity_id,
                    SECForm4Transaction.transaction_date >= recent_start,
                    SECForm4Transaction.transaction_date <= as_of_date,
                    SECForm4Transaction.total_value.isnot(None),
                )
                .all()
            )

            if not recent_txns:
                return None

            # Get average recent transaction value
            recent_values = [t.total_value for t in recent_txns if t.total_value]
            if not recent_values:
                return None
            current_avg = sum(recent_values) / len(recent_values)

            # Get historical transactions for comparison
            historical_txns = (
                session.query(SECForm4Transaction.total_value)
                .filter(
                    SECForm4Transaction.ticker == entity_id,
                    SECForm4Transaction.transaction_date >= historical_start,
                    SECForm4Transaction.transaction_date < recent_start,
                    SECForm4Transaction.total_value.isnot(None),
                )
                .all()
            )

            historical_values = [t.total_value for t in historical_txns if t.total_value]
            if not historical_values:
                return None

            return calc_insider_size_percentile(current_avg, historical_values)

        finally:
            self._close_session()


@FactorRegistry.register
class CXOTransactionFlag(BaseFactor):
    """C-Suite Transaction Flag Factor.

    Identifies transactions by C-level executives (CEO, CFO, COO, etc.).
    Returns 1 if C-suite activity detected, 0 otherwise.
    """

    FACTOR_NAME = "cxo_transaction_flag"
    FACTOR_DESCRIPTION = "Flag for C-suite executive transactions"
    CATEGORY = "sec"
    ENTITY_TYPE = "company"
    FREQUENCY = "daily"
    LOOKBACK_DAYS = 7

    CXO_TITLES = [
        "CEO", "CFO", "COO", "CTO", "CIO", "CMO", "CLO",
        "Chief Executive", "Chief Financial", "Chief Operating",
        "Chief Technology", "Chief Information", "Chief Marketing",
        "Chief Legal", "President", "Chairman",
    ]

    def compute(
        self,
        entity_id: str,
        as_of_date: datetime,
        lookback_days: Optional[int] = None,
    ) -> Optional[float]:
        """Compute C-suite transaction flag.

        Args:
            entity_id: Ticker symbol
            as_of_date: Date for computation
            lookback_days: Override default lookback period

        Returns:
            1.0 if C-suite transactions found, 0.0 otherwise
        """
        lookback = lookback_days or self.LOOKBACK_DAYS
        start_date = as_of_date - timedelta(days=lookback)

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

            for txn in transactions:
                title = (txn.insider_title or "").upper()
                for cxo_title in self.CXO_TITLES:
                    if cxo_title.upper() in title:
                        return 1.0

            return 0.0

        finally:
            self._close_session()


def calc_form4_timing_score(
    transaction_date: datetime,
    filed_date: datetime,
) -> Optional[float]:
    """Calculate Form 4 timing score.

    Days between trade and filing. Faster filings may indicate
    more transparency or urgency.

    Args:
        transaction_date: Date of the transaction
        filed_date: Date the Form 4 was filed

    Returns:
        Days between transaction and filing
    """
    if not transaction_date or not filed_date:
        return None

    delta = (filed_date - transaction_date).days
    return float(max(0, delta))


@FactorRegistry.register
class Form4TimingScore(BaseFactor):
    """Form 4 Timing Score Factor.

    Average days between insider trades and Form 4 filing.
    Faster filings may indicate more transparency.
    """

    FACTOR_NAME = "form4_timing_score"
    FACTOR_DESCRIPTION = "Average days between trade and Form 4 filing"
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
        """Compute Form 4 timing score.

        Args:
            entity_id: Ticker symbol
            as_of_date: Date for computation
            lookback_days: Override default lookback period

        Returns:
            Average days between transaction and filing
        """
        lookback = lookback_days or self.LOOKBACK_DAYS
        start_date = as_of_date - timedelta(days=lookback)

        session = self._get_session()
        try:
            transactions = (
                session.query(SECForm4Transaction)
                .filter(
                    SECForm4Transaction.ticker == entity_id,
                    SECForm4Transaction.transaction_date >= start_date,
                    SECForm4Transaction.transaction_date <= as_of_date,
                    SECForm4Transaction.transaction_date.isnot(None),
                    SECForm4Transaction.filed_date.isnot(None),
                )
                .all()
            )

            if not transactions:
                return None

            timing_scores = []
            for txn in transactions:
                score = calc_form4_timing_score(txn.transaction_date, txn.filed_date)
                if score is not None:
                    timing_scores.append(score)

            if not timing_scores:
                return None

            return sum(timing_scores) / len(timing_scores)

        finally:
            self._close_session()
