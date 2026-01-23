"""Tests for internet and cybersecurity factors."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.transformations.factors.internet_factors import (
    TrafficAnomalyIndex,
    SecurityThreatLevel,
)
from src.transformations.factors.base import FactorResult
from src.models.data_sources import CloudflareRadarMetrics


@pytest.fixture
def traffic_anomaly_factor():
    """Create TrafficAnomalyIndex instance."""
    return TrafficAnomalyIndex()


@pytest.fixture
def security_threat_factor():
    """Create SecurityThreatLevel instance."""
    return SecurityThreatLevel()


@pytest.fixture
def sample_traffic_data():
    """Sample traffic deviation data for testing."""
    return [
        (Decimal("15.5"), Decimal("1150000"), Decimal("1000000")),
        (Decimal("12.3"), Decimal("1123000"), Decimal("1000000")),
        (Decimal("18.7"), Decimal("1187000"), Decimal("1000000")),
        (Decimal("10.2"), Decimal("1102000"), Decimal("1000000")),
        (Decimal("14.8"), Decimal("1148000"), Decimal("1000000")),
        (Decimal("16.1"), Decimal("1161000"), Decimal("1000000")),
        (Decimal("11.5"), Decimal("1115000"), Decimal("1000000")),
        (Decimal("13.9"), Decimal("1139000"), Decimal("1000000")),
        (Decimal("17.2"), Decimal("1172000"), Decimal("1000000")),
        (Decimal("9.8"), Decimal("1098000"), Decimal("1000000")),
        (Decimal("15.0"), Decimal("1150000"), Decimal("1000000")),
        (Decimal("14.5"), Decimal("1145000"), Decimal("1000000")),
    ]


@pytest.fixture
def sample_attack_data():
    """Sample attack deviation data for testing."""
    return [
        (Decimal("45.0"), Decimal("7250"), Decimal("5000")),
        (Decimal("52.0"), Decimal("7600"), Decimal("5000")),
        (Decimal("38.0"), Decimal("6900"), Decimal("5000")),
        (Decimal("61.0"), Decimal("8050"), Decimal("5000")),
        (Decimal("55.0"), Decimal("7750"), Decimal("5000")),
        (Decimal("42.0"), Decimal("7100"), Decimal("5000")),
        (Decimal("48.0"), Decimal("7400"), Decimal("5000")),
        (Decimal("58.0"), Decimal("7900"), Decimal("5000")),
        (Decimal("35.0"), Decimal("6750"), Decimal("5000")),
        (Decimal("50.0"), Decimal("7500"), Decimal("5000")),
        (Decimal("44.0"), Decimal("7200"), Decimal("5000")),
        (Decimal("47.0"), Decimal("7350"), Decimal("5000")),
    ]


class TestTrafficAnomalyIndex:
    """Tests for TrafficAnomalyIndex factor."""

    def test_factor_attributes(self, traffic_anomaly_factor):
        """Test factor has correct attributes."""
        assert traffic_anomaly_factor.factor_id == "traffic_anomaly_index"
        assert traffic_anomaly_factor.name == "Traffic Anomaly Index"
        assert traffic_anomaly_factor.domain == "internet"
        assert traffic_anomaly_factor.primary_entities == ["NET", "CRWD", "PANW", "ZS"]

    def test_lookback_configuration(self, traffic_anomaly_factor):
        """Test lookback period is 24 hours."""
        assert traffic_anomaly_factor.LOOKBACK_HOURS == 24
        assert traffic_anomaly_factor.MIN_DATA_POINTS == 12

    def test_ticker_sensitivity_values(self, traffic_anomaly_factor):
        """Test ticker sensitivity multipliers."""
        assert traffic_anomaly_factor._get_ticker_sensitivity("NET") == Decimal("1.2")
        assert traffic_anomaly_factor._get_ticker_sensitivity("CRWD") == Decimal("0.9")
        assert traffic_anomaly_factor._get_ticker_sensitivity("PANW") == Decimal("0.8")
        assert traffic_anomaly_factor._get_ticker_sensitivity("ZS") == Decimal("0.85")
        assert traffic_anomaly_factor._get_ticker_sensitivity("UNKNOWN") == Decimal("1.0")

    @pytest.mark.asyncio
    async def test_compute_returns_results_for_all_tickers(
        self, traffic_anomaly_factor, sample_traffic_data
    ):
        """Test compute returns results for all primary entities."""
        with patch(
            "src.transformations.factors.internet_factors.get_async_session"
        ) as mock_session:
            mock_session_instance = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = sample_traffic_data
            mock_session_instance.execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await traffic_anomaly_factor.compute(
                as_of_date=date(2024, 1, 15)
            )

            assert len(results) == 4
            tickers = {r.ticker for r in results}
            assert tickers == {"NET", "CRWD", "PANW", "ZS"}

    @pytest.mark.asyncio
    async def test_compute_calculates_valid_deviation_percentages(
        self, traffic_anomaly_factor, sample_traffic_data
    ):
        """Test computed deviations are valid percentages."""
        with patch(
            "src.transformations.factors.internet_factors.get_async_session"
        ) as mock_session:
            mock_session_instance = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = sample_traffic_data
            mock_session_instance.execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await traffic_anomaly_factor.compute(
                as_of_date=date(2024, 1, 15)
            )

            for result in results:
                # Mean should be a reasonable percentage deviation
                assert result.mean >= Decimal("-100")
                assert result.mean <= Decimal("1000")
                # Variance should be non-negative
                assert result.variance >= Decimal("0")

    @pytest.mark.asyncio
    async def test_compute_with_insufficient_data(self, traffic_anomaly_factor):
        """Test compute handles insufficient data gracefully."""
        # Only 5 data points (less than minimum 12)
        insufficient_data = [
            (Decimal("10.0"), Decimal("1100000"), Decimal("1000000")),
            (Decimal("15.0"), Decimal("1150000"), Decimal("1000000")),
            (Decimal("12.0"), Decimal("1120000"), Decimal("1000000")),
            (Decimal("8.0"), Decimal("1080000"), Decimal("1000000")),
            (Decimal("11.0"), Decimal("1110000"), Decimal("1000000")),
        ]

        with patch(
            "src.transformations.factors.internet_factors.get_async_session"
        ) as mock_session:
            mock_session_instance = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = insufficient_data
            mock_session_instance.execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await traffic_anomaly_factor.compute(
                as_of_date=date(2024, 1, 15)
            )

            # Should still return results but with low quality score
            assert len(results) == 4
            for result in results:
                assert result.data_quality == Decimal("0.1")
                assert result.revision_status == "insufficient_data"

    @pytest.mark.asyncio
    async def test_compute_applies_ticker_sensitivity(
        self, traffic_anomaly_factor, sample_traffic_data
    ):
        """Test that ticker sensitivity is applied to mean values."""
        with patch(
            "src.transformations.factors.internet_factors.get_async_session"
        ) as mock_session:
            mock_session_instance = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = sample_traffic_data
            mock_session_instance.execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await traffic_anomaly_factor.compute(
                as_of_date=date(2024, 1, 15)
            )

            # NET should have highest adjusted mean (1.2x)
            # PANW should have lowest adjusted mean (0.8x)
            net_result = next(r for r in results if r.ticker == "NET")
            panw_result = next(r for r in results if r.ticker == "PANW")

            # NET sensitivity (1.2) / PANW sensitivity (0.8) = 1.5
            ratio = net_result.mean / panw_result.mean
            assert abs(ratio - Decimal("1.5")) < Decimal("0.01")

    @pytest.mark.asyncio
    async def test_compute_for_specific_tickers(
        self, traffic_anomaly_factor, sample_traffic_data
    ):
        """Test computing for specific tickers only."""
        with patch(
            "src.transformations.factors.internet_factors.get_async_session"
        ) as mock_session:
            mock_session_instance = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = sample_traffic_data
            mock_session_instance.execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await traffic_anomaly_factor.compute(
                as_of_date=date(2024, 1, 15),
                tickers=["NET", "CRWD"],
            )

            assert len(results) == 2
            tickers = {r.ticker for r in results}
            assert tickers == {"NET", "CRWD"}

    def test_get_formula_returns_latex(self, traffic_anomaly_factor):
        """Test formula returns valid LaTeX."""
        formula = traffic_anomaly_factor.get_formula()
        assert "TrafficAnomalyIndex" in formula
        assert "V_i" in formula
        assert "B_i" in formula
        assert "S_{\\text{ticker}}" in formula

    def test_get_economic_rationale_is_comprehensive(self, traffic_anomaly_factor):
        """Test economic rationale covers key points."""
        rationale = traffic_anomaly_factor.get_economic_rationale()
        assert "Cloudflare" in rationale
        assert "CrowdStrike" in rationale
        assert "Palo Alto" in rationale
        assert "Zscaler" in rationale


class TestSecurityThreatLevel:
    """Tests for SecurityThreatLevel factor."""

    def test_factor_attributes(self, security_threat_factor):
        """Test factor has correct attributes."""
        assert security_threat_factor.factor_id == "security_threat_level"
        assert security_threat_factor.name == "Security Threat Level"
        assert security_threat_factor.domain == "internet"
        assert security_threat_factor.primary_entities == ["NET", "CRWD", "PANW", "ZS"]

    def test_threat_thresholds(self, security_threat_factor):
        """Test threat level thresholds are properly defined."""
        thresholds = security_threat_factor.THREAT_THRESHOLDS
        assert thresholds["low"] == Decimal("-20")
        assert thresholds["normal"] == Decimal("0")
        assert thresholds["elevated"] == Decimal("25")
        assert thresholds["high"] == Decimal("50")
        assert thresholds["critical"] == Decimal("100")

    def test_categorize_threat_level_critical(self, security_threat_factor):
        """Test critical threat level categorization."""
        assert security_threat_factor._categorize_threat_level(Decimal("150")) == "critical"
        assert security_threat_factor._categorize_threat_level(Decimal("100")) == "critical"

    def test_categorize_threat_level_high(self, security_threat_factor):
        """Test high threat level categorization."""
        assert security_threat_factor._categorize_threat_level(Decimal("75")) == "high"
        assert security_threat_factor._categorize_threat_level(Decimal("50")) == "high"

    def test_categorize_threat_level_elevated(self, security_threat_factor):
        """Test elevated threat level categorization."""
        assert security_threat_factor._categorize_threat_level(Decimal("35")) == "elevated"
        assert security_threat_factor._categorize_threat_level(Decimal("25")) == "elevated"

    def test_categorize_threat_level_normal(self, security_threat_factor):
        """Test normal threat level categorization."""
        assert security_threat_factor._categorize_threat_level(Decimal("10")) == "normal"
        assert security_threat_factor._categorize_threat_level(Decimal("0")) == "normal"

    def test_categorize_threat_level_low(self, security_threat_factor):
        """Test low threat level categorization."""
        assert security_threat_factor._categorize_threat_level(Decimal("-10")) == "low"
        assert security_threat_factor._categorize_threat_level(Decimal("-50")) == "low"

    def test_ticker_threat_multipliers(self, security_threat_factor):
        """Test ticker-specific threat multipliers."""
        assert security_threat_factor._get_ticker_threat_multiplier("CRWD") == Decimal("1.3")
        assert security_threat_factor._get_ticker_threat_multiplier("NET") == Decimal("1.2")
        assert security_threat_factor._get_ticker_threat_multiplier("ZS") == Decimal("1.1")
        assert security_threat_factor._get_ticker_threat_multiplier("PANW") == Decimal("1.0")
        assert security_threat_factor._get_ticker_threat_multiplier("UNKNOWN") == Decimal("1.0")

    @pytest.mark.asyncio
    async def test_compute_returns_results_for_all_tickers(
        self, security_threat_factor, sample_attack_data
    ):
        """Test compute returns results for all primary entities."""
        with patch(
            "src.transformations.factors.internet_factors.get_async_session"
        ) as mock_session:
            mock_session_instance = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = sample_attack_data
            mock_session_instance.execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await security_threat_factor.compute(
                as_of_date=date(2024, 1, 15)
            )

            assert len(results) == 4
            tickers = {r.ticker for r in results}
            assert tickers == {"NET", "CRWD", "PANW", "ZS"}

    @pytest.mark.asyncio
    async def test_compute_includes_threat_level_metadata(
        self, security_threat_factor, sample_attack_data
    ):
        """Test compute includes threat level in metadata."""
        with patch(
            "src.transformations.factors.internet_factors.get_async_session"
        ) as mock_session:
            mock_session_instance = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = sample_attack_data
            mock_session_instance.execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await security_threat_factor.compute(
                as_of_date=date(2024, 1, 15)
            )

            for result in results:
                assert "threat_level" in result.metadata
                assert result.metadata["threat_level"] in [
                    "low", "normal", "elevated", "high", "critical"
                ]

    @pytest.mark.asyncio
    async def test_compute_high_threat_categorization(self, security_threat_factor):
        """Test that high attack deviations result in high threat level."""
        # All deviations > 50%
        high_attack_data = [
            (Decimal("60.0"), Decimal("8000"), Decimal("5000")),
            (Decimal("55.0"), Decimal("7750"), Decimal("5000")),
            (Decimal("70.0"), Decimal("8500"), Decimal("5000")),
            (Decimal("65.0"), Decimal("8250"), Decimal("5000")),
            (Decimal("58.0"), Decimal("7900"), Decimal("5000")),
            (Decimal("62.0"), Decimal("8100"), Decimal("5000")),
            (Decimal("75.0"), Decimal("8750"), Decimal("5000")),
            (Decimal("68.0"), Decimal("8400"), Decimal("5000")),
            (Decimal("72.0"), Decimal("8600"), Decimal("5000")),
            (Decimal("66.0"), Decimal("8300"), Decimal("5000")),
            (Decimal("59.0"), Decimal("7950"), Decimal("5000")),
            (Decimal("63.0"), Decimal("8150"), Decimal("5000")),
        ]

        with patch(
            "src.transformations.factors.internet_factors.get_async_session"
        ) as mock_session:
            mock_session_instance = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = high_attack_data
            mock_session_instance.execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await security_threat_factor.compute(
                as_of_date=date(2024, 1, 15)
            )

            for result in results:
                assert result.metadata["threat_level"] in ["high", "critical"]

    @pytest.mark.asyncio
    async def test_compute_with_insufficient_data(self, security_threat_factor):
        """Test compute handles insufficient data gracefully."""
        insufficient_data = [
            (Decimal("45.0"), Decimal("7250"), Decimal("5000")),
            (Decimal("52.0"), Decimal("7600"), Decimal("5000")),
        ]

        with patch(
            "src.transformations.factors.internet_factors.get_async_session"
        ) as mock_session:
            mock_session_instance = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = insufficient_data
            mock_session_instance.execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await security_threat_factor.compute(
                as_of_date=date(2024, 1, 15)
            )

            assert len(results) == 4
            for result in results:
                assert result.data_quality == Decimal("0.1")
                assert result.revision_status == "insufficient_data"
                assert result.metadata["threat_level"] == "unknown"

    @pytest.mark.asyncio
    async def test_compute_applies_ticker_multiplier(
        self, security_threat_factor, sample_attack_data
    ):
        """Test that ticker multipliers are applied correctly."""
        with patch(
            "src.transformations.factors.internet_factors.get_async_session"
        ) as mock_session:
            mock_session_instance = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = sample_attack_data
            mock_session_instance.execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await security_threat_factor.compute(
                as_of_date=date(2024, 1, 15)
            )

            # CRWD should have highest adjusted mean (1.3x)
            # PANW should have lowest adjusted mean (1.0x)
            crwd_result = next(r for r in results if r.ticker == "CRWD")
            panw_result = next(r for r in results if r.ticker == "PANW")

            # CRWD multiplier (1.3) / PANW multiplier (1.0) = 1.3
            ratio = crwd_result.mean / panw_result.mean
            assert abs(ratio - Decimal("1.3")) < Decimal("0.01")

    def test_get_formula_returns_latex(self, security_threat_factor):
        """Test formula returns valid LaTeX."""
        formula = security_threat_factor.get_formula()
        assert "SecurityThreatLevel" in formula
        assert "A_i" in formula
        assert "M_{\\text{ticker}}" in formula
        assert "Critical" in formula

    def test_get_economic_rationale_is_comprehensive(self, security_threat_factor):
        """Test economic rationale covers key points."""
        rationale = security_threat_factor.get_economic_rationale()
        assert "DDoS" in rationale
        assert "demand" in rationale.lower()
        assert "Falcon" in rationale  # CrowdStrike product


class TestFactorResultValidation:
    """Tests for FactorResult validation."""

    @pytest.mark.asyncio
    async def test_factor_result_structure(
        self, traffic_anomaly_factor, sample_traffic_data
    ):
        """Test FactorResult has all required fields."""
        with patch(
            "src.transformations.factors.internet_factors.get_async_session"
        ) as mock_session:
            mock_session_instance = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = sample_traffic_data
            mock_session_instance.execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await traffic_anomaly_factor.compute(
                as_of_date=date(2024, 1, 15)
            )

            for result in results:
                assert hasattr(result, "ticker")
                assert hasattr(result, "factor_id")
                assert hasattr(result, "as_of_date")
                assert hasattr(result, "mean")
                assert hasattr(result, "variance")
                assert hasattr(result, "data_quality")
                assert hasattr(result, "revision_status")
                assert hasattr(result, "metadata")

    @pytest.mark.asyncio
    async def test_data_quality_calculation(
        self, traffic_anomaly_factor, sample_traffic_data
    ):
        """Test data quality is based on coverage."""
        with patch(
            "src.transformations.factors.internet_factors.get_async_session"
        ) as mock_session:
            mock_session_instance = AsyncMock()
            mock_result = MagicMock()
            # 12 data points for 24-hour lookback = 50% coverage
            mock_result.fetchall.return_value = sample_traffic_data[:12]
            mock_session_instance.execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await traffic_anomaly_factor.compute(
                as_of_date=date(2024, 1, 15)
            )

            for result in results:
                # 12 points / 24 expected = 0.5
                assert result.data_quality == Decimal("0.5")


class TestAnomalyDetectionAccuracy:
    """Tests for anomaly detection accuracy."""

    @pytest.mark.asyncio
    async def test_detects_positive_anomaly(self, traffic_anomaly_factor):
        """Test detection of significant positive deviation."""
        # All deviations strongly positive (around 50%)
        positive_anomaly_data = [
            (Decimal("50.0"), Decimal("1500000"), Decimal("1000000")),
        ] * 24

        with patch(
            "src.transformations.factors.internet_factors.get_async_session"
        ) as mock_session:
            mock_session_instance = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = positive_anomaly_data
            mock_session_instance.execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await traffic_anomaly_factor.compute(
                as_of_date=date(2024, 1, 15)
            )

            for result in results:
                # All tickers should show positive mean (adjusted by sensitivity)
                assert result.mean > Decimal("0")

    @pytest.mark.asyncio
    async def test_detects_negative_anomaly(self, traffic_anomaly_factor):
        """Test detection of significant negative deviation."""
        # All deviations strongly negative (around -30%)
        negative_anomaly_data = [
            (Decimal("-30.0"), Decimal("700000"), Decimal("1000000")),
        ] * 24

        with patch(
            "src.transformations.factors.internet_factors.get_async_session"
        ) as mock_session:
            mock_session_instance = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = negative_anomaly_data
            mock_session_instance.execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await traffic_anomaly_factor.compute(
                as_of_date=date(2024, 1, 15)
            )

            for result in results:
                # All tickers should show negative mean
                assert result.mean < Decimal("0")

    @pytest.mark.asyncio
    async def test_variance_reflects_volatility(self, traffic_anomaly_factor):
        """Test that variance captures volatility in deviations."""
        # High volatility data (wide range of deviations)
        volatile_data = [
            (Decimal("-40.0"), Decimal("600000"), Decimal("1000000")),
            (Decimal("60.0"), Decimal("1600000"), Decimal("1000000")),
            (Decimal("-30.0"), Decimal("700000"), Decimal("1000000")),
            (Decimal("50.0"), Decimal("1500000"), Decimal("1000000")),
            (Decimal("-20.0"), Decimal("800000"), Decimal("1000000")),
            (Decimal("40.0"), Decimal("1400000"), Decimal("1000000")),
        ] * 4  # 24 points

        # Low volatility data (narrow range of deviations)
        stable_data = [
            (Decimal("5.0"), Decimal("1050000"), Decimal("1000000")),
            (Decimal("7.0"), Decimal("1070000"), Decimal("1000000")),
            (Decimal("4.0"), Decimal("1040000"), Decimal("1000000")),
            (Decimal("6.0"), Decimal("1060000"), Decimal("1000000")),
        ] * 6  # 24 points

        with patch(
            "src.transformations.factors.internet_factors.get_async_session"
        ) as mock_session:
            mock_session_instance = AsyncMock()

            # Test volatile data
            mock_result_volatile = MagicMock()
            mock_result_volatile.fetchall.return_value = volatile_data
            mock_session_instance.execute = AsyncMock(return_value=mock_result_volatile)
            mock_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            volatile_results = await traffic_anomaly_factor.compute(
                as_of_date=date(2024, 1, 15)
            )
            volatile_variance = volatile_results[0].variance

            # Test stable data
            mock_result_stable = MagicMock()
            mock_result_stable.fetchall.return_value = stable_data
            mock_session_instance.execute = AsyncMock(return_value=mock_result_stable)

            stable_results = await traffic_anomaly_factor.compute(
                as_of_date=date(2024, 1, 15)
            )
            stable_variance = stable_results[0].variance

            # Volatile data should have much higher variance
            assert volatile_variance > stable_variance * 10
