"""Unit tests for TSA-based factors."""

import pytest
import pytest_asyncio
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from src.transformations.factors.tsa_factors import (
    TSAThroughputMomentum,
    TSAWeekdayWeekendRatio,
    TSAAirlineEnplanementNowcast,
    get_tsa_factors,
    TSA_PRIMARY_ENTITIES,
    AIRLINE_MARKET_SHARES,
)
from src.transformations.factors.base import FactorResult
from src.models.data_sources import TSACheckpoint


class TestTSAPrimaryEntities:
    """Tests for TSA factor configuration."""

    def test_primary_entities(self):
        """Test primary entities are defined."""
        assert "DAL" in TSA_PRIMARY_ENTITIES
        assert "UAL" in TSA_PRIMARY_ENTITIES
        assert "AAL" in TSA_PRIMARY_ENTITIES
        assert "LUV" in TSA_PRIMARY_ENTITIES
        assert "JBLU" in TSA_PRIMARY_ENTITIES
        assert "JETS" in TSA_PRIMARY_ENTITIES

    def test_market_shares_sum(self):
        """Test market shares are reasonable (excluding JETS)."""
        total = sum(v for k, v in AIRLINE_MARKET_SHARES.items() if k != "JETS")
        # Market shares should sum to less than 1 (there are other airlines)
        assert total < Decimal("1.0")
        assert total > Decimal("0.5")

    def test_get_tsa_factors(self):
        """Test factory function returns all factors."""
        factors = get_tsa_factors()

        assert len(factors) == 3
        factor_ids = {f.factor_id for f in factors}
        assert "tsa_throughput_momentum" in factor_ids
        assert "tsa_weekday_weekend_ratio" in factor_ids
        assert "tsa_enplanement_nowcast" in factor_ids


class TestTSAThroughputMomentum:
    """Tests for TSA Throughput Momentum factor."""

    @pytest.fixture
    def factor(self):
        """Create factor instance."""
        return TSAThroughputMomentum()

    def test_factor_properties(self, factor):
        """Test factor has correct properties."""
        assert factor.factor_id == "tsa_throughput_momentum"
        assert factor.name == "TSA Throughput Momentum"
        assert factor.domain == "travel"
        assert factor.LOOKBACK_DAYS == 7
        assert factor.primary_entities == TSA_PRIMARY_ENTITIES

    def test_get_formula(self, factor):
        """Test formula returns LaTeX string."""
        formula = factor.get_formula()

        assert "Momentum" in formula
        assert "frac" in formula  # LaTeX fraction

    def test_get_economic_rationale(self, factor):
        """Test economic rationale is provided."""
        rationale = factor.get_economic_rationale()

        assert len(rationale) > 100
        assert "momentum" in rationale.lower()
        assert "passenger" in rationale.lower() or "demand" in rationale.lower()

    @pytest.mark.asyncio
    async def test_compute_insufficient_data(self, factor):
        """Test compute handles insufficient data."""
        mock_result = AsyncMock()
        mock_result.fetchall = lambda: [
            (date(2024, 1, 15), 2_500_000, 2_300_000, Decimal("8.70"), Decimal("1.0")),
            (date(2024, 1, 14), 2_600_000, 2_400_000, Decimal("8.33"), Decimal("1.0")),
            # Only 2 days, need 7
        ]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch('src.transformations.factors.tsa_factors.get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await factor.compute(
                as_of_date=date(2024, 1, 15),
                tickers=["DAL"],
            )

        assert results == []

    @pytest.mark.asyncio
    async def test_compute_success(self, factor):
        """Test successful momentum computation."""
        # Generate 7 days of data
        rows = []
        for i in range(7):
            d = date(2024, 1, 15) - timedelta(days=i)
            current = 2_500_000 + i * 10_000
            prior = 2_300_000 + i * 10_000
            yoy = Decimal(str(((current - prior) / prior) * 100))
            rows.append((d, current, prior, yoy, Decimal("1.0")))

        mock_result = AsyncMock()
        mock_result.fetchall = lambda: rows

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch('src.transformations.factors.tsa_factors.get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await factor.compute(
                as_of_date=date(2024, 1, 15),
                tickers=["DAL", "JETS"],
            )

        assert len(results) == 2

        # Check results structure
        for result in results:
            assert isinstance(result, FactorResult)
            assert result.factor_id == "tsa_throughput_momentum"
            assert result.as_of_date == date(2024, 1, 15)
            assert result.data_quality == Decimal("1.0")
            assert "lookback_days" in result.metadata

        # JETS should get full momentum (market share = 1.0)
        jets_result = next(r for r in results if r.ticker == "JETS")
        dal_result = next(r for r in results if r.ticker == "DAL")

        # DAL should get weighted momentum
        assert abs(dal_result.mean) < abs(jets_result.mean)

    @pytest.mark.asyncio
    async def test_compute_default_tickers(self, factor):
        """Test compute uses primary_entities when tickers not specified."""
        # Generate 7 days of data
        rows = []
        for i in range(7):
            d = date(2024, 1, 15) - timedelta(days=i)
            rows.append((d, 2_500_000, 2_300_000, Decimal("8.70"), Decimal("1.0")))

        mock_result = AsyncMock()
        mock_result.fetchall = lambda: rows

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch('src.transformations.factors.tsa_factors.get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await factor.compute(as_of_date=date(2024, 1, 15))

        # Should compute for all primary entities
        assert len(results) == len(TSA_PRIMARY_ENTITIES)
        tickers = {r.ticker for r in results}
        assert tickers == set(TSA_PRIMARY_ENTITIES)


class TestTSAWeekdayWeekendRatio:
    """Tests for TSA Weekday/Weekend Ratio factor."""

    @pytest.fixture
    def factor(self):
        """Create factor instance."""
        return TSAWeekdayWeekendRatio()

    def test_factor_properties(self, factor):
        """Test factor has correct properties."""
        assert factor.factor_id == "tsa_weekday_weekend_ratio"
        assert factor.name == "TSA Weekday/Weekend Ratio"
        assert factor.domain == "travel"
        assert factor.LOOKBACK_WEEKS == 4

    def test_get_formula(self, factor):
        """Test formula returns LaTeX string."""
        formula = factor.get_formula()

        assert "Ratio" in formula
        assert "weekday" in formula.lower()
        assert "weekend" in formula.lower()

    def test_get_economic_rationale(self, factor):
        """Test economic rationale is provided."""
        rationale = factor.get_economic_rationale()

        assert len(rationale) > 100
        assert "business" in rationale.lower()
        assert "leisure" in rationale.lower()

    @pytest.mark.asyncio
    async def test_compute_insufficient_data(self, factor):
        """Test compute handles insufficient data."""
        mock_result = AsyncMock()
        mock_result.fetchall = lambda: [
            (0, 2_500_000, Decimal("1.0")),  # Only 1 day
        ]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch('src.transformations.factors.tsa_factors.get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await factor.compute(
                as_of_date=date(2024, 1, 15),
                tickers=["DAL"],
            )

        assert results == []

    @pytest.mark.asyncio
    async def test_compute_success(self, factor):
        """Test successful ratio computation."""
        # Generate 4 weeks of data with weekday/weekend pattern
        rows = []
        for week in range(4):
            for dow in range(7):
                # Weekdays (Mon-Fri) have higher throughput
                throughput = 2_700_000 if dow < 5 else 2_200_000
                rows.append((dow, throughput, Decimal("1.0")))

        mock_result = AsyncMock()
        mock_result.fetchall = lambda: rows

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch('src.transformations.factors.tsa_factors.get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await factor.compute(
                as_of_date=date(2024, 1, 15),
                tickers=["DAL"],
            )

        assert len(results) == 1
        result = results[0]

        # Ratio should be > 1 since weekday > weekend
        assert result.mean > Decimal("1.0")

        # Expected ratio: 2_700_000 / 2_200_000 = 1.2273
        assert abs(result.mean - Decimal("1.2273")) < Decimal("0.01")

        # Check metadata
        assert "avg_weekday_throughput" in result.metadata
        assert "avg_weekend_throughput" in result.metadata
        assert result.metadata["avg_weekday_throughput"] == 2_700_000
        assert result.metadata["avg_weekend_throughput"] == 2_200_000

    @pytest.mark.asyncio
    async def test_compute_no_weekend_data(self, factor):
        """Test compute handles missing weekend data."""
        # Only weekday data (dow 0-4)
        rows = [(dow, 2_500_000, Decimal("1.0")) for dow in range(5)]

        mock_result = AsyncMock()
        mock_result.fetchall = lambda: rows

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch('src.transformations.factors.tsa_factors.get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await factor.compute(
                as_of_date=date(2024, 1, 15),
                tickers=["DAL"],
            )

        # Should handle gracefully
        assert results == []


class TestTSAAirlineEnplanementNowcast:
    """Tests for TSA Airline Enplanement Nowcast factor."""

    @pytest.fixture
    def factor(self):
        """Create factor instance."""
        return TSAAirlineEnplanementNowcast()

    def test_factor_properties(self, factor):
        """Test factor has correct properties."""
        assert factor.factor_id == "tsa_enplanement_nowcast"
        assert factor.name == "TSA Airline Enplanement Nowcast"
        assert factor.domain == "travel"
        assert factor.TSA_TO_ENPLANEMENT_FACTOR == Decimal("0.98")

    def test_get_formula(self, factor):
        """Test formula returns LaTeX string."""
        formula = factor.get_formula()

        assert "Enplanement" in formula
        assert "0.98" in formula

    def test_get_economic_rationale(self, factor):
        """Test economic rationale is provided."""
        rationale = factor.get_economic_rationale()

        assert len(rationale) > 100
        assert "nowcast" in rationale.lower()
        assert "enplanement" in rationale.lower()

    @pytest.mark.asyncio
    async def test_compute_no_data(self, factor):
        """Test compute handles no data."""
        mock_current = AsyncMock()
        mock_current.fetchone = lambda: (None, None, 0, None)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_current)

        with patch('src.transformations.factors.tsa_factors.get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await factor.compute(
                as_of_date=date(2024, 1, 15),
                tickers=["DAL"],
            )

        assert results == []

    @pytest.mark.asyncio
    async def test_compute_success(self, factor):
        """Test successful enplanement nowcast computation."""
        # Mid-month data (15 days)
        mtd_throughput = 37_500_000  # 15 days * 2.5M avg
        avg_daily = 2_500_000
        days_reported = 15
        quality = Decimal("1.0")

        mock_current = AsyncMock()
        mock_current.fetchone = lambda: (mtd_throughput, avg_daily, days_reported, quality)

        mock_prior = AsyncMock()
        mock_prior.fetchone = lambda: (35_000_000, 15)  # Prior year MTD

        call_count = [0]

        async def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_current
            return mock_prior

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        with patch('src.transformations.factors.tsa_factors.get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await factor.compute(
                as_of_date=date(2024, 1, 15),
                tickers=["DAL", "JETS"],
            )

        assert len(results) == 2

        # Check JETS result (market share = 1.0)
        jets_result = next(r for r in results if r.ticker == "JETS")

        # Projected full month: 2.5M * 31 * 0.98 / 1M = 75.95 million
        expected_enplanement = Decimal("2.5") * 31 * Decimal("0.98")
        assert abs(jets_result.mean - expected_enplanement) < Decimal("1.0")

        # Check metadata
        assert jets_result.metadata["days_reported"] == 15
        assert jets_result.metadata["days_in_month"] == 31
        assert jets_result.metadata["completion_pct"] > 40

        # Check DAL result (market share weighted)
        dal_result = next(r for r in results if r.ticker == "DAL")
        assert dal_result.mean < jets_result.mean
        assert dal_result.metadata["market_share"] == float(AIRLINE_MARKET_SHARES["DAL"])

    @pytest.mark.asyncio
    async def test_compute_revision_status(self, factor):
        """Test revision status based on month completion."""
        # Full month data (31 days in January)
        mtd_throughput = 77_500_000  # 31 days * 2.5M avg
        avg_daily = 2_500_000
        days_reported = 31
        quality = Decimal("1.0")

        mock_current = AsyncMock()
        mock_current.fetchone = lambda: (mtd_throughput, avg_daily, days_reported, quality)

        mock_prior = AsyncMock()
        mock_prior.fetchone = lambda: (70_000_000, 31)

        call_count = [0]

        async def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_current
            return mock_prior

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        with patch('src.transformations.factors.tsa_factors.get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await factor.compute(
                as_of_date=date(2024, 1, 31),  # Last day of month
                tickers=["DAL"],
            )

        assert len(results) == 1
        assert results[0].revision_status == "final"

    @pytest.mark.asyncio
    async def test_compute_preliminary_status(self, factor):
        """Test preliminary status for incomplete month."""
        # Partial month data
        mtd_throughput = 25_000_000  # 10 days
        avg_daily = 2_500_000
        days_reported = 10
        quality = Decimal("1.0")

        mock_current = AsyncMock()
        mock_current.fetchone = lambda: (mtd_throughput, avg_daily, days_reported, quality)

        mock_prior = AsyncMock()
        mock_prior.fetchone = lambda: (23_000_000, 10)

        call_count = [0]

        async def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_current
            return mock_prior

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        with patch('src.transformations.factors.tsa_factors.get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await factor.compute(
                as_of_date=date(2024, 1, 10),
                tickers=["DAL"],
            )

        assert len(results) == 1
        assert results[0].revision_status == "preliminary"


class TestFactorValidation:
    """Tests for factor input validation."""

    @pytest.fixture
    def momentum_factor(self):
        """Create momentum factor instance."""
        return TSAThroughputMomentum()

    @pytest.mark.asyncio
    async def test_validate_future_date(self, momentum_factor):
        """Test validation rejects future dates."""
        future_date = date.today() + timedelta(days=1)

        is_valid = await momentum_factor.validate_inputs(
            as_of_date=future_date,
            tickers=["DAL"],
        )

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_past_date(self, momentum_factor):
        """Test validation accepts past dates."""
        past_date = date.today() - timedelta(days=1)

        is_valid = await momentum_factor.validate_inputs(
            as_of_date=past_date,
            tickers=["DAL"],
        )

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_compute_with_logging(self, momentum_factor):
        """Test compute_with_logging works correctly."""
        # Generate 7 days of data
        rows = []
        for i in range(7):
            d = date(2024, 1, 15) - timedelta(days=i)
            rows.append((d, 2_500_000, 2_300_000, Decimal("8.70"), Decimal("1.0")))

        mock_result = AsyncMock()
        mock_result.fetchall = lambda: rows

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch('src.transformations.factors.tsa_factors.get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await momentum_factor.compute_with_logging(
                as_of_date=date(2024, 1, 15),
                tickers=["DAL"],
            )

        assert len(results) == 1


class TestFactorCalculationAccuracy:
    """Tests for factor calculation accuracy."""

    @pytest.mark.asyncio
    async def test_momentum_calculation_accuracy(self):
        """Test momentum calculation is mathematically correct."""
        factor = TSAThroughputMomentum()

        # Fixed data for accurate calculation
        # Current avg: 2,600,000, Prior avg: 2,400,000
        # Momentum = (2600000 - 2400000) / 2400000 * 100 = 8.3333%
        rows = [
            (date(2024, 1, i), 2_600_000, 2_400_000, Decimal("8.3333"), Decimal("1.0"))
            for i in range(15, 8, -1)  # 7 days
        ]

        mock_result = AsyncMock()
        mock_result.fetchall = lambda: rows

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch('src.transformations.factors.tsa_factors.get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await factor.compute(
                as_of_date=date(2024, 1, 15),
                tickers=["JETS"],
            )

        assert len(results) == 1

        # JETS gets full momentum (market share = 1.0)
        expected_momentum = Decimal("8.3333")
        assert abs(results[0].mean - expected_momentum) < Decimal("0.01")

    @pytest.mark.asyncio
    async def test_weekday_weekend_ratio_accuracy(self):
        """Test weekday/weekend ratio calculation is mathematically correct."""
        factor = TSAWeekdayWeekendRatio()

        # Weekday avg: 3,000,000, Weekend avg: 2,000,000
        # Ratio = 3000000 / 2000000 = 1.5
        rows = []
        for week in range(4):
            for dow in range(7):
                throughput = 3_000_000 if dow < 5 else 2_000_000
                rows.append((dow, throughput, Decimal("1.0")))

        mock_result = AsyncMock()
        mock_result.fetchall = lambda: rows

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch('src.transformations.factors.tsa_factors.get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await factor.compute(
                as_of_date=date(2024, 1, 15),
                tickers=["DAL"],
            )

        assert len(results) == 1

        expected_ratio = Decimal("1.5")
        assert abs(results[0].mean - expected_ratio) < Decimal("0.01")
