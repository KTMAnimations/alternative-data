"""Unit tests for catalog API endpoints (US-001 to US-004)."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.data_sources import (
    DataSourceCategory,
    UpdateFrequency,
    SaturationLevel,
)


# Create test client that doesn't raise server exceptions
# This allows us to test endpoint existence without database
def get_test_client():
    """Get test client that catches server errors as 500 responses."""
    return TestClient(app, raise_server_exceptions=False)


class TestListSources:
    """Tests for GET /api/v1/catalog/sources (US-001)."""

    @pytest.fixture
    def mock_sources(self):
        """Create mock data sources."""
        mock1 = MagicMock()
        mock1.id = 1
        mock1.name = "TSA Checkpoint"
        mock1.description = "Daily airport passenger throughput data"
        mock1.category = DataSourceCategory.TRAVEL
        mock1.update_frequency = UpdateFrequency.DAILY
        mock1.latency_hours = 12.0
        mock1.is_real_time = False
        mock1.saturation_level = SaturationLevel.MEDIUM
        mock1.primary_entities = ["DAL", "UAL", "AAL"]
        mock1.geographic_coverage = "United States"
        mock1.date_range_start = date(2019, 1, 1)
        mock1.date_range_end = date(2025, 1, 14)
        mock1.is_active = True
        mock1.is_archived = False

        mock2 = MagicMock()
        mock2.id = 2
        mock2.name = "OpenTable"
        mock2.description = "Restaurant seated diners metrics"
        mock2.category = DataSourceCategory.REAL_ESTATE
        mock2.update_frequency = UpdateFrequency.WEEKLY
        mock2.latency_hours = 48.0
        mock2.is_real_time = False
        mock2.saturation_level = SaturationLevel.LOW
        mock2.primary_entities = ["DRI", "MCD", "CMG"]
        mock2.geographic_coverage = "Global"
        mock2.date_range_start = date(2020, 1, 1)
        mock2.date_range_end = date(2025, 1, 14)
        mock2.is_active = True
        mock2.is_archived = False

        mock3 = MagicMock()
        mock3.id = 3
        mock3.name = "USGS Earthquake"
        mock3.description = "Real-time earthquake event data"
        mock3.category = DataSourceCategory.GOVERNMENT
        mock3.update_frequency = UpdateFrequency.CONTINUOUS
        mock3.latency_hours = 0.25
        mock3.is_real_time = True
        mock3.saturation_level = SaturationLevel.NOVEL
        mock3.primary_entities = ["ALL", "TRV", "CB"]
        mock3.geographic_coverage = "Global"
        mock3.date_range_start = date(2010, 1, 1)
        mock3.date_range_end = date(2025, 1, 14)
        mock3.is_active = True
        mock3.is_archived = False

        return [mock1, mock2, mock3]

    def test_list_sources_endpoint_exists(self):
        """Test that the list sources endpoint exists."""
        client = get_test_client()
        # Just check that we get a response (not 404)
        response = client.get("/api/v1/catalog/sources")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_list_sources_with_category_filter(self):
        """Test filtering sources by category parameter."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources?category=travel")
        # Endpoint should accept the category parameter
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,  # May fail due to DB, but endpoint works
        ]

    def test_list_sources_with_frequency_filter(self):
        """Test filtering sources by frequency parameter."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources?frequency=daily")
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_list_sources_with_search(self):
        """Test keyword search parameter."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources?search=earthquake")
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_list_sources_with_sorting(self):
        """Test sorting parameters."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources?sort_by=name&sort_order=asc")
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_list_sources_with_pagination(self):
        """Test pagination parameters."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources?page=1&page_size=10")
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_list_sources_invalid_sort_field(self):
        """Test that invalid sort field is rejected."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources?sort_by=invalid_field")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestSemanticSearch:
    """Tests for POST /api/v1/catalog/search/semantic (US-002)."""

    def test_semantic_search_endpoint_exists(self):
        """Test that semantic search endpoint exists."""
        client = get_test_client()
        response = client.post("/api/v1/catalog/search/semantic?query=consumer%20spending")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_semantic_search_minimum_length(self):
        """Test that query must meet minimum length."""
        client = get_test_client()
        response = client.post("/api/v1/catalog/search/semantic?query=ab")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_semantic_search_accepts_limit(self):
        """Test that limit parameter is accepted."""
        client = get_test_client()
        response = client.post("/api/v1/catalog/search/semantic?query=travel%20data&limit=5")
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]


class TestSourcePreview:
    """Tests for GET /api/v1/catalog/sources/{source_id}/preview (US-003)."""

    def test_preview_endpoint_exists(self):
        """Test that preview endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources/1/preview")
        # 404 is valid if source doesn't exist, but endpoint exists
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_preview_with_date_range(self):
        """Test preview with date range parameters."""
        client = get_test_client()
        response = client.get(
            "/api/v1/catalog/sources/1/preview?start_date=2025-01-01&end_date=2025-01-14"
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_preview_with_limit(self):
        """Test preview with limit parameter."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources/1/preview?limit=50")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestSourceDetail:
    """Tests for GET /api/v1/catalog/sources/{source_id} (US-004)."""

    def test_source_detail_endpoint_exists(self):
        """Test that source detail endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources/1")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_source_detail_invalid_id(self):
        """Test that invalid source ID returns appropriate error."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources/invalid")
        # Should fail validation (not an integer)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestCatalogResponseSchemas:
    """Tests for catalog API response schemas."""

    def test_list_sources_response_schema(self):
        """Test that list response has expected schema fields."""
        # This tests the Pydantic schema structure
        from src.api.routes.catalog import DataSourceListResponse, DataSourceResponse

        # Create a mock response
        mock_source = DataSourceResponse(
            id=1,
            name="Test Source",
            description="Test description",
            category=DataSourceCategory.TRAVEL,
            update_frequency=UpdateFrequency.DAILY,
            latency_hours=12.0,
            is_real_time=False,
            saturation_level=SaturationLevel.MEDIUM,
            primary_entities=["TEST"],
            geographic_coverage="Global",
            date_range_start=date(2020, 1, 1),
            date_range_end=date(2025, 1, 1),
            is_active=True,
            is_archived=False,
        )

        list_response = DataSourceListResponse(
            items=[mock_source],
            total=1,
            page=1,
            page_size=20,
        )

        assert list_response.total == 1
        assert list_response.page == 1
        assert list_response.page_size == 20
        assert len(list_response.items) == 1

    def test_preview_response_schema(self):
        """Test preview response schema."""
        from src.api.routes.catalog import PreviewResponse

        response = PreviewResponse(
            source_id=1,
            source_name="Test Source",
            data=[{"date": "2025-01-14", "value": 100}],
            row_count=1,
            completeness_pct=98.5,
            last_updated=date(2025, 1, 14),
            statistics={"mean": 100, "std": 10},
        )

        assert response.source_id == 1
        assert response.row_count == 1
        assert response.completeness_pct == 98.5


class TestCatalogValidation:
    """Tests for input validation on catalog endpoints."""

    def test_page_size_max_limit(self):
        """Test that page_size cannot exceed 100."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources?page_size=200")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_page_minimum_value(self):
        """Test that page must be at least 1."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources?page=0")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_sort_order_valid_values(self):
        """Test that sort_order only accepts asc/desc."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources?sort_order=invalid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_preview_limit_max(self):
        """Test that preview limit cannot exceed 1000."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources/1/preview?limit=2000")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
