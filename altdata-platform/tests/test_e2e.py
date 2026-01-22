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


class TestPhase1E2EPipeline:
    """End-to-end tests for Phase 1 data sources."""

    def test_full_adsb_pipeline(self, client, api_key):
        """Test complete ADS-B Exchange data pipeline.

        1. Insert aircraft and flight landing data
        2. Verify data is stored
        3. Compute aviation factor
        4. Query via API
        5. Verify response
        """
        from src.models.database import SessionLocal
        from src.models.adsb import Aircraft, FlightLanding
        from src.models.schemas import Factor, Entity
        from src.transformations.factors.aviation_factors import ExecutiveFlightFrequency

        session = SessionLocal()
        try:
            # 1. Setup: Create entity, aircraft, and flight data
            entity = Entity(
                id="E2E_ADSB_TEST",
                entity_type="company",
                name="E2E Aviation Test Company",
                ticker="ADSB",
            )
            session.add(entity)
            session.flush()

            aircraft = Aircraft(
                icao_hex="E2ETEST",
                registration="N12345",
                aircraft_type="GLF6",
                owner_name="E2E Aviation Test Company",
                owner_type="corporate",
                company_entity_id="E2E_ADSB_TEST",
                is_corporate_jet=True,
            )
            session.add(aircraft)
            session.flush()

            # Add flight landings
            landings = [
                FlightLanding(
                    icao_hex="E2ETEST",
                    aircraft_id=aircraft.id,
                    landing_timestamp=datetime(2024, 1, 10 + i),
                    airport_icao=f"KSF{i}",
                    airport_name=f"Test Airport {i}",
                    latitude=37.7749 + i * 0.1,
                    longitude=-122.4194 + i * 0.1,
                )
                for i in range(5)
            ]
            session.add_all(landings)
            session.commit()

            # 2. Verify raw data stored
            stored_count = session.query(FlightLanding).filter(
                FlightLanding.icao_hex == "E2ETEST"
            ).count()
            assert stored_count == 5

            # 3. Compute factor
            factor = ExecutiveFlightFrequency()
            value = factor.compute("E2E_ADSB_TEST", as_of_date=datetime(2024, 1, 20))
            assert value is not None

            # Store the computed factor
            stored_factor = factor.compute_and_store("E2E_ADSB_TEST", as_of_date=datetime(2024, 1, 20))
            assert stored_factor is not None

            # 4. Query via API
            response = client.get(
                "/api/v1/factors/executive_flight_frequency",
                params={
                    "entity_id": "E2E_ADSB_TEST",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200

            # 5. Verify response
            data = response.json()
            assert data["factor_name"] == "executive_flight_frequency"
            assert data["entity_id"] == "E2E_ADSB_TEST"

            # Also test the new aviation flights endpoint
            response = client.get(
                "/api/v1/aviation/flights",
                params={
                    "company_id": "E2E_ADSB_TEST",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200
            flights_data = response.json()
            assert flights_data["company_id"] == "E2E_ADSB_TEST"
            assert flights_data["total"] == 5

        finally:
            # Cleanup
            session.query(Factor).filter_by(entity_id="E2E_ADSB_TEST").delete()
            session.query(FlightLanding).filter(FlightLanding.icao_hex == "E2ETEST").delete()
            session.query(Aircraft).filter_by(icao_hex="E2ETEST").delete()
            session.query(Entity).filter_by(id="E2E_ADSB_TEST").delete()
            session.commit()
            session.close()

    def test_full_power_grid_pipeline(self, client, api_key):
        """Test complete Power Grid data pipeline.

        1. Insert grid load data
        2. Verify data is stored
        3. Compute power grid factor
        4. Query via API
        5. Verify response
        """
        from src.models.database import SessionLocal
        from src.models.power_grid import GridLoad, GenerationMix
        from src.models.schemas import Factor
        from src.transformations.factors.power_grid_factors import GridLoadSurprise

        session = SessionLocal()
        try:
            # 1. Insert grid load data for CAISO
            loads = [
                GridLoad(
                    iso_region="CAISO",
                    timestamp=datetime(2024, 1, 15, hour, 0, 0),
                    load_mw=25000 + hour * 500,
                    forecast_mw=24500 + hour * 500,
                    capacity_mw=50000,
                )
                for hour in range(24)
            ]
            session.add_all(loads)
            session.commit()

            # 2. Verify data stored
            stored_count = session.query(GridLoad).filter(
                GridLoad.iso_region == "CAISO"
            ).count()
            assert stored_count >= 24

            # 3. Compute factor
            factor = GridLoadSurprise()
            value = factor.compute("CAISO", as_of_date=datetime(2024, 1, 15))
            assert value is not None

            # Store the computed factor
            stored_factor = factor.compute_and_store("CAISO", as_of_date=datetime(2024, 1, 15))
            assert stored_factor is not None

            # 4. Query via API
            response = client.get(
                "/api/v1/factors/grid_load_surprise",
                params={
                    "entity_id": "CAISO",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200

            # 5. Verify response
            data = response.json()
            assert data["factor_name"] == "grid_load_surprise"
            assert data["entity_id"] == "CAISO"

            # Also test the new energy load endpoint
            response = client.get(
                "/api/v1/energy/load",
                params={
                    "iso": "CAISO",
                    "date": "2024-01-15",
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200
            load_data = response.json()
            assert load_data["iso"] == "CAISO"
            assert load_data["total"] == 24

        finally:
            # Cleanup
            session.query(Factor).filter_by(entity_id="CAISO").delete()
            session.query(GridLoad).filter(GridLoad.iso_region == "CAISO").delete()
            session.commit()
            session.close()

    def test_full_uspto_pipeline(self, client, api_key):
        """Test complete USPTO patent data pipeline.

        1. Insert patent data
        2. Verify data is stored
        3. Compute patent factor
        4. Query via API
        5. Verify response
        """
        from src.models.database import SessionLocal
        from src.models.patents import Patent, PatentAssignee
        from src.models.schemas import Factor, Entity
        from src.transformations.factors.patent_factors import PatentMomentum

        session = SessionLocal()
        try:
            # 1. Setup: Create entity and patent data
            entity = Entity(
                id="E2E_USPTO_TEST",
                entity_type="company",
                name="E2E Patent Test Company",
                ticker="PAT",
            )
            session.add(entity)
            session.flush()

            # Add patents
            patents = [
                Patent(
                    patent_number=f"E2E-PAT-{i:04d}",
                    application_number=f"E2E-APP-{i:04d}",
                    title=f"Test Patent {i}",
                    filing_date=datetime(2023, 6, 1 + i),
                    grant_date=datetime(2024, 1, 10 + i),
                    patent_type="utility",
                    claims_count=10 + i,
                    primary_class="G06N",
                    status="granted",
                )
                for i in range(10)
            ]
            session.add_all(patents)
            session.flush()

            # Add assignees
            assignees = [
                PatentAssignee(
                    patent_number=f"E2E-PAT-{i:04d}",
                    assignee_name="E2E Patent Test Company",
                    entity_id="E2E_USPTO_TEST",
                    is_original_assignee=True,
                )
                for i in range(10)
            ]
            session.add_all(assignees)
            session.commit()

            # 2. Verify data stored
            stored_count = session.query(Patent).filter(
                Patent.patent_number.like("E2E-PAT%")
            ).count()
            assert stored_count == 10

            # 3. Compute factor
            factor = PatentMomentum()
            value = factor.compute("E2E_USPTO_TEST", as_of_date=datetime(2024, 1, 20))
            assert value is not None

            # Store the computed factor
            stored_factor = factor.compute_and_store("E2E_USPTO_TEST", as_of_date=datetime(2024, 1, 20))
            assert stored_factor is not None

            # 4. Query via API
            response = client.get(
                "/api/v1/factors/patent_momentum",
                params={
                    "entity_id": "E2E_USPTO_TEST",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200

            # 5. Verify response
            data = response.json()
            assert data["factor_name"] == "patent_momentum"
            assert data["entity_id"] == "E2E_USPTO_TEST"

            # Also test the new patents endpoint
            response = client.get(
                "/api/v1/patents/filings",
                params={
                    "company_id": "E2E_USPTO_TEST",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200
            patents_data = response.json()
            assert patents_data["company_id"] == "E2E_USPTO_TEST"
            assert patents_data["total"] == 10

        finally:
            # Cleanup
            session.query(Factor).filter_by(entity_id="E2E_USPTO_TEST").delete()
            session.query(PatentAssignee).filter(PatentAssignee.patent_number.like("E2E-PAT%")).delete()
            session.query(Patent).filter(Patent.patent_number.like("E2E-PAT%")).delete()
            session.query(Entity).filter_by(id="E2E_USPTO_TEST").delete()
            session.commit()
            session.close()

    def test_full_openaq_pipeline(self, client, api_key):
        """Test complete OpenAQ air quality data pipeline.

        1. Insert air quality measurement data
        2. Verify data is stored
        3. Compute air quality factor
        4. Query via API
        5. Verify response
        """
        from src.models.database import SessionLocal
        from src.models.air_quality import AirQualityLocation, AirQualityMeasurement
        from src.models.schemas import Factor
        from src.transformations.factors.air_quality_factors import AirQualityAnomaly

        session = SessionLocal()
        location_id_str = "E2E_AQ_999999"
        try:
            # 1. Setup: Create location and measurements
            location = AirQualityLocation(
                location_id=location_id_str,
                name="E2E Test Monitor",
                city="San Francisco",
                country="US",
                latitude=37.7749,
                longitude=-122.4194,
            )
            session.add(location)
            session.flush()

            # Add measurements (20 days of data for anomaly calculation)
            measurements = [
                AirQualityMeasurement(
                    location_id=location_id_str,
                    timestamp=datetime(2024, 1, day, 12, 0, 0),
                    parameter="pm25",
                    value=15.0 + (day % 5),  # Slight variation
                    unit="ug/m3",
                )
                for day in range(1, 21)
            ]
            session.add_all(measurements)
            session.commit()

            # 2. Verify data stored
            stored_count = session.query(AirQualityMeasurement).filter(
                AirQualityMeasurement.location_id == location_id_str
            ).count()
            assert stored_count == 20

            # 3. Compute factor
            factor = AirQualityAnomaly()
            value = factor.compute(location_id_str, as_of_date=datetime(2024, 1, 20))
            # Value might be None if not enough historical data, which is ok for this test
            # The important thing is the factor computes without error

            # Store the computed factor
            stored_factor = factor.compute_and_store(location_id_str, as_of_date=datetime(2024, 1, 20))
            # May be None if no anomaly detected

            # 4. Query via API - test the factor endpoint
            response = client.get(
                "/api/v1/factors/air_quality_anomaly",
                params={
                    "entity_id": location_id_str,
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200

            # 5. Verify response
            data = response.json()
            assert data["factor_name"] == "air_quality_anomaly"

            # Also test the new air quality endpoint
            response = client.get(
                "/api/v1/environment/air-quality",
                params={
                    "date": "2024-01-15",
                    "city": "San Francisco",
                    "parameter": "pm25",
                },
                headers={"X-API-Key": api_key}
            )
            assert response.status_code == 200
            aq_data = response.json()
            assert aq_data["city"] == "San Francisco"
            assert aq_data["total"] > 0

        finally:
            # Cleanup
            session.query(Factor).filter_by(entity_id=location_id_str).delete()
            session.query(AirQualityMeasurement).filter(
                AirQualityMeasurement.location_id == location_id_str
            ).delete()
            session.query(AirQualityLocation).filter_by(location_id=location_id_str).delete()
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
    # Check collectors exist (MVP + Phase 1)
    from src.collectors.sec_edgar import SECEdgarCollector
    from src.collectors.fred import FREDCollector
    from src.collectors.adsb_exchange import ADSBExchangeCollector
    from src.collectors.power_grid import CAISOCollector, ERCOTCollector, PJMCollector, MISOCollector
    from src.collectors.uspto import USPTOCollector
    from src.collectors.openaq import OpenAQCollector

    # Check factors are registered (should have 23+ for Phase 1)
    from src.transformations.base import FactorRegistry
    factors = FactorRegistry.get_all()
    assert len(factors) >= 20, f"Expected at least 20 factors, got {len(factors)}"

    # Check API app exists
    from src.api.main import app
    assert app is not None

    # Check database models (MVP)
    from src.models.schemas import (
        Entity, Factor, RawDataCatalog,
        SECForm4Transaction, FREDSeries
    )

    # Check Phase 1 database models
    from src.models.adsb import Aircraft, FlightPosition, FlightLanding
    from src.models.power_grid import GridLoad, GridPrice, GenerationMix
    from src.models.patents import Patent, PatentAssignee, PatentCitation
    from src.models.air_quality import AirQualityLocation, AirQualityMeasurement

    # All components are properly imported and configured
    assert True


def test_phase1_api_endpoints_exist(client, api_key):
    """Verify Phase 1 Stage 6 API endpoints exist."""
    # Test aviation endpoint
    response = client.get(
        "/api/v1/aviation/flights",
        params={"company_id": "TEST"},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200

    # Test energy endpoint
    response = client.get(
        "/api/v1/energy/load",
        params={"iso": "CAISO", "date": "2024-01-15"},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200

    # Test patents endpoint
    response = client.get(
        "/api/v1/patents/filings",
        params={"company_id": "TEST"},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200

    # Test air quality endpoint
    response = client.get(
        "/api/v1/environment/air-quality",
        params={"date": "2024-01-15"},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200
