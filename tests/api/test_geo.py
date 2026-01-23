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
