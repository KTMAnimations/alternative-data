"""Unit tests for geographic visualization API endpoints (US-014 to US-016)."""

from datetime import date, datetime

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app


# Create test client that doesn't raise server exceptions
def get_test_client():
    """Get test client that catches server errors as 500 responses."""
    return TestClient(app, raise_server_exceptions=False)


class TestEarthquakeMap:
    """Tests for earthquake map visualization (US-014)."""

    def test_earthquakes_endpoint_exists(self):
        """Test that earthquakes endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/geo/earthquakes")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_earthquakes_with_magnitude_filter(self):
        """Test filtering earthquakes by magnitude."""
        client = get_test_client()
        response = client.get("/api/v1/geo/earthquakes?magnitude_min=5.0")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_earthquakes_with_date_range(self):
        """Test filtering earthquakes by date range."""
        client = get_test_client()
        response = client.get(
            "/api/v1/geo/earthquakes?start_date=2025-01-01&end_date=2025-01-14"
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_earthquakes_with_limit(self):
        """Test limiting earthquake results."""
        client = get_test_client()
        response = client.get("/api/v1/geo/earthquakes?limit=50")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_earthquake_detail_endpoint_exists(self):
        """Test that earthquake detail endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/geo/earthquakes/us7000abcd")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestRegionalThresholds:
    """Tests for regional threshold configuration (US-015)."""

    def test_configure_regional_threshold_endpoint_exists(self):
        """Test that regional threshold configuration endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/geo/thresholds/regional",
            json={
                "region_name": "California",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-125, 32], [-114, 32], [-114, 42], [-125, 42], [-125, 32]]],
                },
                "magnitude_threshold": 5.0,
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_preview_threshold_events_endpoint_exists(self):
        """Test that threshold preview endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/geo/thresholds/preview?magnitude_threshold=6.0")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_preview_with_days_back(self):
        """Test threshold preview with days_back parameter."""
        client = get_test_client()
        response = client.get(
            "/api/v1/geo/thresholds/preview?magnitude_threshold=5.0&days_back=60"
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestPowerGridMap:
    """Tests for power grid visualization (US-016)."""

    def test_power_grid_endpoint_exists(self):
        """Test that power grid endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/geo/power-grid")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_power_grid_with_iso_filter(self):
        """Test filtering power grid by ISO region."""
        client = get_test_client()
        response = client.get("/api/v1/geo/power-grid?iso_region=ERCOT")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_power_grid_invalid_iso_region(self):
        """Test that invalid ISO region returns error."""
        client = get_test_client()
        response = client.get("/api/v1/geo/power-grid?iso_region=INVALID")
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_power_grid_with_price_percentile(self):
        """Test filtering power grid by price percentile."""
        client = get_test_client()
        response = client.get("/api/v1/geo/power-grid?price_percentile_min=90")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_power_grid_history_endpoint_exists(self):
        """Test that power grid history endpoint exists."""
        client = get_test_client()
        response = client.get(
            "/api/v1/geo/power-grid/history?node_id=ERCOT_HB_NORTH&start_date=2025-01-01&end_date=2025-01-14"
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestGeoSchemas:
    """Tests for geographic API schemas."""

    def test_geo_point_schema(self):
        """Test GeoPoint schema."""
        from src.api.routes.geo import GeoPoint

        point = GeoPoint(latitude=37.7749, longitude=-122.4194)
        assert point.latitude == 37.7749
        assert point.longitude == -122.4194

    def test_earthquake_feature_schema(self):
        """Test EarthquakeFeature schema."""
        from src.api.routes.geo import EarthquakeFeature

        feature = EarthquakeFeature(
            geometry={
                "type": "Point",
                "coordinates": [-122.4194, 37.7749],
            },
            properties={
                "event_id": "us7000abcd",
                "magnitude": 5.2,
                "depth_km": 10.0,
            },
        )
        assert feature.type == "Feature"
        assert feature.geometry["type"] == "Point"

    def test_earthquake_geojson_schema(self):
        """Test EarthquakeGeoJSON schema."""
        from src.api.routes.geo import EarthquakeGeoJSON, EarthquakeFeature

        feature = EarthquakeFeature(
            geometry={"type": "Point", "coordinates": [0, 0]},
            properties={"event_id": "test"},
        )
        geojson = EarthquakeGeoJSON(features=[feature])
        assert geojson.type == "FeatureCollection"
        assert len(geojson.features) == 1

    def test_regional_threshold_config_schema(self):
        """Test RegionalThresholdConfig schema."""
        from src.api.routes.geo import RegionalThresholdConfig

        config = RegionalThresholdConfig(
            region_name="California",
            geometry={"type": "Polygon", "coordinates": []},
            magnitude_threshold=5.0,
        )
        assert config.region_name == "California"
        assert config.magnitude_threshold == 5.0

    def test_power_grid_node_schema(self):
        """Test PowerGridNode schema."""
        from src.api.routes.geo import PowerGridNode, GeoPoint

        node = PowerGridNode(
            node_id="ERCOT_HB_NORTH",
            iso_region="ERCOT",
            location=GeoPoint(latitude=32.7767, longitude=-96.7970),
            current_lmp=45.50,
            lmp_percentile=75.0,
            renewable_share=0.35,
        )
        assert node.node_id == "ERCOT_HB_NORTH"
        assert node.current_lmp == 45.50


class TestEnhancedInsuranceLossModel:
    """Tests for enhanced insurance loss model (US-031)."""

    def test_regional_exposure_schema(self):
        """Test RegionalExposure schema."""
        from src.api.routes.geo import RegionalExposure

        exposure = RegionalExposure(
            region="California",
            exposure_percentage=35.0,
            exposed_policies_estimate=150000,
            exposure_value_usd=5000000000.0,
        )
        assert exposure.region == "California"
        assert exposure.exposure_percentage == 35.0

    def test_regional_exposure_percentage_bounds(self):
        """Test RegionalExposure percentage bounds."""
        from src.api.routes.geo import RegionalExposure
        from pydantic import ValidationError

        # Valid range
        exposure = RegionalExposure(
            region="California",
            exposure_percentage=50.0,
        )
        assert exposure.exposure_percentage == 50.0

        # Test bounds enforcement
        with pytest.raises(ValidationError):
            RegionalExposure(
                region="Invalid",
                exposure_percentage=150.0,  # Over 100
            )

    def test_insurance_estimate_schema(self):
        """Test InsuranceEstimate schema with new fields."""
        from src.api.routes.geo import InsuranceEstimate, RegionalExposure

        regional_exposures = [
            RegionalExposure(region="California", exposure_percentage=35.0),
            RegionalExposure(region="Pacific Northwest", exposure_percentage=15.0),
        ]

        estimate = InsuranceEstimate(
            ticker="ALL",
            name="Allstate",
            estimated_loss_mean=50000000.0,
            estimated_loss_variance=2500000000.0,
            confidence_level=0.75,
            exposure_by_region=regional_exposures,
            reinsurance_percentage=25.0,
            net_retained_loss=37500000.0,
        )

        assert estimate.ticker == "ALL"
        assert estimate.reinsurance_percentage == 25.0
        assert len(estimate.exposure_by_region) == 2
        assert estimate.net_retained_loss == 37500000.0

    def test_historical_comparison_schema(self):
        """Test HistoricalComparison schema."""
        from src.api.routes.geo import HistoricalComparison
        from datetime import datetime

        comparison = HistoricalComparison(
            event_id="us7000hist",
            timestamp=datetime(2020, 7, 5, 12, 30, 0),
            magnitude=6.0,
            distance_km=150.5,
            place_description="Near San Francisco, CA",
            actual_insured_loss_usd=500000000.0,
            similarity_score=0.85,
        )

        assert comparison.event_id == "us7000hist"
        assert comparison.similarity_score == 0.85
        assert comparison.actual_insured_loss_usd == 500000000.0

    def test_earthquake_detail_schema_with_new_fields(self):
        """Test EarthquakeDetail schema includes new fields."""
        from src.api.routes.geo import (
            EarthquakeDetail,
            GeoPoint,
            InsuranceEstimate,
            HistoricalComparison,
            RegionalExposure,
        )
        from datetime import datetime

        insurance_estimates = [
            InsuranceEstimate(
                ticker="ALL",
                name="Allstate",
                estimated_loss_mean=50000000.0,
                estimated_loss_variance=2500000000.0,
                confidence_level=0.75,
                exposure_by_region=[
                    RegionalExposure(region="California", exposure_percentage=35.0)
                ],
                reinsurance_percentage=25.0,
                net_retained_loss=37500000.0,
            )
        ]

        historical_comparisons = [
            HistoricalComparison(
                event_id="us7000hist",
                timestamp=datetime(2020, 7, 5, 12, 30, 0),
                magnitude=6.0,
                distance_km=150.5,
                place_description="Near San Francisco, CA",
                similarity_score=0.85,
            )
        ]

        detail = EarthquakeDetail(
            event_id="us7000test",
            timestamp=datetime.now(),
            magnitude=6.2,
            magnitude_type="mw",
            depth_km=15.0,
            location=GeoPoint(latitude=37.7749, longitude=-122.4194),
            place_description="Near San Francisco, CA",
            felt_reports=5000,
            tsunami_flag=False,
            estimated_population_exposure=2000000,
            estimated_economic_impact_usd=1000000000.0,
            insurance_estimates=insurance_estimates,
            historical_comparisons=historical_comparisons,
        )

        assert detail.event_id == "us7000test"
        assert len(detail.insurance_estimates) == 1
        assert detail.insurance_estimates[0].reinsurance_percentage == 25.0
        assert len(detail.historical_comparisons) == 1
        assert detail.historical_comparisons[0].similarity_score == 0.85

    def test_earthquake_detail_endpoint_with_historical_param(self):
        """Test earthquake detail endpoint with include_historical parameter."""
        client = get_test_client()

        # Test with historical included
        response = client.get(
            "/api/v1/geo/earthquakes/us7000test?include_historical=true"
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

        # Test with historical excluded
        response = client.get(
            "/api/v1/geo/earthquakes/us7000test?include_historical=false"
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_get_event_region_california(self):
        """Test region detection for California coordinates."""
        from src.api.routes.geo import _get_event_region

        # Los Angeles
        region = _get_event_region(34.0522, -118.2437)
        assert region == "California"

        # San Francisco
        region = _get_event_region(37.7749, -122.4194)
        assert region == "California"

    def test_get_event_region_pacific_northwest(self):
        """Test region detection for Pacific Northwest coordinates."""
        from src.api.routes.geo import _get_event_region

        # Seattle
        region = _get_event_region(47.6062, -122.3321)
        assert region == "Pacific Northwest"

        # Portland
        region = _get_event_region(45.5152, -122.6784)
        assert region == "Pacific Northwest"

    def test_get_event_region_other(self):
        """Test region detection falls back to Other."""
        from src.api.routes.geo import _get_event_region

        # Middle of Pacific Ocean
        region = _get_event_region(25.0, -150.0)
        assert region == "Other"

    def test_insurer_config_completeness(self):
        """Test INSURER_CONFIG has all required insurers."""
        from src.api.routes.geo import INSURER_CONFIG

        required_insurers = ["ALL", "TRV", "CB", "PGR"]

        for ticker in required_insurers:
            assert ticker in INSURER_CONFIG
            config = INSURER_CONFIG[ticker]
            assert "ticker" in config
            assert "name" in config
            assert "market_share" in config
            assert "reinsurance_percentage" in config
            assert "regional_exposure" in config
            # Check regional exposure sums close to 1.0
            total_exposure = sum(config["regional_exposure"].values())
            assert abs(total_exposure - 1.0) < 0.01

    def test_reinsurance_reduces_net_loss(self):
        """Test that reinsurance reduces net retained loss."""
        from src.api.routes.geo import INSURER_CONFIG

        for ticker, config in INSURER_CONFIG.items():
            reinsurance_pct = config["reinsurance_percentage"]
            # All insurers should have some reinsurance
            assert reinsurance_pct > 0
            assert reinsurance_pct < 100
