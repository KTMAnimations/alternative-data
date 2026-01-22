"""Stage 7: End-to-end integration tests."""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create test client."""
    from src.api.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def api_key():
    """Get test API key."""
    return "test-api-key"


class TestE2EPipeline:
    """End-to-end pipeline tests."""

    def test_full_sec_pipeline(self, client, api_key):
        """Test complete SEC data pipeline.

        1. Insert raw Form 4 data (simulating collector)
        2. Verify data is stored
        3. Compute factor
        4. Query via API
        5. Verify response
        """
        from src.models.database import SessionLocal
        from src.models.schemas import SECForm4Transaction, Factor, Entity
        from src.transformations.factors.sec_factors import InsiderTransactionMomentum

        session = SessionLocal()
        try:
            # 1. Setup: Create entity and transactions
            entity = Entity(
                id="E2E_SEC_TEST",
                entity_type="company",
                name="E2E Test Company",
                ticker="E2E",
            )
            session.add(entity)

            # Add multiple transactions
            txns = [
                SECForm4Transaction(
                    accession_number=f"E2E-SEC-{i}",
                    cik=f"E2E{i}",
                    issuer_cik="E2E_ISSUER",
                    ticker="E2E",
                    insider_name=f"Insider {i}",
                    transaction_type="P" if i % 2 == 0 else "S",
                    shares=1000 * (i + 1),
                    price_per_share=100.0,
                    transaction_date=datetime(2024, 1, 10 + i),
                )
                for i in range(5)
            ]
            session.add_all(txns)
            session.commit()

            # 2. Verify raw data stored
            stored_count = session.query(SECForm4Transaction).filter(
                SECForm4Transaction.ticker == "E2E"
            ).count()
            assert stored_count == 5

            # 3. Compute factor
            factor = InsiderTransactionMomentum()
            value = factor.compute("E2E", as_of_date=datetime(2024, 1, 20))
            assert value is not None

            # Store the computed factor
            stored_factor = factor.compute_and_store("E2E", as_of_date=datetime(2024, 1, 20))
            assert stored_factor is not None

            # 4. Query via API
            response = client.get(
                "/api/v1/factors/insider_transaction_momentum",
                params={
                    "entity_id": "E2E",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200

            # 5. Verify response
            data = response.json()
            assert data["factor_name"] == "insider_transaction_momentum"
            assert data["entity_id"] == "E2E"
            assert len(data["values"]) >= 1

        finally:
            # Cleanup
            session.query(Factor).filter_by(entity_id="E2E").delete()
            session.query(SECForm4Transaction).filter(
                SECForm4Transaction.ticker == "E2E"
            ).delete()
            session.query(Entity).filter_by(id="E2E_SEC_TEST").delete()
            session.commit()
            session.close()

    def test_full_macro_pipeline(self, client, api_key):
        """Test complete FRED/macro data pipeline.

        1. Insert FRED series data (simulating collector)
        2. Compute yield curve slope
        3. Query via API
        4. Verify calculation
        """
        from src.models.database import SessionLocal
        from src.models.schemas import FREDSeries, Factor
        from src.transformations.factors.macro_factors import YieldCurveSlope

        session = SessionLocal()
        try:
            # 1. Insert FRED data
            gs10 = FREDSeries(
                series_id="GS10",
                observation_date=datetime(2024, 1, 20),
                value=4.50,
            )
            gs2 = FREDSeries(
                series_id="GS2",
                observation_date=datetime(2024, 1, 20),
                value=4.20,
            )
            session.add_all([gs10, gs2])
            session.commit()

            # 2. Compute factor
            factor = YieldCurveSlope()
            value = factor.compute(as_of_date=datetime(2024, 1, 20))

            assert value is not None
            assert value == pytest.approx(0.30)  # 4.50 - 4.20

            # Store factor
            stored = factor.compute_and_store("MARKET", as_of_date=datetime(2024, 1, 20))
            assert stored is not None

            # 3. Query via API
            response = client.get(
                "/api/v1/factors/yield_curve_slope",
                params={"entity_id": "MARKET"},
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200

            # 4. Verify
            data = response.json()
            assert data["factor_name"] == "yield_curve_slope"
            assert len(data["values"]) >= 1

        finally:
            # Cleanup
            session.query(Factor).filter_by(
                factor_name="yield_curve_slope",
                entity_id="MARKET"
            ).delete()
            session.query(FREDSeries).filter(
                FREDSeries.observation_date == datetime(2024, 1, 20)
            ).delete()
            session.commit()
            session.close()

    def test_entity_factor_relationship(self, client, api_key):
        """Test querying multiple factors for same entity."""
        from src.models.database import SessionLocal
        from src.models.schemas import SECForm4Transaction, Factor, Entity

        session = SessionLocal()
        try:
            # Setup entity with data
            entity = Entity(
                id="MULTI_FACTOR",
                entity_type="company",
                name="Multi Factor Test",
                ticker="MFT",
            )
            session.add(entity)

            txn = SECForm4Transaction(
                accession_number="MFT-001",
                cik="MFT_CIK",
                issuer_cik="MFT_ISSUER",
                ticker="MFT",
                insider_name="Test Insider",
                transaction_type="P",
                shares=5000,
                price_per_share=50.0,
                transaction_date=datetime(2024, 1, 15),
            )
            session.add(txn)
            session.commit()

            # Query multiple factors
            factors_to_test = [
                "insider_transaction_momentum",
                "insider_clustering_score",
            ]

            for factor_name in factors_to_test:
                response = client.get(
                    f"/api/v1/factors/{factor_name}",
                    params={"entity_id": "MFT"},
                    headers={"X-API-Key": api_key}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["factor_name"] == factor_name

        finally:
            session.query(SECForm4Transaction).filter_by(
                accession_number="MFT-001"
            ).delete()
            session.query(Entity).filter_by(id="MULTI_FACTOR").delete()
            session.commit()
            session.close()


class TestDataConsistency:
    """Test data consistency across the system."""

    def test_factor_versioning(self):
        """Test that factors are properly versioned."""
        from src.models.database import SessionLocal
        from src.models.schemas import SECForm4Transaction, Factor
        from src.transformations.factors.sec_factors import InsiderTransactionMomentum
        from datetime import datetime

        session = SessionLocal()
        try:
            # Setup
            txn = SECForm4Transaction(
                accession_number="VERSION-001",
                cik="VERSION",
                issuer_cik="VERSION_ISS",
                ticker="VER",
                transaction_type="P",
                shares=1000,
                price_per_share=10.0,
                transaction_date=datetime(2024, 1, 10),
            )
            session.add(txn)
            session.commit()

            # First computation
            factor = InsiderTransactionMomentum()
            stored1 = factor.compute_and_store("VER", as_of_date=datetime(2024, 1, 15))
            assert stored1.version == 1
            first_value = stored1.value

            # Update transaction
            txn.shares = 2000
            session.commit()

            # Second computation (should update version)
            stored2 = factor.compute_and_store("VER", as_of_date=datetime(2024, 1, 15))
            assert stored2.version == 2
            assert stored2.value != first_value

        finally:
            session.query(Factor).filter_by(entity_id="VER").delete()
            session.query(SECForm4Transaction).filter_by(
                accession_number="VERSION-001"
            ).delete()
            session.commit()
            session.close()


class TestPerformance:
    """Performance tests."""

    def test_api_response_under_500ms(self, client, api_key):
        """Test that API responses are under 500ms."""
        import time

        endpoints = [
            "/health",
            "/api/v1/factors",
            "/api/v1/entities",
            "/api/v1/sources",
        ]

        for endpoint in endpoints:
            start = time.time()
            response = client.get(
                endpoint,
                headers={"X-API-Key": api_key} if "api/v1" in endpoint else {}
            )
            elapsed = time.time() - start

            assert response.status_code == 200
            assert elapsed < 0.5, f"{endpoint} took {elapsed:.2f}s"

    def test_factor_computation_performance(self):
        """Test factor computation is reasonably fast."""
        import time
        from src.transformations.factors.sec_factors import InsiderTransactionMomentum
        from datetime import datetime

        factor = InsiderTransactionMomentum()

        start = time.time()
        # Even with no data, computation should be fast
        value = factor.compute("PERF_TEST", as_of_date=datetime(2024, 1, 15))
        elapsed = time.time() - start

        assert elapsed < 0.5


class TestCollectorIntegration:
    """Test collector integration."""

    def test_sec_collector_parsing(self, sample_form4_xml):
        """Test SEC collector XML parsing."""
        from src.collectors.sec_edgar import SECEdgarCollector

        collector = SECEdgarCollector(user_agent="Test test@test.com")
        result = collector.parse_form4_xml(sample_form4_xml)

        assert result["issuer_cik"] == "0001318605"
        assert result["ticker"] == "TSLA"
        assert len(result["transactions"]) > 0

    def test_fred_collector_parsing(self, sample_fred_response):
        """Test FRED collector response parsing."""
        from src.collectors.fred import FREDCollector

        collector = FREDCollector(api_key="test")
        result = collector.parse_series_response(sample_fred_response, "GS10")

        assert len(result) == 5
        assert all(r["series_id"] == "GS10" for r in result)


def test_system_components_exist():
    """Verify all system components are properly configured."""
    # Check collectors exist
    from src.collectors.sec_edgar import SECEdgarCollector
    from src.collectors.fred import FREDCollector

    # Check factors are registered
    from src.transformations.base import FactorRegistry
    factors = FactorRegistry.get_all()
    assert len(factors) >= 5

    # Check API app exists
    from src.api.main import app
    assert app is not None

    # Check database models
    from src.models.schemas import (
        Entity, Factor, RawDataCatalog,
        SECForm4Transaction, FREDSeries
    )

    # All components are properly imported and configured
    assert True
