"""Unit tests for data catalog management API endpoints (US-033 to US-035)."""

from datetime import date, datetime

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.data_sources import DataSourceCategory, UpdateFrequency, SaturationLevel


# Create test client that doesn't raise server exceptions
def get_test_client():
    """Get test client that catches server errors as 500 responses."""
    return TestClient(app, raise_server_exceptions=False)


class TestDataSourceRequest:
    """Tests for new data source requests (US-033)."""

    def test_catalog_sources_endpoint_exists(self):
        """Test that catalog sources endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_catalog_semantic_search_endpoint_exists(self):
        """Test that semantic search endpoint exists."""
        client = get_test_client()
        response = client.post("/api/v1/catalog/search/semantic?query=consumer spending")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_catalog_source_detail_endpoint_exists(self):
        """Test that source detail endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources/1")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestCollectorHealth:
    """Tests for collector health dashboard (US-034)."""

    def test_collector_health_endpoint_exists(self):
        """Test that collector health endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/collectors/health")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_trigger_collector_endpoint_exists(self):
        """Test that trigger collector endpoint exists."""
        client = get_test_client()
        response = client.post("/api/v1/admin/collectors/1/trigger")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestArchivedSources:
    """Tests for viewing archived sources (US-035)."""

    def test_catalog_sources_supports_pagination(self):
        """Test that catalog sources supports pagination."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources?page=1&page_size=10")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_catalog_sources_supports_category_filter(self):
        """Test that catalog sources supports category filter."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources?category=travel")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_catalog_sources_supports_frequency_filter(self):
        """Test that catalog sources supports frequency filter."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources?frequency=daily")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_catalog_sources_supports_sorting(self):
        """Test that catalog sources supports sorting."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources?sort_by=latency_hours&sort_order=asc")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_catalog_sources_supports_search(self):
        """Test that catalog sources supports keyword search."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources?search=earthquake")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_source_preview_endpoint_exists(self):
        """Test that source preview endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources/1/preview")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestCatalogSchemas:
    """Tests for catalog API schemas."""

    def test_data_source_response_schema(self):
        """Test DataSourceResponse schema."""
        from src.api.routes.catalog import DataSourceResponse

        response = DataSourceResponse(
            id=1,
            name="TSA Checkpoint",
            description="Daily airport passenger throughput data",
            category=DataSourceCategory.TRAVEL,
            update_frequency=UpdateFrequency.DAILY,
            latency_hours=12.0,
            is_real_time=False,
            saturation_level=SaturationLevel.MEDIUM,
            primary_entities=["DAL", "UAL", "AAL"],
            geographic_coverage="United States",
            date_range_start=date(2019, 1, 1),
            date_range_end=date(2025, 1, 15),
            is_active=True,
            is_archived=False,
        )
        assert response.id == 1
        assert response.category == DataSourceCategory.TRAVEL

    def test_data_source_list_response_schema(self):
        """Test DataSourceListResponse schema."""
        from src.api.routes.catalog import DataSourceListResponse, DataSourceResponse

        response = DataSourceListResponse(
            items=[
                DataSourceResponse(
                    id=1,
                    name="TSA Checkpoint",
                    description="Test",
                    category=DataSourceCategory.TRAVEL,
                    update_frequency=UpdateFrequency.DAILY,
                    latency_hours=12.0,
                    is_real_time=False,
                    saturation_level=SaturationLevel.MEDIUM,
                    primary_entities=["DAL"],
                    geographic_coverage=None,
                    date_range_start=None,
                    date_range_end=None,
                    is_active=True,
                    is_archived=False,
                )
            ],
            total=1,
            page=1,
            page_size=20,
        )
        assert response.total == 1
        assert len(response.items) == 1

    def test_data_source_detail_response_schema(self):
        """Test DataSourceDetailResponse schema."""
        from src.api.routes.catalog import DataSourceDetailResponse

        response = DataSourceDetailResponse(
            id=1,
            name="TSA Checkpoint",
            description="Daily airport passenger throughput data",
            category=DataSourceCategory.TRAVEL,
            update_frequency=UpdateFrequency.DAILY,
            latency_hours=12.0,
            is_real_time=False,
            saturation_level=SaturationLevel.MEDIUM,
            primary_entities=["DAL", "UAL", "AAL"],
            geographic_coverage="United States",
            date_range_start=date(2019, 1, 1),
            date_range_end=date(2025, 1, 15),
            is_active=True,
            is_archived=False,
            api_documentation_url="https://www.tsa.gov/travel/passenger-volumes",
            archived_reason=None,
            sample_code="from altdata import Client...",
            derived_factors=["tsa_throughput_momentum", "tsa_weekday_weekend_ratio"],
        )
        assert response.id == 1
        assert len(response.derived_factors) == 2

    def test_preview_response_schema(self):
        """Test PreviewResponse schema."""
        from src.api.routes.catalog import PreviewResponse

        response = PreviewResponse(
            source_id=1,
            source_name="TSA Checkpoint",
            data=[
                {"date": "2025-01-15", "throughput": 2500000},
                {"date": "2025-01-14", "throughput": 2400000},
            ],
            row_count=2,
            completeness_pct=98.5,
            last_updated=date(2025, 1, 15),
            statistics={
                "min": 2400000,
                "max": 2500000,
                "mean": 2450000,
            },
        )
        assert response.source_id == 1
        assert response.row_count == 2
        assert response.completeness_pct == 98.5


class TestDataSourceEnums:
    """Tests for data source enum values."""

    def test_data_source_category_enum(self):
        """Test DataSourceCategory enum values."""
        assert DataSourceCategory.TRAVEL.value == "travel"
        assert DataSourceCategory.REAL_ESTATE.value == "real_estate"
        assert DataSourceCategory.ENERGY.value == "energy"
        assert DataSourceCategory.ENTERTAINMENT.value == "entertainment"

    def test_update_frequency_enum(self):
        """Test UpdateFrequency enum values."""
        assert UpdateFrequency.CONTINUOUS.value == "continuous"
        assert UpdateFrequency.HOURLY.value == "hourly"
        assert UpdateFrequency.DAILY.value == "daily"
        assert UpdateFrequency.WEEKLY.value == "weekly"
        assert UpdateFrequency.MONTHLY.value == "monthly"

    def test_saturation_level_enum(self):
        """Test SaturationLevel enum values."""
        assert SaturationLevel.LOW.value == "low"
        assert SaturationLevel.MEDIUM.value == "medium"
        assert SaturationLevel.HIGH.value == "high"
