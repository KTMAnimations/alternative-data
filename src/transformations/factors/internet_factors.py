"""Internet and cybersecurity factors derived from Cloudflare Radar data."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select

from src.core.database import get_async_session
from src.models.data_sources import CloudflareRadarMetrics
from src.transformations.factors.base import BaseFactor, FactorResult


class TrafficAnomalyIndex(BaseFactor):
    """Traffic Anomaly Index factor measuring deviation from baseline internet traffic.

    This factor captures unusual patterns in global internet traffic that may indicate:
    - Significant geopolitical events
    - Infrastructure changes
    - Mass behavioral shifts
    - Regional outages with global implications

    Higher values indicate traffic significantly above baseline (bullish for NET).
    Lower values indicate traffic below baseline (potential infrastructure issues).
    """

    factor_id = "traffic_anomaly_index"
    name = "Traffic Anomaly Index"
    description = (
        "Measures deviation of internet traffic from rolling baseline. "
        "Positive values indicate traffic above normal levels."
    )
    domain = "internet"
    primary_entities = ["NET", "CRWD", "PANW", "ZS"]

    # Configuration
    LOOKBACK_HOURS = 24  # Hours of data to aggregate
    BASELINE_WINDOW_DAYS = 7  # Days for baseline calculation
    MIN_DATA_POINTS = 12  # Minimum hourly data points required

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute Traffic Anomaly Index for cybersecurity entities.

        The factor aggregates hourly traffic deviation data and computes:
        - Mean deviation from baseline over the lookback period
        - Variance to capture stability of the deviation

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers (if None, uses primary_entities)

        Returns:
            List of FactorResult objects, one per ticker
        """
        target_tickers = tickers or self.primary_entities
        results = []

        async with get_async_session() as session:
            # Define time window
            end_time = datetime.combine(as_of_date, datetime.max.time()).replace(
                tzinfo=timezone.utc
            )
            start_time = end_time - timedelta(hours=self.LOOKBACK_HOURS)

            # Query traffic deviation data
            stmt = select(
                CloudflareRadarMetrics.deviation_pct,
                CloudflareRadarMetrics.value,
                CloudflareRadarMetrics.baseline_value,
            ).where(
                CloudflareRadarMetrics.metric_type == "traffic",
                CloudflareRadarMetrics.timestamp >= start_time,
                CloudflareRadarMetrics.timestamp <= end_time,
            )

            result = await session.execute(stmt)
            rows = result.fetchall()

            if len(rows) < self.MIN_DATA_POINTS:
                self.logger.warning(
                    "Insufficient data points",
                    required=self.MIN_DATA_POINTS,
                    available=len(rows),
                )
                # Return results with low quality score
                for ticker in target_tickers:
                    results.append(
                        FactorResult(
                            ticker=ticker,
                            factor_id=self.factor_id,
                            as_of_date=as_of_date,
                            mean=Decimal("0"),
                            variance=Decimal("0"),
                            data_quality=Decimal("0.1"),
                            revision_status="insufficient_data",
                            metadata={
                                "data_points": len(rows),
                                "lookback_hours": self.LOOKBACK_HOURS,
                            },
                        )
                    )
                return results

            # Calculate aggregate metrics
            deviations = [
                row[0] for row in rows if row[0] is not None
            ]

            if not deviations:
                self.logger.warning("No valid deviation values found")
                return results

            # Compute mean and variance
            mean_deviation = Decimal(str(sum(deviations) / len(deviations)))
            variance = Decimal(
                str(
                    sum((d - mean_deviation) ** 2 for d in deviations)
                    / len(deviations)
                )
            )

            # Calculate data quality based on coverage
            expected_points = self.LOOKBACK_HOURS
            coverage = min(len(rows) / expected_points, Decimal("1.0"))
            data_quality = Decimal(str(coverage))

            # Create results for each ticker
            # All cybersecurity companies are affected similarly by traffic anomalies
            for ticker in target_tickers:
                # Adjust factor based on ticker-specific sensitivity
                ticker_adjustment = self._get_ticker_sensitivity(ticker)
                adjusted_mean = mean_deviation * ticker_adjustment

                results.append(
                    FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=adjusted_mean,
                        variance=variance,
                        data_quality=data_quality,
                        revision_status="original",
                        metadata={
                            "data_points": len(rows),
                            "lookback_hours": self.LOOKBACK_HOURS,
                            "raw_mean_deviation": float(mean_deviation),
                            "ticker_sensitivity": float(ticker_adjustment),
                        },
                    )
                )

        return results

    def _get_ticker_sensitivity(self, ticker: str) -> Decimal:
        """Get ticker-specific sensitivity to traffic anomalies.

        Different companies have varying exposure to internet traffic trends.
        """
        sensitivities = {
            "NET": Decimal("1.2"),   # Cloudflare - most sensitive to traffic
            "CRWD": Decimal("0.9"),  # CrowdStrike - security-focused
            "PANW": Decimal("0.8"),  # Palo Alto - enterprise security
            "ZS": Decimal("0.85"),   # Zscaler - cloud security
        }
        return sensitivities.get(ticker, Decimal("1.0"))

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"""
        \text{TrafficAnomalyIndex}_{t} = \frac{1}{N} \sum_{i=1}^{N}
        \left( \frac{V_i - B_i}{B_i} \times 100 \right) \times S_{\text{ticker}}

        \text{where:}
        \begin{align}
        V_i &= \text{actual traffic value at hour } i \\
        B_i &= \text{7-day rolling baseline at hour } i \\
        N &= \text{number of hours in lookback period (24)} \\
        S_{\text{ticker}} &= \text{ticker-specific sensitivity multiplier}
        \end{align}
        """

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return """
        The Traffic Anomaly Index captures deviations in global internet traffic patterns
        from established baselines. This factor is relevant for cybersecurity and
        infrastructure companies because:

        1. **Cloudflare (NET)**: As a major CDN and security provider, traffic anomalies
           directly impact their business. Higher traffic generally means more revenue
           but also more resource utilization.

        2. **CrowdStrike (CRWD)**: Security-focused, traffic spikes often correlate with
           increased attack activity, driving demand for their services.

        3. **Palo Alto (PANW)**: Enterprise security solutions see increased deployment
           during periods of elevated internet activity and threat levels.

        4. **Zscaler (ZS)**: Cloud security gateway usage correlates with overall
           internet traffic patterns, especially for remote work scenarios.

        Positive anomalies (traffic above baseline) can indicate:
        - Increased economic activity online
        - Growing demand for security services
        - Potential for elevated threat environment

        Negative anomalies (traffic below baseline) may signal:
        - Infrastructure issues
        - Geopolitical disruptions
        - Economic slowdowns affecting digital activity
        """


class SecurityThreatLevel(BaseFactor):
    """Security Threat Level factor based on DDoS attack volume trends.

    This factor measures the intensity of DDoS attacks observed globally,
    which serves as a proxy for cybersecurity threat environment.

    Higher threat levels are generally bullish for security companies
    as they drive demand for protection services.
    """

    factor_id = "security_threat_level"
    name = "Security Threat Level"
    description = (
        "Measures DDoS attack intensity relative to baseline. "
        "Higher values indicate elevated threat environment."
    )
    domain = "internet"
    primary_entities = ["NET", "CRWD", "PANW", "ZS"]

    # Configuration
    LOOKBACK_HOURS = 24
    BASELINE_WINDOW_DAYS = 7
    MIN_DATA_POINTS = 12

    # Threat level thresholds (deviation percentages)
    THREAT_THRESHOLDS = {
        "low": Decimal("-20"),
        "normal": Decimal("0"),
        "elevated": Decimal("25"),
        "high": Decimal("50"),
        "critical": Decimal("100"),
    }

    async def compute(
        self,
        as_of_date: date,
        tickers: Optional[list[str]] = None,
    ) -> list[FactorResult]:
        """Compute Security Threat Level for cybersecurity entities.

        The factor aggregates hourly attack volume data and computes:
        - Mean attack intensity deviation from baseline
        - Variance to capture attack pattern volatility

        Args:
            as_of_date: Date to compute factor for
            tickers: Optional list of tickers (if None, uses primary_entities)

        Returns:
            List of FactorResult objects, one per ticker
        """
        target_tickers = tickers or self.primary_entities
        results = []

        async with get_async_session() as session:
            # Define time window
            end_time = datetime.combine(as_of_date, datetime.max.time()).replace(
                tzinfo=timezone.utc
            )
            start_time = end_time - timedelta(hours=self.LOOKBACK_HOURS)

            # Query attack data
            stmt = select(
                CloudflareRadarMetrics.deviation_pct,
                CloudflareRadarMetrics.value,
                CloudflareRadarMetrics.baseline_value,
            ).where(
                CloudflareRadarMetrics.metric_type == "attacks",
                CloudflareRadarMetrics.timestamp >= start_time,
                CloudflareRadarMetrics.timestamp <= end_time,
            )

            result = await session.execute(stmt)
            rows = result.fetchall()

            if len(rows) < self.MIN_DATA_POINTS:
                self.logger.warning(
                    "Insufficient attack data points",
                    required=self.MIN_DATA_POINTS,
                    available=len(rows),
                )
                for ticker in target_tickers:
                    results.append(
                        FactorResult(
                            ticker=ticker,
                            factor_id=self.factor_id,
                            as_of_date=as_of_date,
                            mean=Decimal("0"),
                            variance=Decimal("0"),
                            data_quality=Decimal("0.1"),
                            revision_status="insufficient_data",
                            metadata={
                                "data_points": len(rows),
                                "threat_level": "unknown",
                            },
                        )
                    )
                return results

            # Calculate aggregate metrics
            deviations = [row[0] for row in rows if row[0] is not None]
            values = [row[1] for row in rows if row[1] is not None]

            if not deviations:
                self.logger.warning("No valid attack deviation values found")
                return results

            # Compute mean and variance of attack deviations
            mean_deviation = Decimal(str(sum(deviations) / len(deviations)))
            variance = Decimal(
                str(
                    sum((d - mean_deviation) ** 2 for d in deviations)
                    / len(deviations)
                )
            )

            # Determine threat level category
            threat_level = self._categorize_threat_level(mean_deviation)

            # Calculate data quality
            expected_points = self.LOOKBACK_HOURS
            coverage = min(len(rows) / expected_points, Decimal("1.0"))
            data_quality = Decimal(str(coverage))

            # Create results for each ticker with company-specific adjustments
            for ticker in target_tickers:
                ticker_multiplier = self._get_ticker_threat_multiplier(ticker)
                adjusted_mean = mean_deviation * ticker_multiplier

                results.append(
                    FactorResult(
                        ticker=ticker,
                        factor_id=self.factor_id,
                        as_of_date=as_of_date,
                        mean=adjusted_mean,
                        variance=variance,
                        data_quality=data_quality,
                        revision_status="original",
                        metadata={
                            "data_points": len(rows),
                            "threat_level": threat_level,
                            "raw_mean_deviation": float(mean_deviation),
                            "max_attack_value": float(max(values)) if values else 0,
                            "ticker_multiplier": float(ticker_multiplier),
                        },
                    )
                )

        return results

    def _categorize_threat_level(self, deviation: Decimal) -> str:
        """Categorize the threat level based on deviation from baseline."""
        if deviation >= self.THREAT_THRESHOLDS["critical"]:
            return "critical"
        elif deviation >= self.THREAT_THRESHOLDS["high"]:
            return "high"
        elif deviation >= self.THREAT_THRESHOLDS["elevated"]:
            return "elevated"
        elif deviation >= self.THREAT_THRESHOLDS["normal"]:
            return "normal"
        else:
            return "low"

    def _get_ticker_threat_multiplier(self, ticker: str) -> Decimal:
        """Get ticker-specific multiplier for threat level factor.

        Companies with more direct exposure to attacks get higher multipliers.
        """
        multipliers = {
            "CRWD": Decimal("1.3"),  # Most sensitive - endpoint protection
            "NET": Decimal("1.2"),   # DDoS mitigation leader
            "ZS": Decimal("1.1"),    # Zero trust security
            "PANW": Decimal("1.0"),  # Broad security portfolio
        }
        return multipliers.get(ticker, Decimal("1.0"))

    def get_formula(self) -> str:
        """Return LaTeX formula for the factor."""
        return r"""
        \text{SecurityThreatLevel}_{t} = \frac{1}{N} \sum_{i=1}^{N}
        \left( \frac{A_i - B_i}{B_i} \times 100 \right) \times M_{\text{ticker}}

        \text{where:}
        \begin{align}
        A_i &= \text{attack volume at hour } i \\
        B_i &= \text{7-day rolling baseline attack volume at hour } i \\
        N &= \text{number of hours in lookback period (24)} \\
        M_{\text{ticker}} &= \text{ticker-specific threat multiplier}
        \end{align}

        \text{Threat Level Categories:}
        \begin{cases}
        \text{Critical} & \text{if deviation} \geq 100\% \\
        \text{High} & \text{if deviation} \geq 50\% \\
        \text{Elevated} & \text{if deviation} \geq 25\% \\
        \text{Normal} & \text{if deviation} \geq 0\% \\
        \text{Low} & \text{if deviation} < 0\%
        \end{cases}
        """

    def get_economic_rationale(self) -> str:
        """Return economic rationale for the factor."""
        return """
        The Security Threat Level factor captures the intensity of DDoS and other
        cyber attacks observed globally. This metric is highly relevant for
        cybersecurity companies because elevated threat levels typically drive:

        1. **Increased Demand**: Organizations prioritize security spending during
           heightened threat periods, benefiting security vendors.

        2. **Premium Pricing**: Critical threat environments allow security companies
           to command premium prices for their services.

        3. **Subscription Growth**: Elevated threats accelerate enterprise security
           adoption and expansion of existing contracts.

        4. **Market Awareness**: High-profile attack periods increase board-level
           attention to cybersecurity, driving budget allocation.

        Company-specific impacts:

        - **CrowdStrike (CRWD)**: Endpoint protection demand spikes during attack waves,
          as their Falcon platform detects and prevents intrusions.

        - **Cloudflare (NET)**: DDoS mitigation is a core service; attack volume
          directly correlates with service utilization.

        - **Zscaler (ZS)**: Zero trust adoption accelerates when traditional perimeter
          security proves inadequate during attacks.

        - **Palo Alto (PANW)**: Comprehensive security portfolio benefits from
          enterprise security reviews triggered by threat events.

        Note: While elevated threats are generally bullish for security stocks,
        extreme attacks that successfully breach major companies can create
        broader market risk and reputational concerns for the industry.
        """
