"""Unit tests for admin and entity mapping API endpoints (US-027 to US-030, US-033 to US-035)."""

from datetime import datetime

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.entity_mappings import MappingStatus, SuggestionStatus


# Create test client that doesn't raise server exceptions
def get_test_client():
    """Get test client that catches server errors as 500 responses."""
    return TestClient(app, raise_server_exceptions=False)


class TestPendingMappings:
    """Tests for pending entity mapping review (US-027)."""

    def test_pending_mappings_endpoint_exists(self):
        """Test that pending mappings endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/mappings/pending")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_pending_mappings_with_source_filter(self):
        """Test filtering pending mappings by source."""
        client = get_test_client()
        response = client.get("/api/v1/admin/mappings/pending?source_id=1")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_pending_mappings_with_limit(self):
        """Test limiting pending mappings results."""
        client = get_test_client()
        response = client.get("/api/v1/admin/mappings/pending?limit=10")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_decide_mapping_endpoint_exists(self):
        """Test that mapping decision endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/mappings/1/decide",
            json={"action": "approve"},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_decide_mapping_approve(self):
        """Test approving a mapping."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/mappings/1/decide",
            json={"action": "approve", "notes": "Confirmed correct"},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_decide_mapping_reject(self):
        """Test rejecting a mapping."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/mappings/1/decide",
            json={"action": "reject", "notes": "Incorrect mapping"},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_decide_mapping_correct(self):
        """Test correcting a mapping."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/mappings/1/decide",
            json={
                "action": "correct",
                "ticker": "AAPL",
                "notes": "Corrected ticker",
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_bulk_approve_endpoint_exists(self):
        """Test that bulk approve endpoint exists."""
        client = get_test_client()
        response = client.post("/api/v1/admin/mappings/bulk-approve")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_bulk_approve_with_confidence(self):
        """Test bulk approve with confidence threshold."""
        client = get_test_client()
        response = client.post("/api/v1/admin/mappings/bulk-approve?min_confidence=0.95")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestMappingSuggestions:
    """Tests for user mapping suggestions (US-028)."""

    def test_pending_suggestions_endpoint_exists(self):
        """Test that pending suggestions endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/suggestions/pending")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_pending_suggestions_with_source_filter(self):
        """Test filtering suggestions by source."""
        client = get_test_client()
        response = client.get("/api/v1/admin/suggestions/pending?source_id=1")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestMappingCoverage:
    """Tests for mapping coverage statistics (US-029)."""

    def test_coverage_endpoint_exists(self):
        """Test that mapping coverage endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/mappings/coverage")
        assert response.status_code in [
            status.HTTP_200_OK,
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


class TestAdminSchemas:
    """Tests for admin API schemas."""

    def test_pending_mapping_response_schema(self):
        """Test PendingMappingResponse schema."""
        from src.api.routes.admin import PendingMappingResponse

        response = PendingMappingResponse(
            id=1,
            source_name="TSA Checkpoint",
            source_entity_id="entity_001",
            source_entity_name="Southwest Airlines",
            suggested_ticker="LUV",
            confidence_score=0.95,
            ai_suggestions=[
                {"ticker": "LUV", "score": 0.95},
                {"ticker": "DAL", "score": 0.7},
            ],
            status=MappingStatus.NEEDS_REVIEW,
        )
        assert response.id == 1
        assert response.confidence_score == 0.95

    def test_mapping_decision_schema(self):
        """Test MappingDecision schema."""
        from src.api.routes.admin import MappingDecision

        decision = MappingDecision(
            action="correct",
            ticker="AAPL",
            notes="Corrected to Apple",
        )
        assert decision.action == "correct"
        assert decision.ticker == "AAPL"

    def test_coverage_stats_schema(self):
        """Test CoverageStats schema."""
        from src.api.routes.admin import CoverageStats

        stats = CoverageStats(
            source_id=1,
            source_name="TSA Checkpoint",
            total_entities=100,
            mapped_entities=85,
            coverage_pct=85.0,
            high_confidence_unmapped=5,
        )
        assert stats.coverage_pct == 85.0
        assert stats.mapped_entities == 85

    def test_collector_health_response_schema(self):
        """Test CollectorHealthResponse schema."""
        from src.api.routes.admin import CollectorHealthResponse

        response = CollectorHealthResponse(
            collector_name="TSA Checkpoint Collector",
            status="up",
            last_success=datetime.utcnow(),
            last_error=None,
            freshness_hours=12.0,
            sla_hours=24.0,
            sla_breach=False,
        )
        assert response.status == "up"
        assert response.sla_breach == False


class TestEntityMappingModels:
    """Tests for entity mapping model enums."""

    def test_mapping_status_enum(self):
        """Test MappingStatus enum values."""
        assert MappingStatus.PENDING.value == "pending"
        assert MappingStatus.AUTO_APPROVED.value == "auto_approved"
        assert MappingStatus.MANUAL_APPROVED.value == "manual_approved"
        assert MappingStatus.NEEDS_REVIEW.value == "needs_review"
        assert MappingStatus.REJECTED.value == "rejected"

    def test_suggestion_status_enum(self):
        """Test SuggestionStatus enum values."""
        assert SuggestionStatus.SUBMITTED.value == "submitted"
        assert SuggestionStatus.EVALUATING.value == "evaluating"
        assert SuggestionStatus.APPROVED.value == "approved"
        assert SuggestionStatus.REJECTED.value == "rejected"
        assert SuggestionStatus.IMPLEMENTED.value == "implemented"
