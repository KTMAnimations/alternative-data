"""Tests for US Power Grid ISO collectors and factors."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock


class TestPowerGridModels:
    """Tests for power grid database models."""

    def test_grid_load_model_creation(self):
        """Test GridLoad model can be instantiated."""
        from src.models.power_grid import GridLoad

        load = GridLoad(
            iso_region="CAISO",
            timestamp=datetime.utcnow(),
            load_mw=25000.0,
            forecast_mw=24500.0,
            capacity_mw=50000.0,
        )

        assert load.iso_region == "CAISO"
        assert load.load_mw == 25000.0
        assert load.forecast_mw == 24500.0

    def test_grid_price_model_creation(self):
        """Test GridPrice model can be instantiated."""
        from src.models.power_grid import GridPrice

        price = GridPrice(
            iso_region="PJM",
            node_id="WESTERN_HUB",
            timestamp=datetime.utcnow(),
            lmp_total=45.50,
            lmp_energy=40.00,
            lmp_congestion=3.50,
            lmp_loss=2.00,
        )

        assert price.iso_region == "PJM"
        assert price.lmp_total == 45.50

    def test_generation_mix_model_creation(self):
        """Test GenerationMix model can be instantiated."""
        from src.models.power_grid import GenerationMix

        gen = GenerationMix(
            iso_region="ERCOT",
            timestamp=datetime.utcnow(),
            total_generation_mw=50000.0,
            natural_gas_mw=20000.0,
            wind_mw=15000.0,
            solar_mw=8000.0,
            nuclear_mw=5000.0,
            coal_mw=2000.0,
            renewable_pct=46.0,
        )

        assert gen.iso_region == "ERCOT"
        assert gen.wind_mw == 15000.0
        assert gen.renewable_pct == 46.0

    def test_grid_outage_model_creation(self):
        """Test GridOutage model can be instantiated."""
        from src.models.power_grid import GridOutage

        outage = GridOutage(
            iso_region="MISO",
            outage_id="OUT-2024-001",
            facility_name="Plant A",
            facility_type="generator",
            outage_type="planned",
            capacity_mw=500.0,
            start_time=datetime.utcnow(),
            status="active",
        )

        assert outage.outage_id == "OUT-2024-001"
        assert outage.outage_type == "planned"


class TestGridCollectors:
    """Tests for power grid collectors."""

    @pytest.fixture
    def caiso_collector(self):
        from src.collectors.power_grid import CAISOCollector
        return CAISOCollector()

    @pytest.fixture
    def ercot_collector(self):
        from src.collectors.power_grid import ERCOTCollector
        return ERCOTCollector()

    @pytest.fixture
    def pjm_collector(self):
        from src.collectors.power_grid import PJMCollector
        return PJMCollector()

    @pytest.fixture
    def miso_collector(self):
        from src.collectors.power_grid import MISOCollector
        return MISOCollector()

    def test_caiso_collector_source_name(self, caiso_collector):
        """Test CAISO collector source name."""
        assert caiso_collector.SOURCE_NAME == "caiso"
        assert caiso_collector.ISO_REGION == "CAISO"

    def test_ercot_collector_source_name(self, ercot_collector):
        """Test ERCOT collector source name."""
        assert ercot_collector.SOURCE_NAME == "ercot"
        assert ercot_collector.ISO_REGION == "ERCOT"

    def test_pjm_collector_source_name(self, pjm_collector):
        """Test PJM collector source name."""
        assert pjm_collector.SOURCE_NAME == "pjm"
        assert pjm_collector.ISO_REGION == "PJM"

    def test_miso_collector_source_name(self, miso_collector):
        """Test MISO collector source name."""
        assert miso_collector.SOURCE_NAME == "miso"
        assert miso_collector.ISO_REGION == "MISO"

    def test_get_grid_collector_factory(self):
        """Test factory function for grid collectors."""
        from src.collectors.power_grid import get_grid_collector, CAISOCollector, ERCOTCollector

        caiso = get_grid_collector("CAISO")
        assert isinstance(caiso, CAISOCollector)

        ercot = get_grid_collector("ERCOT")
        assert isinstance(ercot, ERCOTCollector)

    def test_get_grid_collector_invalid_region(self):
        """Test factory function raises for invalid region."""
        from src.collectors.power_grid import get_grid_collector

        with pytest.raises(ValueError, match="Unsupported ISO region"):
            get_grid_collector("INVALID")

    def test_ercot_extract_value(self, ercot_collector):
        """Test ERCOT HTML value extraction."""
        html = """
        <table>
            <tr><td>Current System Demand</td><td>45,123 MW</td></tr>
            <tr><td>Available Capacity</td><td>70,000 MW</td></tr>
        </table>
        """

        demand = ercot_collector._extract_value(html, "Current System Demand")
        assert demand == 45123.0

        capacity = ercot_collector._extract_value(html, "Available Capacity")
        assert capacity == 70000.0

    def test_ercot_extract_value_not_found(self, ercot_collector):
        """Test ERCOT extraction returns 0 when not found."""
        html = "<html><body>No data here</body></html>"

        result = ercot_collector._extract_value(html, "Missing Label")
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_caiso_collector_context_manager(self, caiso_collector):
        """Test async context manager."""
        async with caiso_collector:
            assert caiso_collector is not None
            assert caiso_collector.ISO_REGION == "CAISO"


class TestPowerGridFactors:
    """Tests for power grid-derived factors."""

    def test_factor_registry_has_power_grid_factors(self):
        """Test that power grid factors are registered."""
        from src.transformations.base import FactorRegistry
        # Import to trigger registration
        from src.transformations.factors import power_grid_factors

        factors = FactorRegistry.get_all()

        assert "grid_load_surprise" in factors
        assert "regional_power_demand" in factors
        assert "renewable_share" in factors
        assert "load_capacity_ratio" in factors
        assert "yoy_demand_change" in factors

    def test_grid_load_surprise_factor_definition(self):
        """Test grid load surprise factor definition."""
        from src.transformations.factors.power_grid_factors import GridLoadSurprise

        factor = GridLoadSurprise()
        definition = factor.get_definition()

        assert definition["id"] == "grid_load_surprise"
        assert definition["category"] == "power_grid"
        assert definition["entity_type"] == "iso_region"
        assert definition["frequency"] == "hourly"

    def test_regional_power_demand_factor_definition(self):
        """Test regional power demand factor definition."""
        from src.transformations.factors.power_grid_factors import RegionalPowerDemand

        factor = RegionalPowerDemand()
        definition = factor.get_definition()

        assert definition["id"] == "regional_power_demand"
        assert definition["category"] == "power_grid"
        assert definition["frequency"] == "daily"

    def test_renewable_share_factor_definition(self):
        """Test renewable share factor definition."""
        from src.transformations.factors.power_grid_factors import RenewableShare

        factor = RenewableShare()
        definition = factor.get_definition()

        assert definition["id"] == "renewable_share"
        assert definition["category"] == "power_grid"

    def test_load_capacity_ratio_factor_definition(self):
        """Test load capacity ratio factor definition."""
        from src.transformations.factors.power_grid_factors import LoadCapacityRatio

        factor = LoadCapacityRatio()
        definition = factor.get_definition()

        assert definition["id"] == "load_capacity_ratio"
        assert definition["category"] == "power_grid"
        assert definition["frequency"] == "hourly"


class TestPowerGridDatabaseIntegration:
    """Integration tests for power grid with database."""

    def test_store_grid_load(self):
        """Test storing grid load in database."""
        from src.models.database import SessionLocal
        from src.models.power_grid import GridLoad

        session = SessionLocal()
        try:
            # Clean up
            session.query(GridLoad).filter_by(iso_region="TEST_ISO").delete()
            session.commit()

            # Insert
            load = GridLoad(
                iso_region="TEST_ISO",
                timestamp=datetime.utcnow(),
                load_mw=30000.0,
                forecast_mw=29500.0,
                capacity_mw=60000.0,
                load_pct_of_capacity=50.0,
            )
            session.add(load)
            session.commit()

            # Query
            result = session.query(GridLoad).filter_by(iso_region="TEST_ISO").first()
            assert result is not None
            assert result.load_mw == 30000.0
            assert result.load_pct_of_capacity == 50.0

            # Cleanup
            session.delete(result)
            session.commit()

        finally:
            session.close()

    def test_store_generation_mix(self):
        """Test storing generation mix in database."""
        from src.models.database import SessionLocal
        from src.models.power_grid import GenerationMix

        session = SessionLocal()
        try:
            # Clean up
            session.query(GenerationMix).filter_by(iso_region="TEST_ISO").delete()
            session.commit()

            # Insert
            gen = GenerationMix(
                iso_region="TEST_ISO",
                timestamp=datetime.utcnow(),
                total_generation_mw=50000.0,
                natural_gas_mw=20000.0,
                wind_mw=15000.0,
                solar_mw=10000.0,
                renewable_pct=50.0,
            )
            session.add(gen)
            session.commit()

            # Query
            result = session.query(GenerationMix).filter_by(iso_region="TEST_ISO").first()
            assert result is not None
            assert result.renewable_pct == 50.0
            assert result.wind_mw == 15000.0

            # Cleanup
            session.delete(result)
            session.commit()

        finally:
            session.close()

    def test_calc_grid_load_surprise_with_data(self):
        """Test grid load surprise calculation with test data."""
        from src.models.database import SessionLocal
        from src.models.power_grid import GridLoad
        from src.transformations.factors.power_grid_factors import calc_grid_load_surprise

        session = SessionLocal()
        try:
            # Clean up
            session.query(GridLoad).filter_by(iso_region="SURPRISE_TEST").delete()
            session.commit()

            # Insert test data with 5% surprise (actual > forecast)
            now = datetime.utcnow()
            load = GridLoad(
                iso_region="SURPRISE_TEST",
                timestamp=now,
                load_mw=10500.0,  # Actual
                forecast_mw=10000.0,  # Forecast
            )
            session.add(load)
            session.commit()

            # Calculate surprise
            surprise = calc_grid_load_surprise(
                "SURPRISE_TEST",
                now + timedelta(hours=1),
                lookback_hours=2
            )

            assert surprise is not None
            assert pytest.approx(surprise, rel=0.01) == 5.0  # 5% surprise

            # Cleanup
            session.query(GridLoad).filter_by(iso_region="SURPRISE_TEST").delete()
            session.commit()

        finally:
            session.close()

    def test_calc_renewable_share_with_data(self):
        """Test renewable share calculation with test data."""
        from src.models.database import SessionLocal
        from src.models.power_grid import GenerationMix
        from src.transformations.factors.power_grid_factors import calc_renewable_share

        session = SessionLocal()
        try:
            # Clean up
            session.query(GenerationMix).filter_by(iso_region="RENEWABLE_TEST").delete()
            session.commit()

            # Insert test data with 40% renewable
            now = datetime.utcnow()
            gen = GenerationMix(
                iso_region="RENEWABLE_TEST",
                timestamp=now,
                total_generation_mw=100000.0,
                wind_mw=25000.0,
                solar_mw=10000.0,
                hydro_mw=5000.0,  # Total renewable = 40,000
                natural_gas_mw=40000.0,
                coal_mw=20000.0,
            )
            session.add(gen)
            session.commit()

            # Calculate renewable share
            share = calc_renewable_share(
                "RENEWABLE_TEST",
                now + timedelta(hours=1),
                lookback_hours=2
            )

            assert share is not None
            assert pytest.approx(share, rel=0.01) == 40.0  # 40% renewable

            # Cleanup
            session.query(GenerationMix).filter_by(iso_region="RENEWABLE_TEST").delete()
            session.commit()

        finally:
            session.close()
