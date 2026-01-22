"""Stage 5 Tests: Factor computation verification."""

import pytest
from datetime import datetime, timedelta


def test_insider_momentum_calculation():
    """Test insider momentum factor calculation."""
    from src.transformations.factors.sec_factors import calc_insider_momentum

    # Setup test data
    transactions = [
        {"type": "P", "shares": 1000, "price": 100},  # Buy $100k
        {"type": "P", "shares": 500, "price": 105},   # Buy $52.5k
        {"type": "S", "shares": 200, "price": 110},   # Sell $22k
    ]

    result = calc_insider_momentum(transactions)

    # Net buy value should be positive
    expected = (1000 * 100 + 500 * 105) - (200 * 110)
    assert result == expected
    assert result == 130500.0  # 100000 + 52500 - 22000


def test_insider_momentum_net_selling():
    """Test momentum with net selling."""
    from src.transformations.factors.sec_factors import calc_insider_momentum

    transactions = [
        {"type": "S", "shares": 10000, "price": 50},  # Sell $500k
        {"type": "P", "shares": 1000, "price": 50},   # Buy $50k
    ]

    result = calc_insider_momentum(transactions)

    assert result == -450000.0  # Net selling


def test_insider_momentum_empty():
    """Test momentum with no transactions."""
    from src.transformations.factors.sec_factors import calc_insider_momentum

    result = calc_insider_momentum([])
    assert result == 0.0


def test_clustering_score_buyers():
    """Test clustering score with multiple buyers."""
    from src.transformations.factors.sec_factors import calc_clustering_score

    transactions = [
        {"type": "P", "insider_name": "Alice"},
        {"type": "P", "insider_name": "Bob"},
        {"type": "P", "insider_name": "Charlie"},
        {"type": "S", "insider_name": "Dave"},
    ]

    result = calc_clustering_score(transactions)
    assert result == 3  # 3 unique buyers vs 1 seller


def test_clustering_score_sellers():
    """Test clustering score with dominant selling."""
    from src.transformations.factors.sec_factors import calc_clustering_score

    transactions = [
        {"type": "S", "insider_name": "Alice"},
        {"type": "S", "insider_name": "Bob"},
        {"type": "S", "insider_name": "Charlie"},
        {"type": "P", "insider_name": "Dave"},
    ]

    result = calc_clustering_score(transactions)
    assert result == -3  # Negative indicates selling dominance


def test_clustering_score_same_insider_multiple_trades():
    """Test that same insider is only counted once."""
    from src.transformations.factors.sec_factors import calc_clustering_score

    transactions = [
        {"type": "P", "insider_name": "Alice"},
        {"type": "P", "insider_name": "Alice"},  # Same insider
        {"type": "P", "insider_name": "Alice"},  # Same insider
        {"type": "S", "insider_name": "Bob"},
    ]

    result = calc_clustering_score(transactions)
    assert result == 1  # Only 1 unique buyer vs 1 seller


def test_yield_curve_slope():
    """Test yield curve slope calculation."""
    from src.transformations.factors.macro_factors import calc_yield_curve_slope

    gs10 = 4.5
    gs2 = 4.2

    result = calc_yield_curve_slope(gs10, gs2)
    assert result == pytest.approx(0.3)


def test_yield_curve_inverted():
    """Test inverted yield curve detection."""
    from src.transformations.factors.macro_factors import calc_yield_curve_slope

    gs10 = 4.0
    gs2 = 4.5

    result = calc_yield_curve_slope(gs10, gs2)
    assert result == -0.5  # Negative = inverted


def test_credit_spread():
    """Test credit spread calculation."""
    from src.transformations.factors.macro_factors import calc_credit_spread

    baa_spread = 2.5
    result = calc_credit_spread(baa_spread)
    assert result == 2.5


def test_factor_registry():
    """Test factor registry contains expected factors."""
    from src.transformations.base import FactorRegistry

    factors = FactorRegistry.get_all()

    # Should have registered factors
    assert "insider_transaction_momentum" in factors
    assert "insider_clustering_score" in factors
    assert "yield_curve_slope" in factors
    assert "credit_spread_index" in factors


def test_factor_definition():
    """Test factor definition retrieval."""
    from src.transformations.factors.sec_factors import InsiderTransactionMomentum

    factor = InsiderTransactionMomentum()
    definition = factor.get_definition()

    assert definition["id"] == "insider_transaction_momentum"
    assert definition["category"] == "sec"
    assert definition["entity_type"] == "company"
    assert definition["frequency"] == "daily"


def test_factor_list():
    """Test listing all factors."""
    from src.transformations.base import FactorRegistry

    factors = FactorRegistry.list_factors()

    assert len(factors) >= 5  # At least our implemented factors
    assert all("id" in f for f in factors)
    assert all("category" in f for f in factors)


def test_macro_factor_with_db_data():
    """Test macro factor computation with database data."""
    from src.models.database import SessionLocal
    from src.models.schemas import FREDSeries
    from src.transformations.factors.macro_factors import YieldCurveSlope
    from datetime import datetime

    session = SessionLocal()
    try:
        # Insert test data
        gs10 = FREDSeries(
            series_id="GS10",
            observation_date=datetime(2024, 1, 15),
            value=4.50,
        )
        gs2 = FREDSeries(
            series_id="GS2",
            observation_date=datetime(2024, 1, 15),
            value=4.20,
        )
        session.add_all([gs10, gs2])
        session.commit()

        # Compute factor
        factor = YieldCurveSlope()
        result = factor.compute(as_of_date=datetime(2024, 1, 15))

        assert result == pytest.approx(0.30)

        # Cleanup
        session.query(FREDSeries).filter(
            FREDSeries.series_id.in_(["GS10", "GS2"]),
            FREDSeries.observation_date == datetime(2024, 1, 15)
        ).delete(synchronize_session=False)
        session.commit()

    finally:
        session.close()


def test_sec_factor_with_db_data():
    """Test SEC factor computation with database data."""
    from src.models.database import SessionLocal
    from src.models.schemas import SECForm4Transaction
    from src.transformations.factors.sec_factors import InsiderTransactionMomentum
    from datetime import datetime

    session = SessionLocal()
    try:
        # Insert test transactions
        txn1 = SECForm4Transaction(
            accession_number="TEST-MOMENTUM-001",
            cik="TEST123",
            issuer_cik="TEST_ISSUER",
            ticker="TEST",
            transaction_type="P",
            shares=1000,
            price_per_share=100.0,
            transaction_date=datetime(2024, 1, 10),
        )
        txn2 = SECForm4Transaction(
            accession_number="TEST-MOMENTUM-002",
            cik="TEST456",
            issuer_cik="TEST_ISSUER",
            ticker="TEST",
            transaction_type="S",
            shares=500,
            price_per_share=105.0,
            transaction_date=datetime(2024, 1, 12),
        )
        session.add_all([txn1, txn2])
        session.commit()

        # Compute factor
        factor = InsiderTransactionMomentum()
        result = factor.compute("TEST", as_of_date=datetime(2024, 1, 15))

        # Net = 1000*100 - 500*105 = 100000 - 52500 = 47500
        assert result == 47500.0

        # Cleanup
        session.query(SECForm4Transaction).filter(
            SECForm4Transaction.accession_number.like("TEST-MOMENTUM-%")
        ).delete(synchronize_session=False)
        session.commit()

    finally:
        session.close()


def test_factor_store_and_retrieve():
    """Test storing and retrieving factor values."""
    from src.models.database import SessionLocal
    from src.models.schemas import Factor, SECForm4Transaction
    from src.transformations.factors.sec_factors import InsiderTransactionMomentum
    from datetime import datetime

    session = SessionLocal()
    try:
        # Clean up any existing test data first
        session.query(Factor).filter_by(
            factor_name="insider_transaction_momentum",
            entity_id="STORE"
        ).delete()
        session.query(SECForm4Transaction).filter_by(
            accession_number="TEST-STORE-001"
        ).delete()
        session.commit()

        # Setup test data
        txn = SECForm4Transaction(
            accession_number="TEST-STORE-001",
            cik="STORE_TEST",
            issuer_cik="STORE_ISSUER",
            ticker="STORE",
            transaction_type="P",
            shares=2000,
            price_per_share=50.0,
            transaction_date=datetime(2024, 1, 10),
        )
        session.add(txn)
        session.commit()

        # Compute and store
        factor = InsiderTransactionMomentum()
        stored = factor.compute_and_store("STORE", as_of_date=datetime(2024, 1, 15))

        assert stored is not None
        assert stored.value == 100000.0
        assert stored.factor_name == "insider_transaction_momentum"

        # Retrieve from database
        result = session.query(Factor).filter_by(
            factor_name="insider_transaction_momentum",
            entity_id="STORE"
        ).first()

        assert result is not None
        assert result.value == 100000.0

        # Cleanup
        session.query(Factor).filter_by(
            factor_name="insider_transaction_momentum",
            entity_id="STORE"
        ).delete()
        session.query(SECForm4Transaction).filter_by(
            accession_number="TEST-STORE-001"
        ).delete()
        session.commit()

    finally:
        session.close()
