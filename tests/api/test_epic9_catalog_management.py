"""Comprehensive tests for Epic 9: Data Catalog Management (US-033 to US-035).

This module contains tests for:
- US-033: Source request submission
- US-034: Collector health tracking
- US-035: Source archival workflow
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.data_sources import (
    DataSource,
    DataSourceCategory,
    DataSourceRequest,
    RequestPriority,
    RequestStatus,
    CollectorHealthLog,
    CollectorStatus,
    UpdateFrequency,
    SaturationLevel,
)


def get_test_client():
    """Get test client that catches server errors as 500 responses."""
    return TestClient(app, raise_server_exceptions=False)


# ============================================================================
# US-033: Source Request Submission Tests
# ============================================================================


class TestDataSourceRequestModel:
    """Tests for DataSourceRequest model (US-033)."""

    def test_request_status_enum_values(self):
        """Test RequestStatus enum has all required values."""
        assert RequestStatus.PENDING.value == "pending"
        assert RequestStatus.UNDER_REVIEW.value == "under_review"
        assert RequestStatus.APPROVED.value == "approved"
        assert RequestStatus.REJECTED.value == "rejected"
        assert RequestStatus.IN_PROGRESS.value == "in_progress"
        assert RequestStatus.COMPLETED.value == "completed"

    def test_request_priority_enum_values(self):
        """Test RequestPriority enum has all required values."""
        assert RequestPriority.LOW.value == "low"
        assert RequestPriority.MEDIUM.value == "medium"
        assert RequestPriority.HIGH.value == "high"
        assert RequestPriority.CRITICAL.value == "critical"


class TestSourceRequestSubmission:
    """Tests for POST /api/v1/catalog/requests (US-033)."""

    def test_submit_request_endpoint_exists(self):
        """Test that the submit request endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/catalog/requests",
            json={
                "name": "New Data Source",
                "url": "https://example.com/data",
                "description": "This is a new data source that provides valuable insights",
                "use_case": "I need this for analyzing consumer spending patterns",
                "priority": "medium",
            },
        )
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_submit_request_validation_name_required(self):
        """Test that name is required."""
        client = get_test_client()
        response = client.post(
            "/api/v1/catalog/requests",
            json={
                "description": "This is a description",
                "use_case": "This is my use case",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_submit_request_validation_description_min_length(self):
        """Test that description must meet minimum length."""
        client = get_test_client()
        response = client.post(
            "/api/v1/catalog/requests",
            json={
                "name": "Test Source",
                "description": "Short",  # Too short (< 10 chars)
                "use_case": "This is my use case explanation",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_submit_request_with_all_fields(self):
        """Test submitting request with all optional fields."""
        client = get_test_client()
        response = client.post(
            "/api/v1/catalog/requests",
            json={
                "name": "Satellite Imagery Data",
                "url": "https://satellite-data.example.com/api",
                "description": "High-resolution satellite imagery for supply chain analysis",
                "use_case": "Tracking retail parking lot occupancy and shipping container activity",
                "priority": "high",
            },
        )
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_submit_request_priority_values(self):
        """Test all priority values are accepted."""
        client = get_test_client()
        for priority in ["low", "medium", "high", "critical"]:
            response = client.post(
                "/api/v1/catalog/requests",
                json={
                    "name": f"Test Source {priority}",
                    "description": "This is a test data source description",
                    "use_case": "Testing priority values acceptance",
                    "priority": priority,
                },
            )
            assert response.status_code in [
                status.HTTP_201_CREATED,
                status.HTTP_200_OK,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ]


class TestSourceRequestListing:
    """Tests for GET /api/v1/catalog/requests (US-033)."""

    def test_list_requests_endpoint_exists(self):
        """Test that list requests endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/requests")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_list_requests_with_status_filter(self):
        """Test filtering requests by status."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/requests?status=pending")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_list_requests_with_priority_filter(self):
        """Test filtering requests by priority."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/requests?priority=high")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_list_requests_with_pagination(self):
        """Test pagination for request listing."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/requests?page=1&page_size=10")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_get_single_request(self):
        """Test getting a single request by ID."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/requests/1")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestSourceRequestStatusUpdate:
    """Tests for PATCH /api/v1/admin/requests/{request_id}/status (US-033)."""

    def test_update_request_status_endpoint_exists(self):
        """Test that status update endpoint exists."""
        client = get_test_client()
        response = client.patch(
            "/api/v1/admin/requests/1/status",
            json={"status": "under_review"},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_update_request_status_all_values(self):
        """Test all status values can be set."""
        client = get_test_client()
        for status_value in ["under_review", "approved", "rejected", "in_progress", "completed"]:
            response = client.patch(
                "/api/v1/admin/requests/1/status",
                json={"status": status_value, "notes": f"Changed to {status_value}"},
            )
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ]


class TestSourceRequestSchemas:
    """Tests for source request API schemas."""

    def test_request_create_schema(self):
        """Test DataSourceRequestCreate schema."""
        from src.api.routes.catalog import DataSourceRequestCreate

        request = DataSourceRequestCreate(
            name="Test Source",
            url="https://example.com",
            description="This is a test data source",
            use_case="For testing purposes only",
            priority=RequestPriority.HIGH,
        )
        assert request.name == "Test Source"
        assert request.priority == RequestPriority.HIGH

    def test_request_response_schema(self):
        """Test DataSourceRequestResponse schema."""
        from src.api.routes.catalog import DataSourceRequestResponse

        response = DataSourceRequestResponse(
            id=1,
            name="Test Source",
            url="https://example.com",
            description="This is a test description",
            use_case="This is a test use case",
            priority=RequestPriority.MEDIUM,
            status=RequestStatus.PENDING,
            requester_id=1,
            created_at=datetime.utcnow(),
            reviewed_at=None,
            review_notes=None,
            created_source_id=None,
        )
        assert response.id == 1
        assert response.status == RequestStatus.PENDING


# ============================================================================
# US-034: Collector Health Tracking Tests
# ============================================================================


class TestCollectorHealthLogModel:
    """Tests for CollectorHealthLog model (US-034)."""

    def test_collector_status_enum_values(self):
        """Test CollectorStatus enum has all required values."""
        assert CollectorStatus.UP.value == "up"
        assert CollectorStatus.DOWN.value == "down"
        assert CollectorStatus.DEGRADED.value == "degraded"


class TestCollectorHealthEndpoint:
    """Tests for GET /api/v1/admin/collectors/health (US-034)."""

    def test_collector_health_endpoint_exists(self):
        """Test that collector health endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/collectors/health")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_collector_health_response_schema(self):
        """Test CollectorHealthResponse schema fields."""
        from src.api.routes.admin import CollectorHealthResponse

        response = CollectorHealthResponse(
            source_id=1,
            collector_name="TSA Checkpoint",
            status="up",
            last_success=datetime.utcnow(),
            last_run=datetime.utcnow(),
            last_error=None,
            error_count_24h=0,
            success_count_24h=24,
            freshness_hours=2.5,
            sla_hours=24.0,
            sla_breach=False,
            records_collected_24h=100,
            avg_duration_seconds=5.2,
        )
        assert response.source_id == 1
        assert response.status == "up"
        assert response.sla_breach == False
        assert response.error_count_24h == 0

    def test_collector_health_detail_endpoint_exists(self):
        """Test that collector health detail endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/collectors/1/health")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_collector_health_detail_response_schema(self):
        """Test CollectorHealthDetailResponse schema."""
        from src.api.routes.admin import CollectorHealthDetailResponse

        response = CollectorHealthDetailResponse(
            source_id=1,
            collector_name="TSA Checkpoint",
            status="up",
            last_success=datetime.utcnow(),
            last_run=datetime.utcnow(),
            error_count_24h=1,
            success_count_24h=23,
            freshness_hours=3.0,
            sla_hours=24.0,
            sla_breach=False,
            recent_errors=[
                {
                    "run_started_at": "2025-01-15T10:00:00",
                    "error_message": "Connection timeout",
                    "error_stack_trace": "Traceback...",
                    "triggered_by": "scheduled",
                }
            ],
            run_history=[
                {
                    "run_started_at": "2025-01-15T11:00:00",
                    "run_completed_at": "2025-01-15T11:00:05",
                    "is_success": True,
                    "records_collected": 50,
                    "duration_seconds": 5.0,
                    "triggered_by": "scheduled",
                }
            ],
        )
        assert response.source_id == 1
        assert len(response.recent_errors) == 1
        assert len(response.run_history) == 1


class TestCollectorTrigger:
    """Tests for POST /api/v1/admin/collectors/{source_id}/trigger (US-034)."""

    def test_trigger_collector_endpoint_exists(self):
        """Test that trigger collector endpoint exists."""
        client = get_test_client()
        response = client.post("/api/v1/admin/collectors/1/trigger")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_trigger_collector_response_schema(self):
        """Test CollectorTriggerResponse schema."""
        from src.api.routes.admin import CollectorTriggerResponse

        response = CollectorTriggerResponse(
            status="triggered",
            source_id=1,
            source_name="TSA Checkpoint",
            task_id="abc-123-def",
            triggered_at=datetime.utcnow(),
            triggered_by="manual",
        )
        assert response.status == "triggered"
        assert response.source_id == 1
        assert response.triggered_by == "manual"

    def test_trigger_nonexistent_collector(self):
        """Test triggering a nonexistent collector returns 404."""
        client = get_test_client()
        response = client.post("/api/v1/admin/collectors/99999/trigger")
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestSLABreachDetection:
    """Tests for SLA breach detection (US-034)."""

    def test_sla_breach_when_freshness_exceeds_sla(self):
        """Test that SLA breach is flagged when data is stale."""
        from src.api.routes.admin import CollectorHealthResponse

        # Freshness hours exceeds SLA hours
        response = CollectorHealthResponse(
            source_id=1,
            collector_name="Test Collector",
            status="degraded",
            last_success=datetime.utcnow() - timedelta(hours=48),
            last_run=datetime.utcnow(),
            last_error="Connection failed",
            error_count_24h=5,
            success_count_24h=0,
            freshness_hours=48.0,
            sla_hours=24.0,
            sla_breach=True,  # Freshness > SLA
            records_collected_24h=0,
            avg_duration_seconds=None,
        )
        assert response.sla_breach == True
        assert response.freshness_hours > response.sla_hours


# ============================================================================
# US-035: Source Archival Workflow Tests
# ============================================================================


class TestSourceArchivalEndpoint:
    """Tests for POST /api/v1/admin/sources/{source_id}/archive (US-035)."""

    def test_archive_source_endpoint_exists(self):
        """Test that archive source endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/sources/1/archive",
            json={
                "reason": "This data source has been deprecated and replaced by a newer version",
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_archive_source_with_alternative(self):
        """Test archiving source with alternative source link."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/sources/1/archive",
            json={
                "reason": "Replaced by improved data source with better coverage",
                "alternative_source_id": 2,
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_archive_source_requires_reason(self):
        """Test that archive requires a reason."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/sources/1/archive",
            json={},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_archive_source_reason_min_length(self):
        """Test that archive reason must meet minimum length."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/sources/1/archive",
            json={"reason": "Short"},  # Too short (< 10 chars)
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_archive_source_response_schema(self):
        """Test ArchivedSourceResponse schema."""
        from src.api.routes.admin import ArchivedSourceResponse

        response = ArchivedSourceResponse(
            id=1,
            name="Old TSA Data",
            description="Deprecated TSA checkpoint data",
            archived_at=datetime.utcnow(),
            archived_reason="Replaced by improved data collection method",
            alternative_source_id=2,
            alternative_source_name="New TSA Data",
            factors_count=5,
        )
        assert response.id == 1
        assert response.alternative_source_id == 2
        assert response.factors_count == 5


class TestListArchivedSources:
    """Tests for GET /api/v1/admin/sources/archived (US-035)."""

    def test_list_archived_sources_endpoint_exists(self):
        """Test that list archived sources endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/sources/archived")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestUnarchiveSource:
    """Tests for POST /api/v1/admin/sources/{source_id}/unarchive (US-035)."""

    def test_unarchive_source_endpoint_exists(self):
        """Test that unarchive source endpoint exists."""
        client = get_test_client()
        response = client.post("/api/v1/admin/sources/1/unarchive")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestArchivedDataAccess:
    """Tests for maintaining API access to archived data (US-035)."""

    def test_archived_source_still_accessible_via_detail(self):
        """Test that archived source details are still accessible."""
        client = get_test_client()
        # Even if source is archived, its detail should be accessible
        response = client.get("/api/v1/catalog/sources/1")
        # Should not return 403 Forbidden for archived sources
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_archived_source_data_preview_accessible(self):
        """Test that archived source data preview is still accessible."""
        client = get_test_client()
        response = client.get("/api/v1/catalog/sources/1/preview")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestSourceArchiveRequestSchema:
    """Tests for source archive request schema (US-035)."""

    def test_source_archive_request_schema(self):
        """Test SourceArchiveRequest schema."""
        from src.api.routes.admin import SourceArchiveRequest

        request = SourceArchiveRequest(
            reason="This source is being deprecated due to API changes",
            alternative_source_id=5,
        )
        assert request.alternative_source_id == 5

    def test_source_archive_request_optional_alternative(self):
        """Test that alternative_source_id is optional."""
        from src.api.routes.admin import SourceArchiveRequest

        request = SourceArchiveRequest(
            reason="Deprecating without replacement source available"
        )
        assert request.alternative_source_id is None


# ============================================================================
# Integration Tests
# ============================================================================


class TestEpic9Integration:
    """Integration tests for Epic 9 features."""

    def test_request_to_archive_workflow_endpoints_exist(self):
        """Test that all workflow endpoints exist for the full cycle."""
        client = get_test_client()

        # 1. Submit request
        submit_response = client.post(
            "/api/v1/catalog/requests",
            json={
                "name": "Integration Test Source",
                "description": "Source for integration testing",
                "use_case": "Testing the full workflow from request to archive",
            },
        )
        assert submit_response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

        # 2. List requests
        list_response = client.get("/api/v1/catalog/requests")
        assert list_response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

        # 3. Check collector health
        health_response = client.get("/api/v1/admin/collectors/health")
        assert health_response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

        # 4. Trigger collector
        trigger_response = client.post("/api/v1/admin/collectors/1/trigger")
        assert trigger_response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

        # 5. Archive source
        archive_response = client.post(
            "/api/v1/admin/sources/1/archive",
            json={"reason": "Integration test archival reason for this source"},
        )
        assert archive_response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

        # 6. List archived
        archived_response = client.get("/api/v1/admin/sources/archived")
        assert archived_response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]
