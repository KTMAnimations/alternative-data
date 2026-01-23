"""Tests for earthquake-related factor computations."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.transformations.factors.earthquake_factors import (
    SeismicRiskExposure,
    DisasterImpactEstimate,
    haversine_distance,
    US_POPULATION_CENTERS,
    INSURANCE_EXPOSURE_REGIONS,
)
from src.transformations.factors.base import FactorResult
from src.models.data_sources import EarthquakeEvent


# Helper to create mock EarthquakeEvent objects
def create_mock_earthquake(
    event_id: str = "test_event",
    magnitude: Decimal = Decimal("5.5"),
    latitude: Decimal = Decimal("34.0522"),  # Los Angeles
    longitude: Decimal = Decimal("-118.2437"),
    depth_km: Decimal = Decimal("10.0"),
    timestamp: datetime = None,
    felt_reports: int = 1000,
    tsunami_flag: bool = False,
    alert_level: str = "green",
    estimated_population_exposure: int = 5000,
) -> MagicMock:
    """Create a mock EarthquakeEvent for testing."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc) - timedelta(days=1)

    mock = MagicMock(spec=EarthquakeEvent)
    mock.event_id = event_id
    mock.magnitude = magnitude
    mock.latitude = latitude
    mock.longitude = longitude
    mock.depth_km = depth_km
    mock.timestamp = timestamp
    mock.felt_reports = felt_reports
    mock.tsunami_flag = tsunami_flag
    mock.alert_level = alert_level
    mock.estimated_population_exposure = estimated_population_exposure
    return mock


class TestHaversineDistance:
    """Tests for the haversine distance calculation."""

    def test_same_point_returns_zero(self):
        """Test distance between same point is zero."""
        distance = haversine_distance(34.0522, -118.2437, 34.0522, -118.2437)
        assert distance == 0.0

    def test_known_distance_los_angeles_to_san_francisco(self):
        """Test known distance between LA and SF (~560km)."""
        la_lat, la_lon = 34.0522, -118.2437
        sf_lat, sf_lon = 37.7749, -122.4194

        distance = haversine_distance(la_lat, la_lon, sf_lat, sf_lon)

        # Should be approximately 560 km (allow 10% tolerance)
        assert 500 < distance < 620

    def test_equator_distance(self):
        """Test distance along equator."""
        # 1 degree of longitude at equator is approximately 111.32 km
        distance = haversine_distance(0, 0, 0, 1)
        assert 110 < distance < 113

    def test_symmetric(self):
        """Test distance is symmetric (A to B == B to A)."""
        d1 = haversine_distance(34.0522, -118.2437, 37.7749, -122.4194)
        d2 = haversine_distance(37.7749, -122.4194, 34.0522, -118.2437)

        assert abs(d1 - d2) < 0.001


class TestSeismicRiskExposure:
    """Tests for SeismicRiskExposure factor."""

    @pytest.fixture
    def factor(self):
        """Create factor instance for testing."""
        return SeismicRiskExposure()

    @pytest.mark.asyncio
    async def test_compute_no_events_returns_baseline(self, factor):
        """Test computation with no recent events returns baseline exposure."""
        with patch.object(factor, "_get_recent_events") as mock_get_events:
            mock_get_events.return_value = []

            results = await factor.compute(as_of_date=date.today())

            # Should return results for all primary entities
            assert len(results) == 4  # ALL, TRV, CB, PGR

            for result in results:
                assert result.mean == factor.BASELINE_EXPOSURE
                assert result.data_quality == Decimal("0.5")
                assert result.metadata["event_count"] == 0

    @pytest.mark.asyncio
    async def test_compute_with_events_returns_exposure(self, factor):
        """Test computation with events returns calculated exposure."""
        mock_events = [
            create_mock_earthquake(
                event_id="test1",
                magnitude=Decimal("5.5"),
                latitude=Decimal("34.0522"),  # Los Angeles
                longitude=Decimal("-118.2437"),
            ),
        ]

        with patch.object(factor, "_get_recent_events") as mock_get_events:
            mock_get_events.return_value = mock_events

            results = await factor.compute(as_of_date=date.today())

            assert len(results) == 4

            # All results should have exposure > baseline (event near LA)
            for result in results:
                assert result.mean >= factor.BASELINE_EXPOSURE
                assert result.data_quality == Decimal("0.95")
                assert result.metadata["event_count"] == 1

    @pytest.mark.asyncio
    async def test_compute_specific_tickers(self, factor):
        """Test computation for specific tickers only."""
        mock_events = [create_mock_earthquake()]

        with patch.object(factor, "_get_recent_events") as mock_get_events:
            mock_get_events.return_value = mock_events

            results = await factor.compute(
                as_of_date=date.today(),
                tickers=["ALL", "TRV"],
            )

            assert len(results) == 2
            tickers_returned = {r.ticker for r in results}
            assert tickers_returned == {"ALL", "TRV"}

    @pytest.mark.asyncio
    async def test_exposure_increases_with_magnitude(self, factor):
        """Test that higher magnitude events produce higher exposure."""
        small_event = [create_mock_earthquake(magnitude=Decimal("4.5"))]
        large_event = [create_mock_earthquake(magnitude=Decimal("7.0"))]

        with patch.object(factor, "_get_recent_events") as mock_get_events:
            # Compute for small event
            mock_get_events.return_value = small_event
            small_results = await factor.compute(
                as_of_date=date.today(),
                tickers=["ALL"],
            )

            # Compute for large event
            mock_get_events.return_value = large_event
            large_results = await factor.compute(
                as_of_date=date.today(),
                tickers=["ALL"],
            )

            # Larger event should produce higher exposure
            assert large_results[0].mean > small_results[0].mean

    @pytest.mark.asyncio
    async def test_exposure_decreases_with_distance(self, factor):
        """Test that events farther from population centers produce lower exposure."""
        # Event near LA
        near_event = [
            create_mock_earthquake(
                latitude=Decimal("34.0522"),
                longitude=Decimal("-118.2437"),
            )
        ]

        # Event far from any US population center (middle of Pacific)
        far_event = [
            create_mock_earthquake(
                latitude=Decimal("25.0"),
                longitude=Decimal("-150.0"),
            )
        ]

        with patch.object(factor, "_get_recent_events") as mock_get_events:
            # Near event
            mock_get_events.return_value = near_event
            near_results = await factor.compute(
                as_of_date=date.today(),
                tickers=["ALL"],
            )

            # Far event
            mock_get_events.return_value = far_event
            far_results = await factor.compute(
                as_of_date=date.today(),
                tickers=["ALL"],
            )

            # Near event should produce higher exposure
            assert near_results[0].mean > far_results[0].mean

    @pytest.mark.asyncio
    async def test_factor_result_structure(self, factor):
        """Test that factor results have correct structure."""
        mock_events = [create_mock_earthquake()]

        with patch.object(factor, "_get_recent_events") as mock_get_events:
            mock_get_events.return_value = mock_events

            results = await factor.compute(as_of_date=date.today())

            for result in results:
                assert isinstance(result, FactorResult)
                assert result.factor_id == "seismic_risk_exposure"
                assert result.as_of_date == date.today()
                assert isinstance(result.mean, Decimal)
                assert isinstance(result.variance, Decimal)
                assert isinstance(result.data_quality, Decimal)
                assert "event_count" in result.metadata

    def test_get_formula_returns_latex(self, factor):
        """Test formula returns valid LaTeX string."""
        formula = factor.get_formula()

        assert isinstance(formula, str)
        assert "SeismicRiskExposure" in formula
        assert r"\sum" in formula or "sum" in formula

    def test_get_economic_rationale(self, factor):
        """Test economic rationale is provided."""
        rationale = factor.get_economic_rationale()

        assert isinstance(rationale, str)
        assert len(rationale) > 100  # Should be substantial explanation
        assert "Insurance" in rationale or "insurance" in rationale

    def test_primary_entities(self, factor):
        """Test primary entities are insurance companies."""
        assert factor.primary_entities == ["ALL", "TRV", "CB", "PGR"]
        assert factor.domain == "insurance"


class TestDisasterImpactEstimate:
    """Tests for DisasterImpactEstimate factor."""

    @pytest.fixture
    def factor(self):
        """Create factor instance for testing."""
        return DisasterImpactEstimate()

    @pytest.mark.asyncio
    async def test_compute_no_events_returns_zero(self, factor):
        """Test computation with no significant events returns zero impact."""
        with patch.object(factor, "_get_significant_events") as mock_get_events:
            mock_get_events.return_value = []

            results = await factor.compute(as_of_date=date.today())

            assert len(results) == 4

            for result in results:
                assert result.mean == Decimal("0")
                assert result.variance == Decimal("0")
                assert result.metadata["event_count"] == 0

    @pytest.mark.asyncio
    async def test_compute_with_events_returns_impact(self, factor):
        """Test computation with significant events returns impact estimate."""
        mock_events = [
            create_mock_earthquake(
                magnitude=Decimal("6.0"),
                depth_km=Decimal("10.0"),
                estimated_population_exposure=10000,
            ),
        ]

        with patch.object(factor, "_get_significant_events") as mock_get_events:
            mock_get_events.return_value = mock_events

            results = await factor.compute(as_of_date=date.today())

            assert len(results) == 4

            for result in results:
                assert result.mean > Decimal("0")
                assert result.metadata["event_count"] == 1
                assert "total_economic_damage_usd" in result.metadata

    @pytest.mark.asyncio
    async def test_impact_increases_with_magnitude(self, factor):
        """Test that higher magnitude events produce higher impact."""
        small_event = [
            create_mock_earthquake(
                magnitude=Decimal("5.5"),
                estimated_population_exposure=5000,
            )
        ]
        large_event = [
            create_mock_earthquake(
                magnitude=Decimal("7.5"),
                estimated_population_exposure=5000,
            )
        ]

        with patch.object(factor, "_get_significant_events") as mock_get_events:
            # Small event
            mock_get_events.return_value = small_event
            small_results = await factor.compute(
                as_of_date=date.today(),
                tickers=["ALL"],
            )

            # Large event
            mock_get_events.return_value = large_event
            large_results = await factor.compute(
                as_of_date=date.today(),
                tickers=["ALL"],
            )

            # Larger magnitude should produce higher impact
            assert large_results[0].mean > small_results[0].mean

    @pytest.mark.asyncio
    async def test_impact_higher_for_shallow_events(self, factor):
        """Test that shallower events produce higher impact."""
        shallow_event = [
            create_mock_earthquake(
                magnitude=Decimal("6.0"),
                depth_km=Decimal("5.0"),  # Shallow
            )
        ]
        deep_event = [
            create_mock_earthquake(
                magnitude=Decimal("6.0"),
                depth_km=Decimal("50.0"),  # Deep
            )
        ]

        with patch.object(factor, "_get_significant_events") as mock_get_events:
            # Shallow event
            mock_get_events.return_value = shallow_event
            shallow_results = await factor.compute(
                as_of_date=date.today(),
                tickers=["ALL"],
            )

            # Deep event
            mock_get_events.return_value = deep_event
            deep_results = await factor.compute(
                as_of_date=date.today(),
                tickers=["ALL"],
            )

            # Shallow event should produce higher impact
            assert shallow_results[0].mean > deep_results[0].mean

    @pytest.mark.asyncio
    async def test_market_share_affects_impact(self, factor):
        """Test that companies with higher market share have higher impact."""
        mock_events = [
            create_mock_earthquake(
                magnitude=Decimal("6.5"),
                estimated_population_exposure=10000,
            )
        ]

        with patch.object(factor, "_get_significant_events") as mock_get_events:
            mock_get_events.return_value = mock_events

            results = await factor.compute(
                as_of_date=date.today(),
                tickers=["ALL", "CB"],  # ALL has higher market share than CB
            )

            all_result = next(r for r in results if r.ticker == "ALL")
            cb_result = next(r for r in results if r.ticker == "CB")

            # ALL should have higher impact due to larger market share
            assert all_result.mean > cb_result.mean

    @pytest.mark.asyncio
    async def test_factor_result_metadata(self, factor):
        """Test that metadata includes economic damage estimates."""
        mock_events = [
            create_mock_earthquake(
                event_id="severe_event",
                magnitude=Decimal("7.0"),
            )
        ]

        with patch.object(factor, "_get_significant_events") as mock_get_events:
            mock_get_events.return_value = mock_events

            results = await factor.compute(
                as_of_date=date.today(),
                tickers=["ALL"],
            )

            result = results[0]
            assert "total_economic_damage_usd" in result.metadata
            assert "industry_insured_loss_usd" in result.metadata
            assert "most_severe_event" in result.metadata
            assert result.metadata["most_severe_event"] == "severe_event"

    @pytest.mark.asyncio
    async def test_variance_increases_with_uncertainty(self, factor):
        """Test that variance is higher for larger, more uncertain events."""
        single_moderate = [create_mock_earthquake(magnitude=Decimal("5.5"))]
        multiple_severe = [
            create_mock_earthquake(event_id="e1", magnitude=Decimal("7.0")),
            create_mock_earthquake(event_id="e2", magnitude=Decimal("6.5")),
        ]

        with patch.object(factor, "_get_significant_events") as mock_get_events:
            # Single moderate event
            mock_get_events.return_value = single_moderate
            moderate_results = await factor.compute(
                as_of_date=date.today(),
                tickers=["ALL"],
            )

            # Multiple severe events
            mock_get_events.return_value = multiple_severe
            severe_results = await factor.compute(
                as_of_date=date.today(),
                tickers=["ALL"],
            )

            # Multiple severe events should have higher variance (more uncertainty)
            assert severe_results[0].variance > moderate_results[0].variance

    def test_get_formula_returns_latex(self, factor):
        """Test formula returns valid LaTeX string."""
        formula = factor.get_formula()

        assert isinstance(formula, str)
        assert "DisasterImpact" in formula

    def test_get_economic_rationale(self, factor):
        """Test economic rationale is provided."""
        rationale = factor.get_economic_rationale()

        assert isinstance(rationale, str)
        assert len(rationale) > 100
        assert "Catastrophe" in rationale or "loss" in rationale.lower()

    def test_primary_entities(self, factor):
        """Test primary entities match expected insurance companies."""
        assert factor.primary_entities == ["ALL", "TRV", "CB", "PGR"]


class TestInsuranceExposureConfig:
    """Tests for insurance exposure configuration."""

    def test_all_primary_entities_have_config(self):
        """Test all primary entities have exposure configuration."""
        primary_entities = ["ALL", "TRV", "CB", "PGR"]

        for ticker in primary_entities:
            assert ticker in INSURANCE_EXPOSURE_REGIONS
            config = INSURANCE_EXPOSURE_REGIONS[ticker]
            assert "name" in config
            assert "primary_regions" in config
            assert "market_share_pct" in config

    def test_market_shares_are_reasonable(self):
        """Test market shares sum to less than 100%."""
        total_share = sum(
            float(config["market_share_pct"])
            for config in INSURANCE_EXPOSURE_REGIONS.values()
        )

        # Should be reasonable portion of market (not > 50%)
        assert total_share < 0.5

    def test_population_centers_have_coordinates(self):
        """Test all population centers have valid coordinates."""
        for city, info in US_POPULATION_CENTERS.items():
            assert "lat" in info
            assert "lon" in info
            assert "population" in info
            assert -90 <= info["lat"] <= 90
            assert -180 <= info["lon"] <= 180
            assert info["population"] > 0


class TestFactorValidation:
    """Tests for factor input validation."""

    @pytest.mark.asyncio
    async def test_seismic_factor_rejects_future_date(self):
        """Test SeismicRiskExposure rejects future dates."""
        factor = SeismicRiskExposure()
        future_date = date.today() + timedelta(days=30)

        is_valid = await factor.validate_inputs(future_date)

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_disaster_factor_rejects_future_date(self):
        """Test DisasterImpactEstimate rejects future dates."""
        factor = DisasterImpactEstimate()
        future_date = date.today() + timedelta(days=30)

        is_valid = await factor.validate_inputs(future_date)

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_factor_accepts_past_date(self):
        """Test factors accept past dates."""
        seismic = SeismicRiskExposure()
        disaster = DisasterImpactEstimate()
        past_date = date.today() - timedelta(days=7)

        assert await seismic.validate_inputs(past_date) is True
        assert await disaster.validate_inputs(past_date) is True

    @pytest.mark.asyncio
    async def test_factor_accepts_today(self):
        """Test factors accept today's date."""
        seismic = SeismicRiskExposure()
        disaster = DisasterImpactEstimate()

        assert await seismic.validate_inputs(date.today()) is True
        assert await disaster.validate_inputs(date.today()) is True
