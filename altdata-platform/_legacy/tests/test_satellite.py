"""Tests for Sentinel-2 satellite data collection and factors."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

from src.collectors.sentinel import SentinelCollector
from src.models.satellite import (
    SatelliteLocation,
    SatelliteImage,
    ParkingLotMetrics,
    ConstructionMetrics,
    AgriculturalMetrics,
    PortActivityMetrics,
)
from src.transformations.factors.satellite_factors import (
    calc_parking_occupancy,
    calc_parking_trend,
    calc_construction_progress,
    calc_crop_health_index,
    calc_ndvi_anomaly,
    calc_retail_foot_traffic_proxy,
    ParkingOccupancy,
    ParkingTrend,
    ConstructionProgress,
    CropHealthIndex,
    NDVIAnomaly,
    RetailTrafficProxy,
)


# =============================================================================
# Satellite Model Tests
# =============================================================================

class TestSatelliteModels:
    """Test satellite database models."""

    def test_satellite_location_model(self):
        """Test SatelliteLocation model creation."""
        location = SatelliteLocation(
            location_id="walmart_bentonville_hq",
            name="Walmart HQ Bentonville",
            location_type="parking_lot",
            latitude=36.3729,
            longitude=-94.2088,
            company="Walmart",
            ticker="WMT",
        )
        assert location.location_id == "walmart_bentonville_hq"
        assert location.ticker == "WMT"
        assert location.location_type == "parking_lot"

    def test_satellite_image_model(self):
        """Test SatelliteImage model creation."""
        image = SatelliteImage(
            image_id="S2A_MSIL2A_20240615",
            location_id="walmart_bentonville_hq",
            acquisition_date=datetime.utcnow(),
            platform="Sentinel-2A",
            product_type="S2MSI2A",
            cloud_cover_pct=5.5,
            processing_level="Level-2A",
        )
        assert image.platform == "Sentinel-2A"
        assert image.cloud_cover_pct == 5.5

    def test_parking_lot_metrics_model(self):
        """Test ParkingLotMetrics model creation."""
        metrics = ParkingLotMetrics(
            location_id="tesla_fremont_factory",
            observation_date=date.today(),
            total_spaces=5000,
            occupied_spaces=4250,
            occupancy_rate=0.85,
            cars_detected=4000,
            trucks_detected=250,
            confidence_score=0.92,
            ticker="TSLA",
        )
        assert metrics.occupancy_rate == 0.85
        assert metrics.cars_detected == 4000

    def test_construction_metrics_model(self):
        """Test ConstructionMetrics model creation."""
        metrics = ConstructionMetrics(
            location_id="intel_ohio_fab",
            observation_date=date.today(),
            active_area_sqm=150000,
            equipment_count=45,
            change_from_prior=5.5,
            foundation_complete=True,
            structure_visible=True,
            estimated_completion_pct=35.0,
            ticker="INTC",
        )
        assert metrics.estimated_completion_pct == 35.0
        assert metrics.foundation_complete is True

    def test_agricultural_metrics_model(self):
        """Test AgriculturalMetrics model creation."""
        metrics = AgriculturalMetrics(
            location_id="iowa_corn_belt",
            region="iowa",
            crop_type="corn",
            observation_date=date.today(),
            ndvi_mean=0.72,
            ndvi_std=0.08,
            evi_mean=0.55,
            crop_health_score=85.0,
            stress_indicator=0.15,
            ndvi_vs_historical=5.2,
        )
        assert metrics.ndvi_mean == 0.72
        assert metrics.crop_health_score == 85.0

    def test_port_activity_metrics_model(self):
        """Test PortActivityMetrics model creation."""
        metrics = PortActivityMetrics(
            port_id="USLAX",
            observation_date=date.today(),
            container_area_sqm=500000,
            estimated_teu=15000,
            vessels_detected=25,
            activity_index=78.5,
            change_from_prior=3.2,
        )
        assert metrics.activity_index == 78.5
        assert metrics.vessels_detected == 25


# =============================================================================
# Sentinel Collector Tests
# =============================================================================

class TestSentinelCollector:
    """Test Sentinel-2 collector."""

    def test_collector_initialization(self):
        """Test collector initialization."""
        collector = SentinelCollector(username="user", password="pass")
        assert collector.username == "user"
        assert collector.SOURCE_NAME == "sentinel"

    def test_tracked_locations(self):
        """Test tracked locations configuration."""
        collector = SentinelCollector()
        assert len(collector.TRACKED_LOCATIONS) >= 10

        # Check for various location types
        types = [l["type"] for l in collector.TRACKED_LOCATIONS]
        assert "parking_lot" in types
        assert "construction" in types
        assert "agricultural" in types
        assert "port" in types

    def test_get_bbox(self):
        """Test bounding box calculation."""
        collector = SentinelCollector()
        bbox = collector._get_bbox(40.0, -100.0, size_km=10)

        west, south, east, north = bbox
        assert west < -100.0 < east
        assert south < 40.0 < north

    def test_get_bbox_size(self):
        """Test bbox size scales correctly."""
        collector = SentinelCollector()

        small_bbox = collector._get_bbox(40.0, -100.0, size_km=5)
        large_bbox = collector._get_bbox(40.0, -100.0, size_km=20)

        small_width = small_bbox[2] - small_bbox[0]
        large_width = large_bbox[2] - large_bbox[0]

        assert large_width > small_width

    def test_calculate_ndvi(self):
        """Test NDVI calculation."""
        collector = SentinelCollector()

        # Healthy vegetation (high NIR, low red)
        ndvi = collector.calculate_ndvi(nir_band=0.8, red_band=0.1)
        assert 0.7 < ndvi < 0.9

        # Bare soil (similar NIR and red)
        ndvi = collector.calculate_ndvi(nir_band=0.3, red_band=0.3)
        assert ndvi == 0

        # Water (negative NDVI)
        ndvi = collector.calculate_ndvi(nir_band=0.1, red_band=0.2)
        assert ndvi < 0

    def test_calculate_ndvi_zero_division(self):
        """Test NDVI handles zero values."""
        collector = SentinelCollector()
        ndvi = collector.calculate_ndvi(nir_band=0, red_band=0)
        assert ndvi == 0

    def test_calculate_evi(self):
        """Test EVI calculation."""
        collector = SentinelCollector()
        evi = collector.calculate_evi(nir_band=0.8, red_band=0.1, blue_band=0.05)
        assert 0 < evi < 1

    def test_calculate_evi_zero_division(self):
        """Test EVI handles zero denominator."""
        collector = SentinelCollector()
        # When denominator would be zero
        evi = collector.calculate_evi(nir_band=0, red_band=0, blue_band=0, l=0)
        assert evi == 0

    def test_parse_image_entry(self):
        """Test parsing Copernicus API entry."""
        collector = SentinelCollector()
        entry = {
            "id": "abc123",
            "title": "S2A_MSIL2A_20240615",
            "str": [
                {"name": "platformname", "content": "Sentinel-2A"},
                {"name": "producttype", "content": "S2MSI2A"},
            ],
            "double": [
                {"name": "cloudcoverpercentage", "content": "5.5"},
            ],
            "date": [
                {"name": "beginposition", "content": "2024-06-15T10:30:00Z"},
            ],
            "link": [{"href": "https://download.url"}],
        }

        parsed = collector._parse_image_entry(entry, "test_location")

        assert parsed["image_id"] == "abc123"
        assert parsed["location_id"] == "test_location"
        assert parsed["platform"] == "Sentinel-2A"
        assert parsed["cloud_cover_pct"] == 5.5

    def test_parse_returns_structured_data(self):
        """Test parse returns proper structure."""
        collector = SentinelCollector()
        raw_data = [
            {
                "location": {
                    "location_id": "loc1",
                    "name": "Test",
                    "type": "parking_lot",
                    "lat": 40.0,
                    "lon": -100.0,
                },
                "images": [
                    {"image_id": "img1", "location_id": "loc1"},
                ],
            }
        ]

        parsed = collector.parse(raw_data)

        assert "locations" in parsed
        assert "images" in parsed
        assert len(parsed["locations"]) == 1
        assert len(parsed["images"]) == 1

    def test_estimate_parking_occupancy_placeholder(self):
        """Test parking occupancy estimation returns expected structure."""
        collector = SentinelCollector()
        result = collector.estimate_parking_occupancy({}, total_spaces=1000)

        assert "total_spaces" in result
        assert result["total_spaces"] == 1000
        assert "occupancy_rate" in result
        assert "confidence_score" in result


# =============================================================================
# Satellite Factor Calculation Tests
# =============================================================================

class TestSatelliteFactorCalculations:
    """Test satellite factor calculation functions."""

    @patch("src.transformations.factors.satellite_factors.SessionLocal")
    def test_calc_parking_occupancy(self, mock_session_local):
        """Test parking occupancy calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.scalar.return_value = 0.75

        result = calc_parking_occupancy("WMT", date(2024, 6, 15))

        assert result == 0.75
        mock_session.close.assert_called_once()

    @patch("src.transformations.factors.satellite_factors.SessionLocal")
    def test_calc_parking_occupancy_no_data(self, mock_session_local):
        """Test parking occupancy returns None when no data."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_session.query.return_value.filter.return_value.scalar.return_value = None

        result = calc_parking_occupancy("UNKNOWN", date(2024, 6, 15))

        assert result is None

    @patch("src.transformations.factors.satellite_factors.SessionLocal")
    def test_calc_parking_trend(self, mock_session_local):
        """Test parking trend calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Short avg: 0.80, Long avg: 0.70
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [0.80, 0.70]

        result = calc_parking_trend("TSLA", date(2024, 6, 15))

        # Trend = 0.80 - 0.70 = 0.10
        assert abs(result - 0.10) < 0.001

    @patch("src.transformations.factors.satellite_factors.SessionLocal")
    def test_calc_construction_progress(self, mock_session_local):
        """Test construction progress calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_record = MagicMock()
        mock_record.estimated_completion_pct = 45.0
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_record

        result = calc_construction_progress("intel_ohio_fab", date(2024, 6, 15))

        assert result == 45.0

    @patch("src.transformations.factors.satellite_factors.SessionLocal")
    def test_calc_crop_health_index(self, mock_session_local):
        """Test crop health index calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.scalar.return_value = 82.5

        result = calc_crop_health_index("iowa", date(2024, 6, 15))

        assert result == 82.5

    @patch("src.transformations.factors.satellite_factors.SessionLocal")
    def test_calc_ndvi_anomaly(self, mock_session_local):
        """Test NDVI anomaly calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.first.return_value = (5.5,)

        result = calc_ndvi_anomaly("california_central_valley", date(2024, 6, 15))

        assert result == 5.5

    @patch("src.transformations.factors.satellite_factors.SessionLocal")
    def test_calc_retail_foot_traffic_proxy(self, mock_session_local):
        """Test retail traffic proxy calculation."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_session.query.return_value.filter.return_value.scalar.return_value = 0.72

        result = calc_retail_foot_traffic_proxy(target_date=date(2024, 6, 15))

        # 0.72 * 100 = 72
        assert result == 72.0


# =============================================================================
# Satellite Factor Class Tests
# =============================================================================

class TestSatelliteFactorClasses:
    """Test satellite factor classes."""

    def test_parking_occupancy_factor(self):
        """Test ParkingOccupancy factor class."""
        factor = ParkingOccupancy()
        assert factor.FACTOR_NAME == "parking_occupancy"
        assert factor.CATEGORY == "satellite"
        assert factor.ENTITY_TYPE == "ticker"

    def test_parking_trend_factor(self):
        """Test ParkingTrend factor class."""
        factor = ParkingTrend()
        assert factor.FACTOR_NAME == "parking_trend"
        assert factor.LOOKBACK_DAYS == 30

    def test_construction_progress_factor(self):
        """Test ConstructionProgress factor class."""
        factor = ConstructionProgress()
        assert factor.FACTOR_NAME == "construction_progress"
        assert factor.ENTITY_TYPE == "location"

    def test_crop_health_index_factor(self):
        """Test CropHealthIndex factor class."""
        factor = CropHealthIndex()
        assert factor.FACTOR_NAME == "crop_health_index"
        assert factor.ENTITY_TYPE == "region"

    def test_ndvi_anomaly_factor(self):
        """Test NDVIAnomaly factor class."""
        factor = NDVIAnomaly()
        assert factor.FACTOR_NAME == "ndvi_anomaly"
        assert "ndvi" in factor.FACTOR_DESCRIPTION.lower()

    def test_retail_traffic_proxy_factor(self):
        """Test RetailTrafficProxy factor class."""
        factor = RetailTrafficProxy()
        assert factor.FACTOR_NAME == "retail_traffic_proxy"
        assert factor.ENTITY_TYPE == "market"

    @patch("src.transformations.factors.satellite_factors.calc_parking_occupancy")
    def test_parking_occupancy_compute(self, mock_calc):
        """Test ParkingOccupancy compute method."""
        mock_calc.return_value = 0.82

        factor = ParkingOccupancy()
        result = factor.compute("WMT", datetime(2024, 6, 15))

        assert result == 0.82
        mock_calc.assert_called_once()

    @patch("src.transformations.factors.satellite_factors.calc_crop_health_index")
    def test_crop_health_compute(self, mock_calc):
        """Test CropHealthIndex compute method."""
        mock_calc.return_value = 88.5

        factor = CropHealthIndex()
        result = factor.compute("iowa", datetime(2024, 6, 15))

        assert result == 88.5


# =============================================================================
# Factor Registry Tests
# =============================================================================

class TestSatelliteFactorRegistry:
    """Test satellite factors in registry."""

    def test_satellite_factors_registered(self):
        """Test that all satellite factors are registered."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        registered_ids = [f["id"] for f in registered]

        satellite_factors = [
            "parking_occupancy",
            "parking_trend",
            "construction_progress",
            "crop_health_index",
            "ndvi_anomaly",
            "retail_traffic_proxy",
        ]

        for factor in satellite_factors:
            assert factor in registered_ids, f"{factor} not registered"

    def test_satellite_factors_category(self):
        """Test satellite factors have correct category."""
        from src.transformations.base import FactorRegistry

        registered = FactorRegistry.list_factors()
        satellite_factors = [f for f in registered if f["category"] == "satellite"]

        assert len(satellite_factors) >= 6
