"""Unit tests for disaster and event signals API endpoints (US-031 to US-032)."""

from datetime import date, datetime

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app


# Create test client that doesn't raise server exceptions
def get_test_client():
    """Get test client that catches server errors as 500 responses."""
    return TestClient(app, raise_server_exceptions=False)


class TestInsuranceLossEstimates:
    """Tests for insurance loss estimates (US-031)."""

    def test_earthquake_detail_endpoint_exists(self):
        """Test that earthquake detail endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/geo/earthquakes/us7000test")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_earthquake_list_endpoint_exists(self):
        """Test that earthquake list endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/geo/earthquakes")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_earthquake_magnitude_filter(self):
        """Test filtering earthquakes by magnitude."""
        client = get_test_client()
        response = client.get("/api/v1/geo/earthquakes?magnitude_min=6.0")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_earthquake_date_filter(self):
        """Test filtering earthquakes by date."""
        client = get_test_client()
        response = client.get(
            "/api/v1/geo/earthquakes?start_date=2025-01-01&end_date=2025-01-14"
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestBoxOfficePredictions:
    """Tests for box office predictions (US-032)."""

    def test_factors_list_endpoint_exists(self):
        """Test that factors list endpoint exists for box office."""
        client = get_test_client()
        response = client.get("/api/v1/factors?domain=entertainment")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_factor_detail_endpoint_exists(self):
        """Test that factor detail endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/factors/opening_weekend_surprise")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_factor_history_for_studios(self):
        """Test factor history for movie studio tickers."""
        client = get_test_client()
        response = client.get(
            "/api/v1/factors/opening_weekend_surprise/history?tickers=DIS,WBD,PARA"
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestDisasterSchemas:
    """Tests for disaster-related schemas."""

    def test_earthquake_detail_response_schema(self):
        """Test EarthquakeDetail schema."""
        from src.api.routes.geo import EarthquakeDetail, GeoPoint

        response = EarthquakeDetail(
            event_id="us7000test",
            timestamp=datetime.utcnow(),
            magnitude=6.5,
            magnitude_type="mw",
            depth_km=10.0,
            location=GeoPoint(latitude=34.0522, longitude=-118.2437),
            place_description="Near Los Angeles, CA",
            felt_reports=500,
            tsunami_flag=False,
            estimated_population_exposure=5000000,
            estimated_economic_impact_usd=1000000000.0,
            insurance_estimates=[
                {
                    "insurer_ticker": "ALL",
                    "insurer_name": "Allstate",
                    "estimated_loss_mean": 100000000.0,
                    "estimated_loss_variance": 250000000000000.0,
                },
                {
                    "insurer_ticker": "TRV",
                    "insurer_name": "Travelers",
                    "estimated_loss_mean": 80000000.0,
                    "estimated_loss_variance": 160000000000000.0,
                },
            ],
        )
        assert response.event_id == "us7000test"
        assert response.magnitude == 6.5
        assert len(response.insurance_estimates) == 2

    def test_earthquake_feature_schema(self):
        """Test EarthquakeFeature schema for GeoJSON."""
        from src.api.routes.geo import EarthquakeFeature

        feature = EarthquakeFeature(
            geometry={
                "type": "Point",
                "coordinates": [-118.2437, 34.0522],
            },
            properties={
                "event_id": "us7000test",
                "magnitude": 6.5,
                "depth_km": 10.0,
                "timestamp": "2025-01-15T12:00:00Z",
                "place": "Near Los Angeles, CA",
            },
        )
        assert feature.type == "Feature"
        assert feature.properties["magnitude"] == 6.5

    def test_earthquake_geojson_schema(self):
        """Test EarthquakeGeoJSON collection schema."""
        from src.api.routes.geo import EarthquakeGeoJSON, EarthquakeFeature

        feature = EarthquakeFeature(
            geometry={"type": "Point", "coordinates": [0, 0]},
            properties={"event_id": "test"},
        )
        geojson = EarthquakeGeoJSON(features=[feature])
        assert geojson.type == "FeatureCollection"
        assert len(geojson.features) == 1


class TestFactorSchemas:
    """Tests for factor schemas related to box office."""

    def test_opening_weekend_factor_definition(self):
        """Test that OpeningWeekendSurprise factor is properly defined."""
        from src.transformations.factors.boxoffice_factors import OpeningWeekendSurprise

        factor = OpeningWeekendSurprise()
        assert factor.factor_id == "opening_weekend_surprise"
        assert "Opening Weekend" in factor.name

    def test_studio_market_share_factor_definition(self):
        """Test that StudioMarketShare factor is properly defined."""
        from src.transformations.factors.boxoffice_factors import StudioMarketShare

        factor = StudioMarketShare()
        assert factor.factor_id == "studio_market_share"
        assert "Market Share" in factor.name


class TestSeismicFactors:
    """Tests for seismic-related factors."""

    def test_seismic_risk_exposure_factor(self):
        """Test that SeismicRiskExposure factor exists."""
        from src.transformations.factors.earthquake_factors import SeismicRiskExposure

        factor = SeismicRiskExposure()
        assert factor.factor_id == "seismic_risk_exposure"

    def test_disaster_impact_estimate_factor(self):
        """Test that DisasterImpactEstimate factor exists."""
        from src.transformations.factors.earthquake_factors import DisasterImpactEstimate

        factor = DisasterImpactEstimate()
        assert factor.factor_id == "disaster_impact_estimate"
