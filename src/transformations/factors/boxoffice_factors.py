"""Box office factors for entertainment company analysis."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
import statistics

from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_session
from src.entity_mapping.studio_ticker_mapping import PRIMARY_TICKERS, TICKER_TO_STUDIO
from src.models.data_sources import BoxOfficeDaily
from src.transformations.factors.base import BaseFactor, FactorResult


# Model accuracy tracking storage (in production, use database)
MODEL_ACCURACY_HISTORY: dict[str, list[dict]] = {}


class OpeningWeekendSurprise(BaseFactor):
    """Factor measuring opening weekend performance vs expectations.

    This factor captures the surprise element of a movie's opening weekend
    performance relative to market forecasts. Positive surprise indicates
    better-than-expected performance which may signal strong content and
    positive sentiment for the studio.

    The factor is computed as:
        surprise = (actual_opening - forecast) / forecast

    Since we don't have direct access to forecast data, we use a proxy
    based on theater count and historical averages as the baseline expectation.
    """

    factor_id = "opening_weekend_surprise"
    name = "Opening Weekend Surprise"
    description = "Measures opening weekend box office vs expected performance"
    domain = "entertainment"
    primary_entities = PRIMARY_TICKERS

    # Baseline per-theater average for expectations (in dollars)
    # This is calibrated based on historical industry averages
    BASELINE_PER_THEATER = Decimal("8500")

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute opening weekend surprise factor.

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers (defaults to primary entities)

        Returns:
            List of FactorResult for each ticker
        """
        if tickers is None:
            tickers = self.primary_entities

        results = []

        async with get_async_session() as session:
            # Look at opening weekends in the trailing 30 days
            lookback_start = as_of_date - timedelta(days=30)

            for ticker in tickers:
                surprise_values = await self._compute_ticker_surprise(
                    session, ticker, lookback_start, as_of_date
                )

                if surprise_values:
                    mean_surprise = sum(surprise_values) / len(surprise_values)
                    variance = self._compute_variance(surprise_values, mean_surprise)

                    results.append(FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=Decimal(str(round(mean_surprise, 6))),
                        variance=Decimal(str(round(variance, 6))),
                        data_quality=self._compute_data_quality(len(surprise_values)),
                        metadata={
                            "opening_count": len(surprise_values),
                            "lookback_days": 30,
                        }
                    ))
                else:
                    # No openings - return neutral factor
                    results.append(FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=Decimal("0"),
                        variance=Decimal("0.01"),  # Higher uncertainty
                        data_quality=Decimal("0.5"),
                        metadata={"opening_count": 0}
                    ))

        return results

    async def _compute_ticker_surprise(
        self,
        session: AsyncSession,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> list[float]:
        """Compute surprise values for a ticker's opening weekends.

        Args:
            session: Database session
            ticker: Stock ticker
            start_date: Start of lookback period
            end_date: End of lookback period

        Returns:
            List of surprise values (as decimals, e.g., 0.15 for 15%)
        """
        # Query opening weekend data for this studio
        query = select(BoxOfficeDaily).where(
            BoxOfficeDaily.distributor_ticker == ticker,
            BoxOfficeDaily.is_opening_weekend == True,
            BoxOfficeDaily.date >= start_date,
            BoxOfficeDaily.date <= end_date,
        ).order_by(BoxOfficeDaily.date)

        result = await session.execute(query)
        openings = result.scalars().all()

        surprise_values = []
        for opening in openings:
            if opening.theater_count > 0:
                # Expected gross based on theater count and baseline
                expected = self.BASELINE_PER_THEATER * opening.theater_count

                # Actual per-theater performance
                actual = opening.daily_gross

                # Surprise as percentage deviation
                if expected > 0:
                    surprise = float((actual - expected) / expected)
                    # Cap extreme values to reduce noise
                    surprise = max(min(surprise, 5.0), -0.9)
                    surprise_values.append(surprise)

        return surprise_values

    def _compute_variance(self, values: list[float], mean: float) -> float:
        """Compute variance of surprise values."""
        if len(values) < 2:
            return 0.01  # Default variance for single observation
        return sum((v - mean) ** 2 for v in values) / (len(values) - 1)

    def _compute_data_quality(self, opening_count: int) -> Decimal:
        """Compute data quality score based on observation count."""
        if opening_count >= 5:
            return Decimal("1.0")
        elif opening_count >= 3:
            return Decimal("0.9")
        elif opening_count >= 1:
            return Decimal("0.7")
        return Decimal("0.5")

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"S_t = \frac{G_{actual} - G_{expected}}{G_{expected}} = \frac{G_{actual} - (T \times \bar{g})}{T \times \bar{g}}"

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return (
            "Opening weekend box office performance is a key indicator of content quality "
            "and audience reception for entertainment companies. Positive surprises "
            "relative to expectations (based on theater count and historical averages) "
            "signal strong content that may drive recurring revenue through theatrical, "
            "streaming, and merchandise channels. Studios with consistently positive "
            "surprises demonstrate superior content development and marketing capabilities."
        )


class StudioMarketShare(BaseFactor):
    """Factor measuring studio's share of total box office market.

    This factor captures a studio's competitive position in the theatrical
    market. Higher market share indicates stronger content slate and
    competitive positioning.

    The factor is computed as:
        market_share = studio_gross / total_market_gross
    """

    factor_id = "studio_market_share"
    name = "Studio Market Share"
    description = "Measures studio's share of total box office revenue"
    domain = "entertainment"
    primary_entities = PRIMARY_TICKERS

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute studio market share factor.

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers (defaults to primary entities)

        Returns:
            List of FactorResult for each ticker
        """
        if tickers is None:
            tickers = self.primary_entities

        results = []

        async with get_async_session() as session:
            # Use trailing 30-day window for market share
            lookback_start = as_of_date - timedelta(days=30)

            # Get total market gross
            total_market = await self._get_total_market_gross(
                session, lookback_start, as_of_date
            )

            if total_market <= 0:
                # No market data - return neutral factors
                for ticker in tickers:
                    results.append(FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=Decimal("0"),
                        variance=Decimal("0.01"),
                        data_quality=Decimal("0.3"),
                        metadata={"no_market_data": True}
                    ))
                return results

            # Get studio gross and compute market share for each ticker
            for ticker in tickers:
                studio_gross = await self._get_studio_gross(
                    session, ticker, lookback_start, as_of_date
                )

                market_share = float(studio_gross / total_market) if total_market > 0 else 0.0

                # Compute rolling variance from daily shares
                daily_shares = await self._get_daily_shares(
                    session, ticker, lookback_start, as_of_date
                )
                variance = self._compute_variance(daily_shares, market_share) if daily_shares else 0.001

                results.append(FactorResult(
                    ticker=ticker,
                    factor_id=self.factor_id,
                    as_of_date=as_of_date,
                    mean=Decimal(str(round(market_share, 6))),
                    variance=Decimal(str(round(variance, 6))),
                    data_quality=self._compute_data_quality(studio_gross, total_market),
                    metadata={
                        "studio_gross": float(studio_gross),
                        "total_market": float(total_market),
                        "lookback_days": 30,
                    }
                ))

        return results

    async def _get_total_market_gross(
        self,
        session: AsyncSession,
        start_date: date,
        end_date: date,
    ) -> Decimal:
        """Get total market gross for the period."""
        query = select(func.sum(BoxOfficeDaily.daily_gross)).where(
            BoxOfficeDaily.date >= start_date,
            BoxOfficeDaily.date <= end_date,
        )
        result = await session.execute(query)
        total = result.scalar_one_or_none()
        return total or Decimal("0")

    async def _get_studio_gross(
        self,
        session: AsyncSession,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> Decimal:
        """Get studio gross for the period."""
        query = select(func.sum(BoxOfficeDaily.daily_gross)).where(
            BoxOfficeDaily.distributor_ticker == ticker,
            BoxOfficeDaily.date >= start_date,
            BoxOfficeDaily.date <= end_date,
        )
        result = await session.execute(query)
        total = result.scalar_one_or_none()
        return total or Decimal("0")

    async def _get_daily_shares(
        self,
        session: AsyncSession,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> list[float]:
        """Get daily market share values for variance computation."""
        # Get daily totals for studio
        studio_query = (
            select(
                BoxOfficeDaily.date,
                func.sum(BoxOfficeDaily.daily_gross).label("studio_gross")
            )
            .where(
                BoxOfficeDaily.distributor_ticker == ticker,
                BoxOfficeDaily.date >= start_date,
                BoxOfficeDaily.date <= end_date,
            )
            .group_by(BoxOfficeDaily.date)
        )

        # Get daily market totals
        market_query = (
            select(
                BoxOfficeDaily.date,
                func.sum(BoxOfficeDaily.daily_gross).label("market_gross")
            )
            .where(
                BoxOfficeDaily.date >= start_date,
                BoxOfficeDaily.date <= end_date,
            )
            .group_by(BoxOfficeDaily.date)
        )

        studio_result = await session.execute(studio_query)
        studio_by_date = {row.date: row.studio_gross for row in studio_result}

        market_result = await session.execute(market_query)
        market_by_date = {row.date: row.market_gross for row in market_result}

        daily_shares = []
        for dt, market_gross in market_by_date.items():
            if market_gross and market_gross > 0:
                studio_gross = studio_by_date.get(dt, Decimal("0"))
                share = float(studio_gross / market_gross)
                daily_shares.append(share)

        return daily_shares

    def _compute_variance(self, values: list[float], mean: float) -> float:
        """Compute variance of market share values."""
        if len(values) < 2:
            return 0.001
        return sum((v - mean) ** 2 for v in values) / (len(values) - 1)

    def _compute_data_quality(
        self,
        studio_gross: Decimal,
        total_market: Decimal,
    ) -> Decimal:
        """Compute data quality based on data availability."""
        if total_market <= 0:
            return Decimal("0.3")
        if studio_gross <= 0:
            return Decimal("0.5")

        # Higher quality for larger sample
        share = float(studio_gross / total_market)
        if share >= 0.05:  # At least 5% market share
            return Decimal("1.0")
        elif share >= 0.01:
            return Decimal("0.9")
        else:
            return Decimal("0.7")

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"MS_t = \frac{\sum_{i \in S} G_{i,t}}{\sum_{j \in M} G_{j,t}}"

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return (
            "Market share is a key competitive indicator for entertainment studios. "
            "Higher market share indicates stronger content slate, better marketing, "
            "and superior theatrical distribution. Studios gaining market share "
            "demonstrate improving competitive position and may benefit from "
            "operating leverage as fixed costs are spread over larger revenue base. "
            "Market share trends also signal content pipeline strength."
        )


@dataclass
class WeekendPrediction:
    """Container for weekend box office prediction."""

    movie_title: str
    distributor_ticker: str
    predicted_weekend_gross: float
    confidence_interval_low: float
    confidence_interval_high: float
    prediction_methods: dict[str, float]  # method_name -> prediction
    ensemble_weights: dict[str, float]  # method_name -> weight
    studio_guidance: Optional[float] = None
    guidance_variance_pct: Optional[float] = None


@dataclass
class ModelAccuracyMetrics:
    """Container for model accuracy tracking."""

    prediction_date: date
    movie_title: str
    distributor_ticker: str
    predicted_gross: float
    actual_gross: Optional[float]
    prediction_error_pct: Optional[float]
    method_errors: dict[str, Optional[float]] = field(default_factory=dict)


class WeekendForecastEnsemble(BaseFactor):
    """Factor providing ensemble model weekend box office forecasts.

    This factor combines multiple prediction methods to generate robust
    weekend box office forecasts:

    1. Theater Count Model: Based on historical per-theater averages
    2. Franchise Model: Adjusts based on franchise history
    3. Seasonal Model: Accounts for time-of-year patterns
    4. Thursday Preview Model: Uses Thursday night previews as signal

    The ensemble weights are dynamically adjusted based on historical accuracy.

    Economic Rationale:
        Accurate box office forecasts allow investors to anticipate studio
        quarterly performance before official earnings announcements. Studios
        with consistently outperforming content demonstrate superior IP and
        execution capabilities.
    """

    factor_id = "weekend_forecast_ensemble"
    name = "Weekend Forecast Ensemble"
    description = "Ensemble model for weekend box office predictions"
    domain = "entertainment"
    primary_entities = PRIMARY_TICKERS

    # Default ensemble weights (updated based on historical accuracy)
    DEFAULT_WEIGHTS = {
        "theater_count": 0.30,
        "historical_avg": 0.25,
        "seasonal": 0.25,
        "thursday_preview": 0.20,
    }

    # Per-theater baseline by release type
    BASELINE_PER_THEATER = {
        "wide_release": Decimal("8500"),
        "limited_release": Decimal("15000"),
        "platform_release": Decimal("25000"),
    }

    # Seasonal multipliers by month
    SEASONAL_MULTIPLIERS = {
        1: 0.85,   # January - post-holiday slump
        2: 0.90,   # February
        3: 0.95,   # March - spring break
        4: 1.00,   # April
        5: 1.20,   # May - summer kickoff
        6: 1.25,   # June - summer
        7: 1.30,   # July - summer peak
        8: 1.15,   # August
        9: 0.85,   # September - back to school
        10: 0.95,  # October - Halloween buildup
        11: 1.10,  # November - Thanksgiving
        12: 1.25,  # December - holiday season
    }

    # Thursday preview to weekend multiplier (typical 3-day/preview ratio)
    THURSDAY_PREVIEW_MULTIPLIER = 3.5

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute weekend forecast ensemble factor.

        Args:
            as_of_date: Date to compute factor for (typically Friday)
            tickers: Optional list of tickers (defaults to primary entities)

        Returns:
            List of FactorResult for each ticker with prediction metadata
        """
        if tickers is None:
            tickers = self.primary_entities

        results = []

        async with get_async_session() as session:
            # Get movies currently in theaters or opening this weekend
            opening_movies = await self._get_opening_movies(session, as_of_date)

            # Load historical accuracy to adjust weights
            weights = await self._get_adjusted_weights(session)

            for ticker in tickers:
                ticker_movies = [m for m in opening_movies if m.distributor_ticker == ticker]

                if not ticker_movies:
                    # No movies opening for this studio
                    results.append(FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=Decimal("0"),
                        variance=Decimal("0.01"),
                        data_quality=Decimal("0.5"),
                        metadata={"opening_count": 0, "has_predictions": False}
                    ))
                    continue

                # Generate ensemble predictions for each movie
                predictions = []
                total_predicted_gross = Decimal("0")

                for movie in ticker_movies:
                    prediction = await self._generate_ensemble_prediction(
                        session, movie, as_of_date, weights
                    )
                    predictions.append(prediction)
                    total_predicted_gross += Decimal(str(prediction.predicted_weekend_gross))

                # Calculate variance from confidence intervals
                total_variance = sum(
                    (p.confidence_interval_high - p.confidence_interval_low) ** 2 / 16
                    for p in predictions
                )

                results.append(FactorResult(
                    ticker=ticker,
                    factor_id=self.factor_id,
                    as_of_date=as_of_date,
                    mean=total_predicted_gross.quantize(Decimal("0.01")),
                    variance=Decimal(str(total_variance)).quantize(Decimal("0.01")),
                    data_quality=Decimal("0.85"),
                    metadata={
                        "opening_count": len(ticker_movies),
                        "has_predictions": True,
                        "predictions": [
                            {
                                "movie_title": p.movie_title,
                                "predicted_gross": p.predicted_weekend_gross,
                                "confidence_low": p.confidence_interval_low,
                                "confidence_high": p.confidence_interval_high,
                                "methods": p.prediction_methods,
                                "weights": p.ensemble_weights,
                                "studio_guidance": p.studio_guidance,
                                "guidance_variance_pct": p.guidance_variance_pct,
                            }
                            for p in predictions
                        ],
                        "ensemble_weights": weights,
                    }
                ))

        return results

    async def _get_opening_movies(
        self,
        session: AsyncSession,
        as_of_date: date,
    ) -> list[BoxOfficeDaily]:
        """Get movies opening this weekend."""
        # Look for movies with is_opening_weekend=True around the as_of_date
        weekend_start = as_of_date - timedelta(days=as_of_date.weekday())  # Monday
        weekend_end = weekend_start + timedelta(days=6)  # Sunday

        query = select(BoxOfficeDaily).where(
            BoxOfficeDaily.is_opening_weekend == True,
            BoxOfficeDaily.date >= weekend_start,
            BoxOfficeDaily.date <= weekend_end,
        ).distinct(BoxOfficeDaily.movie_title)

        result = await session.execute(query)
        return list(result.scalars().all())

    async def _generate_ensemble_prediction(
        self,
        session: AsyncSession,
        movie: BoxOfficeDaily,
        as_of_date: date,
        weights: dict[str, float],
    ) -> WeekendPrediction:
        """Generate ensemble prediction for a single movie."""

        predictions = {}

        # Method 1: Theater Count Model
        theater_pred = self._theater_count_prediction(movie)
        predictions["theater_count"] = theater_pred

        # Method 2: Historical Average Model
        hist_pred = await self._historical_avg_prediction(session, movie)
        predictions["historical_avg"] = hist_pred

        # Method 3: Seasonal Model
        seasonal_pred = self._seasonal_prediction(movie, as_of_date)
        predictions["seasonal"] = seasonal_pred

        # Method 4: Thursday Preview Model (if available)
        thursday_pred = await self._thursday_preview_prediction(session, movie, as_of_date)
        if thursday_pred:
            predictions["thursday_preview"] = thursday_pred
        else:
            # Redistribute weight if no Thursday data
            weights = weights.copy()
            if "thursday_preview" in weights:
                removed_weight = weights.pop("thursday_preview")
                total_remaining = sum(weights.values())
                if total_remaining > 0:
                    for k in weights:
                        weights[k] += removed_weight * (weights[k] / total_remaining)

        # Calculate weighted ensemble prediction
        ensemble_prediction = sum(
            predictions.get(method, 0) * weight
            for method, weight in weights.items()
            if method in predictions
        )

        # Calculate confidence interval (based on prediction spread)
        pred_values = [v for v in predictions.values() if v > 0]
        if len(pred_values) > 1:
            pred_std = statistics.stdev(pred_values)
            ci_low = max(0, ensemble_prediction - 2 * pred_std)
            ci_high = ensemble_prediction + 2 * pred_std
        else:
            ci_low = ensemble_prediction * 0.7
            ci_high = ensemble_prediction * 1.3

        # Compare to studio guidance if available
        guidance, guidance_var = await self._get_studio_guidance(session, movie)

        return WeekendPrediction(
            movie_title=movie.movie_title,
            distributor_ticker=movie.distributor_ticker or "UNKNOWN",
            predicted_weekend_gross=round(ensemble_prediction, 2),
            confidence_interval_low=round(ci_low, 2),
            confidence_interval_high=round(ci_high, 2),
            prediction_methods=predictions,
            ensemble_weights=weights,
            studio_guidance=guidance,
            guidance_variance_pct=guidance_var,
        )

    def _theater_count_prediction(self, movie: BoxOfficeDaily) -> float:
        """Predict based on theater count and per-theater baseline."""
        theater_count = movie.theater_count

        # Determine release type based on theater count
        if theater_count >= 3000:
            baseline = float(self.BASELINE_PER_THEATER["wide_release"])
        elif theater_count >= 1000:
            baseline = float(self.BASELINE_PER_THEATER["limited_release"])
        else:
            baseline = float(self.BASELINE_PER_THEATER["platform_release"])

        # Weekend is typically 3 days
        return theater_count * baseline * 3

    async def _historical_avg_prediction(
        self,
        session: AsyncSession,
        movie: BoxOfficeDaily,
    ) -> float:
        """Predict based on distributor's historical opening weekend averages."""
        # Get historical opening weekends for this distributor
        query = select(func.avg(BoxOfficeDaily.daily_gross)).where(
            BoxOfficeDaily.distributor_ticker == movie.distributor_ticker,
            BoxOfficeDaily.is_opening_weekend == True,
            BoxOfficeDaily.theater_count >= movie.theater_count * 0.8,
            BoxOfficeDaily.theater_count <= movie.theater_count * 1.2,
        )

        result = await session.execute(query)
        avg_daily = result.scalar_one_or_none()

        if avg_daily:
            return float(avg_daily) * 3  # 3-day weekend
        return self._theater_count_prediction(movie)  # Fallback

    def _seasonal_prediction(self, movie: BoxOfficeDaily, as_of_date: date) -> float:
        """Adjust theater count prediction by seasonal multiplier."""
        base_pred = self._theater_count_prediction(movie)
        month = as_of_date.month
        seasonal_mult = self.SEASONAL_MULTIPLIERS.get(month, 1.0)
        return base_pred * seasonal_mult

    async def _thursday_preview_prediction(
        self,
        session: AsyncSession,
        movie: BoxOfficeDaily,
        as_of_date: date,
    ) -> Optional[float]:
        """Predict weekend gross from Thursday preview numbers."""
        # Look for Thursday preview data (day before Friday opening)
        thursday = as_of_date - timedelta(days=1)
        if thursday.weekday() != 3:  # Not Thursday
            return None

        query = select(BoxOfficeDaily.daily_gross).where(
            BoxOfficeDaily.movie_title == movie.movie_title,
            BoxOfficeDaily.date == thursday,
        )

        result = await session.execute(query)
        thursday_gross = result.scalar_one_or_none()

        if thursday_gross:
            return float(thursday_gross) * self.THURSDAY_PREVIEW_MULTIPLIER
        return None

    async def _get_studio_guidance(
        self,
        session: AsyncSession,
        movie: BoxOfficeDaily,
    ) -> tuple[Optional[float], Optional[float]]:
        """Get studio tracking/guidance numbers for comparison.

        Returns (guidance_value, variance_from_model_pct)
        """
        # In production, this would query a studio guidance table
        # For now, return None (no guidance available)
        return None, None

    async def _get_adjusted_weights(
        self,
        session: AsyncSession,
    ) -> dict[str, float]:
        """Get ensemble weights adjusted based on historical accuracy."""
        # Check if we have enough historical accuracy data
        global MODEL_ACCURACY_HISTORY

        if not MODEL_ACCURACY_HISTORY or len(MODEL_ACCURACY_HISTORY) < 10:
            return self.DEFAULT_WEIGHTS.copy()

        # Calculate method-level accuracy
        method_errors: dict[str, list[float]] = {
            "theater_count": [],
            "historical_avg": [],
            "seasonal": [],
            "thursday_preview": [],
        }

        for movie_history in MODEL_ACCURACY_HISTORY.values():
            for record in movie_history:
                if record.get("method_errors"):
                    for method, error in record["method_errors"].items():
                        if error is not None:
                            method_errors[method].append(abs(error))

        # Calculate mean absolute error for each method
        method_mae = {}
        for method, errors in method_errors.items():
            if errors:
                method_mae[method] = statistics.mean(errors)
            else:
                method_mae[method] = 0.5  # Default 50% error if no data

        # Convert to weights (inverse of MAE, normalized)
        if all(v > 0 for v in method_mae.values()):
            total_inverse = sum(1 / v for v in method_mae.values())
            adjusted_weights = {
                method: (1 / mae) / total_inverse
                for method, mae in method_mae.items()
            }
            return adjusted_weights

        return self.DEFAULT_WEIGHTS.copy()

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"""
        P_{ensemble} = \sum_{m \in M} w_m \cdot P_m

        \text{where:}
        \begin{align}
        M &= \{\text{theater\_count}, \text{historical\_avg}, \text{seasonal}, \text{thursday\_preview}\} \\
        w_m &= \text{weight for method } m \text{ (adjusted by historical accuracy)} \\
        P_m &= \text{prediction from method } m
        \end{align}
        """

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return (
            "Weekend box office forecasts provide early signals for studio quarterly "
            "performance. This ensemble model combines multiple prediction methodologies "
            "to reduce individual model biases and improve accuracy. The theater count "
            "model captures release scale, historical averages capture distributor "
            "performance patterns, seasonal adjustments capture time-of-year effects, "
            "and Thursday preview data provides real-time demand signals. Weights are "
            "dynamically adjusted based on historical prediction accuracy."
        )


def record_prediction_accuracy(
    prediction_date: date,
    movie_title: str,
    distributor_ticker: str,
    predicted_gross: float,
    actual_gross: float,
    method_predictions: dict[str, float],
) -> ModelAccuracyMetrics:
    """Record prediction accuracy for model improvement.

    This function should be called after actual weekend results are known
    to track model accuracy over time.

    Args:
        prediction_date: Date the prediction was made
        movie_title: Title of the movie
        distributor_ticker: Stock ticker of distributor
        predicted_gross: Ensemble predicted gross
        actual_gross: Actual weekend gross
        method_predictions: Individual method predictions

    Returns:
        ModelAccuracyMetrics with computed errors
    """
    global MODEL_ACCURACY_HISTORY

    # Calculate ensemble error
    if actual_gross > 0:
        prediction_error_pct = (predicted_gross - actual_gross) / actual_gross * 100
    else:
        prediction_error_pct = None

    # Calculate individual method errors
    method_errors = {}
    for method, pred in method_predictions.items():
        if actual_gross > 0 and pred > 0:
            method_errors[method] = (pred - actual_gross) / actual_gross * 100
        else:
            method_errors[method] = None

    metrics = ModelAccuracyMetrics(
        prediction_date=prediction_date,
        movie_title=movie_title,
        distributor_ticker=distributor_ticker,
        predicted_gross=predicted_gross,
        actual_gross=actual_gross,
        prediction_error_pct=prediction_error_pct,
        method_errors=method_errors,
    )

    # Store in history
    key = f"{distributor_ticker}_{prediction_date.isoformat()}"
    if key not in MODEL_ACCURACY_HISTORY:
        MODEL_ACCURACY_HISTORY[key] = []

    MODEL_ACCURACY_HISTORY[key].append({
        "prediction_date": prediction_date.isoformat(),
        "movie_title": movie_title,
        "distributor_ticker": distributor_ticker,
        "predicted_gross": predicted_gross,
        "actual_gross": actual_gross,
        "prediction_error_pct": prediction_error_pct,
        "method_errors": method_errors,
    })

    return metrics


def get_model_accuracy_history(
    ticker: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Get historical model accuracy metrics.

    Args:
        ticker: Optional ticker to filter by
        limit: Maximum number of records to return

    Returns:
        List of accuracy records
    """
    global MODEL_ACCURACY_HISTORY

    results = []
    for key, records in MODEL_ACCURACY_HISTORY.items():
        for record in records:
            if ticker is None or record.get("distributor_ticker") == ticker:
                results.append(record)

    # Sort by date descending
    results.sort(key=lambda x: x.get("prediction_date", ""), reverse=True)

    return results[:limit]


def get_model_accuracy_summary() -> dict[str, Any]:
    """Get summary statistics of model accuracy.

    Returns:
        Dictionary with accuracy summary metrics
    """
    global MODEL_ACCURACY_HISTORY

    all_errors = []
    method_errors: dict[str, list[float]] = {
        "theater_count": [],
        "historical_avg": [],
        "seasonal": [],
        "thursday_preview": [],
    }

    for records in MODEL_ACCURACY_HISTORY.values():
        for record in records:
            if record.get("prediction_error_pct") is not None:
                all_errors.append(abs(record["prediction_error_pct"]))

            if record.get("method_errors"):
                for method, error in record["method_errors"].items():
                    if error is not None and method in method_errors:
                        method_errors[method].append(abs(error))

    if not all_errors:
        return {"total_predictions": 0, "accuracy_data_available": False}

    return {
        "total_predictions": len(all_errors),
        "accuracy_data_available": True,
        "ensemble_mae_pct": round(statistics.mean(all_errors), 2),
        "ensemble_median_error_pct": round(statistics.median(all_errors), 2),
        "ensemble_std_error_pct": round(statistics.stdev(all_errors), 2) if len(all_errors) > 1 else 0,
        "method_mae_pct": {
            method: round(statistics.mean(errors), 2) if errors else None
            for method, errors in method_errors.items()
        },
        "within_10pct_accuracy": round(sum(1 for e in all_errors if e <= 10) / len(all_errors) * 100, 1),
        "within_20pct_accuracy": round(sum(1 for e in all_errors if e <= 20) / len(all_errors) * 100, 1),
    }


# Export all factors
BOXOFFICE_FACTORS = [
    OpeningWeekendSurprise,
    StudioMarketShare,
    WeekendForecastEnsemble,
]
