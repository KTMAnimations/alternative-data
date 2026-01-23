"""Tests for Cloudflare Radar data collection and factors."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

from src.collectors.cloudflare_radar import CloudflareRadarCollector
from src.models.cloudflare_radar import CloudflareRadarMetrics
from src.transformations.factors.cloudflare_factors import (
    calc_traffic_anomaly_index,
    calc_attack_volume_index,
    calc_traffic_volatility,
    calc_security_threat_level,
    calc_outage_count,
    TrafficAnomalyIndex,
    SecurityThreatLevel,
    AttackVolumeIndex,
    InternetOutageCount,
    TrafficVolatility,
    CYBERSECURITY_TICKERS,
    CLOUD_PROVIDERS,
    CDN_PROVIDERS,
)


# =============================================================================
# Cloudflare Model Tests
# =============================================================================

class TestCloudflareModels:
    """Test Cloudflare database models."""

    def test_cloudflare_radar_metrics_model(self):
        """Test CloudflareRadarMetrics model creation."""
        metrics = CloudflareRadarMetrics(
            timestamp=datetime(2024, 6, 15, 14, 0, 0),
            region_type="global",
            region_code=None,
            traffic_index=105.5,
            traffic_change_pct=5.5,
            http_share=15.0,
            https_share=82.0,
            http3_share=3.0,
            attack_volume_index=120.0,
            bot_traffic_share=35.0,
            threat_score=45.0,
            is_outage_detected="No",
            outage_severity=None,
        )
        assert metrics.traffic_index == 105.5
        assert metrics.attack_volume_index == 120.0
        assert metrics.is_outage_detected == "No"

    def test_cloudflare_metrics_with_outage(self):
        """Test CloudflareRadarMetrics with outage."""
        metrics = CloudflareRadarMetrics(
            timestamp=datetime(2024, 6, 15, 14, 0, 0),
            region_type="country",
            region_code="US",
            traffic_index=65.0,
            is_outage_detected="Yes",
            outage_severity="moderate",
        )
        assert metrics.is_outage_detected == "Yes"
        assert metrics.outage_severity == "moderate"
        assert metrics.region_code == "US"

    def test_cloudflare_metrics_with_extra_data(self):
        """Test CloudflareRadarMetrics with JSON extra metrics."""
        extra = {
            "ipv6_share": 25.0,
            "mobile_share": 60.0,
            "desktop_share": 40.0,
        }
        metrics = CloudflareRadarMetrics(
            timestamp=datetime.utcnow(),
            traffic_index=100.0,
            extra_metrics=extra,
        )
        assert metrics.extra_metrics == extra
        assert metrics.extra_metrics["ipv6_share"] == 25.0


# =============================================================================
# Cloudflare Collector Tests
# =============================================================================

class TestCloudflareRadarCollector:
    """Test Cloudflare Radar collector."""

    def test_collector_initialization(self):
        """Test collector initialization."""
        collector = CloudflareRadarCollector()
        assert collector.SOURCE_NAME == "cloudflare_radar"
        assert "cloudflare" in collector.BASE_URL.lower()

    def test_parse_returns_list(self):
        """Test parse returns list of metrics."""
        collector = CloudflareRadarCollector()
        result = collector.parse({})
        assert isinstance(result, list)


# =============================================================================
# Cloudflare Factor Calculation Tests
# =============================================================================

class TestCloudflareFactorCalculations:
    """Test Cloudflare factor calculation functions."""

    @patch("src.transformations.factors.cloudflare_factors.SessionLocal")
    def test_calc_traffic_anomaly_index(self, mock_session_local):
        """Test traffic anomaly index calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.scalar.return_value = 108.5

        result = calc_traffic_anomaly_index(date(2024, 6, 15), lookback_hours=24)

        assert result == 108.5
        mock_session.close.assert_called_once()

    @patch("src.transformations.factors.cloudflare_factors.SessionLocal")
    def test_calc_attack_volume_index(self, mock_session_local):
        """Test attack volume index calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.scalar.return_value = 135.0

        result = calc_attack_volume_index(date(2024, 6, 15), lookback_hours=24)

        assert result == 135.0

    @patch("src.transformations.factors.cloudflare_factors.SessionLocal")
    def test_calc_traffic_volatility(self, mock_session_local):
        """Test traffic volatility calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.scalar.return_value = 12.5

        result = calc_traffic_volatility(date(2024, 6, 15), lookback_hours=48)

        assert result == 12.5

    @patch("src.transformations.factors.cloudflare_factors.SessionLocal")
    def test_calc_security_threat_level(self, mock_session_local):
        """Test security threat level calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Attack avg: 120, Threat avg: 50
        # Composite = 120 * 0.6 + 50 * 0.4 = 72 + 20 = 92
        mock_session.query.return_value.filter.return_value.first.return_value = (120.0, 50.0)

        result = calc_security_threat_level(date(2024, 6, 15))

        assert result is not None
        assert abs(result - 92.0) < 0.1

    @patch("src.transformations.factors.cloudflare_factors.SessionLocal")
    def test_calc_outage_count(self, mock_session_local):
        """Test outage count calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.scalar.return_value = 3

        result = calc_outage_count(date(2024, 6, 15), lookback_hours=24)

        assert result == 3

    @patch("src.transformations.factors.cloudflare_factors.SessionLocal")
    def test_calc_outage_count_no_outages(self, mock_session_local):
        """Test outage count with no outages."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_session.query.return_value.filter.return_value.scalar.return_value = 0

        result = calc_outage_count(date(2024, 6, 15))

        assert result == 0


# =============================================================================
# Cloudflare Factor Class Tests
# =============================================================================

class TestCloudflareFactorClasses:
    """Test Cloudflare factor classes."""

    def test_traffic_anomaly_index_factor(self):
        """Test TrafficAnomalyIndex factor class."""
        factor = TrafficAnomalyIndex()
        assert factor.FACTOR_NAME == "traffic_anomaly_index"
        assert factor.CATEGORY == "internet"
        assert factor.ENTITY_TYPE == "market"

    def test_security_threat_level_factor(self):
        """Test SecurityThreatLevel factor class."""
        factor = SecurityThreatLevel()
        assert factor.FACTOR_NAME == "security_threat_level"
        assert factor.ENTITY_TYPE == "company"

    def test_attack_volume_index_factor(self):
        """Test AttackVolumeIndex factor class."""
        factor = AttackVolumeIndex()
        assert factor.FACTOR_NAME == "attack_volume_index"
        assert "attack" in factor.FACTOR_DESCRIPTION.lower()

    def test_internet_outage_count_factor(self):
        """Test InternetOutageCount factor class."""
        factor = InternetOutageCount()
        assert factor.FACTOR_NAME == "internet_outage_count"

    def test_traffic_volatility_factor(self):
        """Test TrafficVolatility factor class."""
        factor = TrafficVolatility()
        assert factor.FACTOR_NAME == "traffic_volatility"
        assert factor.LOOKBACK_DAYS >= 1

    def test_security_threat_only_for_cyber_stocks(self):
        """Test security threat factor only applies to cyber stocks."""
        factor = SecurityThreatLevel()

        with patch("src.transformations.factors.cloudflare_factors.calc_security_threat_level") as mock_calc:
            mock_calc.return_value = 75.0
            result = factor.compute("AAPL", datetime(2024, 6, 15))
            assert result is None

    @patch("src.transformations.factors.cloudflare_factors.calc_security_threat_level")
    def test_security_threat_compute_for_cyber(self, mock_calc):
        """Test security threat compute for cybersecurity ticker."""
        mock_calc.return_value = 85.0

        factor = SecurityThreatLevel()
        result = factor.compute("CRWD", datetime(2024, 6, 15))

        assert result == 85.0

    @patch("src.transformations.factors.cloudflare_factors.calc_traffic_anomaly_index")
    def test_traffic_anomaly_compute(self, mock_calc):
        """Test traffic anomaly compute method."""
        mock_calc.return_value = 110.0

        factor = TrafficAnomalyIndex()
        result = factor.compute("market", datetime(2024, 6, 15))

        assert result == 110.0


# =============================================================================
# Cloudflare Factor Registry Tests
# =============================================================================

class TestCloudflareFactorRegistry:
    """Test Cloudflare factors in registry."""

    def test_cloudflare_factors_registered(self):
        """Test that all Cloudflare factors are registered."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        registered_ids = [f["id"] for f in registered]

        cloudflare_factors = [
            "traffic_anomaly_index",
            "security_threat_level",
            "attack_volume_index",
            "internet_outage_count",
            "traffic_volatility",
        ]

        for factor in cloudflare_factors:
            assert factor in registered_ids, f"{factor} not registered"

    def test_cloudflare_factors_category(self):
        """Test Cloudflare factors have correct category."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        cloudflare_factor_names = [
            "traffic_anomaly_index",
            "security_threat_level",
            "attack_volume_index",
            "internet_outage_count",
            "traffic_volatility",
        ]
        cloudflare_factors = [f for f in registered if f["id"] in cloudflare_factor_names]

        assert len(cloudflare_factors) == 5
        for factor in cloudflare_factors:
            assert factor["category"] == "internet"


# =============================================================================
# Entity Mapping Tests
# =============================================================================

class TestCloudflareEntityMapping:
    """Test Cloudflare entity mapping."""

    def test_cybersecurity_tickers_defined(self):
        """Test cybersecurity tickers are defined."""
        assert len(CYBERSECURITY_TICKERS) >= 5
        assert "CRWD" in CYBERSECURITY_TICKERS  # CrowdStrike
        assert "PANW" in CYBERSECURITY_TICKERS  # Palo Alto Networks
        assert "ZS" in CYBERSECURITY_TICKERS    # Zscaler
        assert "FTNT" in CYBERSECURITY_TICKERS  # Fortinet
        assert "NET" in CYBERSECURITY_TICKERS   # Cloudflare

    def test_cloud_providers_defined(self):
        """Test cloud provider tickers are defined."""
        assert len(CLOUD_PROVIDERS) >= 3
        assert "AMZN" in CLOUD_PROVIDERS  # AWS
        assert "MSFT" in CLOUD_PROVIDERS  # Azure
        assert "GOOGL" in CLOUD_PROVIDERS  # GCP

    def test_cdn_providers_defined(self):
        """Test CDN provider tickers are defined."""
        assert len(CDN_PROVIDERS) >= 2
        assert "NET" in CDN_PROVIDERS   # Cloudflare
        assert "AKAM" in CDN_PROVIDERS  # Akamai
