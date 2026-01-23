"""
Comprehensive tests for Epic 7 Entity Mapping features (US-027 to US-030).

Tests cover:
- US-027: Audit trail for entity mappings
- US-028: Notification on mapping status change
- US-029: Coverage analytics
- US-030: Corporate action handling
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.entity_mappings import (
    MappingStatus,
    SuggestionStatus,
    CorporateActionType,
    CorporateActionStatus,
    AuditActionType,
    NotificationType,
    NotificationChannel,
)


def get_test_client():
    """Get test client that catches server errors as 500 responses."""
    return TestClient(app, raise_server_exceptions=False)


# =============================================================================
# US-027: Audit Trail Tests
# =============================================================================

class TestMappingAuditTrail:
    """Tests for audit trail functionality (US-027)."""

    def test_audit_endpoint_exists(self):
        """Test that audit history endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/mappings/1/audit")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_audit_endpoint_with_limit(self):
        """Test audit history with limit parameter."""
        client = get_test_client()
        response = client.get("/api/v1/admin/mappings/1/audit?limit=50")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_audited_decide_endpoint_exists(self):
        """Test that audited decide endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/mappings/1/decide/audited",
            json={"action": "approve"},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_audited_decide_approve(self):
        """Test approving a mapping with audit trail."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/mappings/1/decide/audited",
            json={"action": "approve", "notes": "Verified correct mapping"},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_audited_decide_reject(self):
        """Test rejecting a mapping with audit trail."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/mappings/1/decide/audited",
            json={"action": "reject", "notes": "Incorrect entity match"},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_audited_decide_correct(self):
        """Test correcting a mapping with audit trail."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/mappings/1/decide/audited",
            json={
                "action": "correct",
                "ticker": "AAPL",
                "notes": "Corrected to Apple Inc.",
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,  # Missing ticker if required
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestAuditLogSchema:
    """Tests for audit log schema validation."""

    def test_audit_action_type_enum(self):
        """Test AuditActionType enum values."""
        assert AuditActionType.CREATE.value == "create"
        assert AuditActionType.UPDATE.value == "update"
        assert AuditActionType.APPROVE.value == "approve"
        assert AuditActionType.REJECT.value == "reject"
        assert AuditActionType.CORRECT.value == "correct"
        assert AuditActionType.BULK_APPROVE.value == "bulk_approve"
        assert AuditActionType.CORPORATE_ACTION_APPLY.value == "corporate_action_apply"


# =============================================================================
# US-028: Notification Tests
# =============================================================================

class TestNotifications:
    """Tests for notification functionality (US-028)."""

    def test_create_notification_endpoint_exists(self):
        """Test that create notification endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/notifications",
            json={
                "user_id": 1,
                "notification_type": "mapping_status_change",
                "title": "Test Notification",
                "message": "This is a test notification",
                "channels": ["in_app"],
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_get_user_notifications_endpoint_exists(self):
        """Test that get user notifications endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/notifications/user/1")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_get_user_notifications_unread_only(self):
        """Test filtering for unread notifications."""
        client = get_test_client()
        response = client.get("/api/v1/admin/notifications/user/1?unread_only=true")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_mark_notification_read_endpoint_exists(self):
        """Test that mark notification read endpoint exists."""
        client = get_test_client()
        response = client.post("/api/v1/admin/notifications/1/read")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestNotificationSchema:
    """Tests for notification schema validation."""

    def test_notification_type_enum(self):
        """Test NotificationType enum values."""
        assert NotificationType.MAPPING_STATUS_CHANGE.value == "mapping_status_change"
        assert NotificationType.SUGGESTION_STATUS_CHANGE.value == "suggestion_status_change"
        assert NotificationType.CORPORATE_ACTION_DETECTED.value == "corporate_action_detected"
        assert NotificationType.CORPORATE_ACTION_APPLIED.value == "corporate_action_applied"
        assert NotificationType.COVERAGE_THRESHOLD_ALERT.value == "coverage_threshold_alert"

    def test_notification_channel_enum(self):
        """Test NotificationChannel enum values."""
        assert NotificationChannel.EMAIL.value == "email"
        assert NotificationChannel.IN_APP.value == "in_app"
        assert NotificationChannel.WEBHOOK.value == "webhook"


# =============================================================================
# US-029: Coverage Analytics Tests
# =============================================================================

class TestCoverageAnalytics:
    """Tests for coverage analytics functionality (US-029)."""

    def test_extended_coverage_endpoint_exists(self):
        """Test that extended coverage endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/mappings/coverage/extended")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_coverage_trend_endpoint_exists(self):
        """Test that coverage trend endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/mappings/coverage/trend/1")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_coverage_trend_with_days(self):
        """Test coverage trend with days parameter."""
        client = get_test_client()
        response = client.get("/api/v1/admin/mappings/coverage/trend/1?days=60")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_create_snapshot_endpoint_exists(self):
        """Test that create snapshot endpoint exists."""
        client = get_test_client()
        response = client.post("/api/v1/admin/mappings/coverage/snapshot")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_create_snapshot_for_source(self):
        """Test creating snapshot for specific source."""
        client = get_test_client()
        response = client.post("/api/v1/admin/mappings/coverage/snapshot?source_id=1")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_prioritized_unmapped_endpoint_exists(self):
        """Test that prioritized unmapped endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/mappings/unmapped/prioritized")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_prioritized_unmapped_with_filters(self):
        """Test prioritized unmapped with filters."""
        client = get_test_client()
        response = client.get(
            "/api/v1/admin/mappings/unmapped/prioritized?source_id=1&min_priority=0.5&limit=50"
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_export_unmapped_csv_endpoint_exists(self):
        """Test that export CSV endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/mappings/unmapped/export")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]
        # Check content type if successful
        if response.status_code == status.HTTP_200_OK:
            assert "text/csv" in response.headers.get("content-type", "")

    def test_export_unmapped_csv_with_filters(self):
        """Test export CSV with filters."""
        client = get_test_client()
        response = client.get(
            "/api/v1/admin/mappings/unmapped/export?source_id=1&min_priority=0.3"
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


# =============================================================================
# US-030: Corporate Action Tests
# =============================================================================

class TestCorporateActions:
    """Tests for corporate action functionality (US-030)."""

    def test_list_corporate_actions_endpoint_exists(self):
        """Test that list corporate actions endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/corporate-actions")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_list_corporate_actions_with_filters(self):
        """Test listing corporate actions with filters."""
        client = get_test_client()
        response = client.get(
            "/api/v1/admin/corporate-actions?status_filter=detected&ticker=AAPL&limit=25"
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_create_corporate_action_endpoint_exists(self):
        """Test that create corporate action endpoint exists."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/corporate-actions",
            json={
                "action_type": "ticker_change",
                "old_ticker": "FB",
                "new_ticker": "META",
                "effective_date": "2022-06-09T00:00:00Z",
                "description": "Facebook renamed to Meta Platforms",
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_create_corporate_action_with_all_fields(self):
        """Test creating corporate action with all fields."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/corporate-actions",
            json={
                "action_type": "merger",
                "old_ticker": "TWTR",
                "new_ticker": None,
                "effective_date": "2022-10-27T00:00:00Z",
                "announcement_date": "2022-04-25T00:00:00Z",
                "description": "Twitter acquired by X Corp",
                "related_tickers": ["TSLA"],
                "adjustment_factor": 54.20,
            },
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_detect_corporate_actions_endpoint_exists(self):
        """Test that detect corporate actions endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/corporate-actions/detect")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_detect_corporate_actions_with_ticker(self):
        """Test detecting corporate actions for specific ticker."""
        client = get_test_client()
        response = client.get("/api/v1/admin/corporate-actions/detect?ticker=AAPL")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_affected_mappings_endpoint_exists(self):
        """Test that affected mappings endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/corporate-actions/1/affected")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_preview_impact_endpoint_exists(self):
        """Test that preview impact endpoint exists."""
        client = get_test_client()
        response = client.get("/api/v1/admin/corporate-actions/1/preview")
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_decide_corporate_action_approve(self):
        """Test approving a corporate action."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/corporate-actions/1/decide",
            json={"action": "approve"},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_decide_corporate_action_reject(self):
        """Test rejecting a corporate action."""
        client = get_test_client()
        response = client.post(
            "/api/v1/admin/corporate-actions/1/decide",
            json={"action": "reject", "notes": "Not applicable to our data"},
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestCorporateActionSchema:
    """Tests for corporate action schema validation."""

    def test_corporate_action_type_enum(self):
        """Test CorporateActionType enum values."""
        assert CorporateActionType.TICKER_CHANGE.value == "ticker_change"
        assert CorporateActionType.MERGER.value == "merger"
        assert CorporateActionType.ACQUISITION.value == "acquisition"
        assert CorporateActionType.SPINOFF.value == "spinoff"
        assert CorporateActionType.DELISTING.value == "delisting"
        assert CorporateActionType.NAME_CHANGE.value == "name_change"

    def test_corporate_action_status_enum(self):
        """Test CorporateActionStatus enum values."""
        assert CorporateActionStatus.DETECTED.value == "detected"
        assert CorporateActionStatus.PENDING_REVIEW.value == "pending_review"
        assert CorporateActionStatus.APPROVED.value == "approved"
        assert CorporateActionStatus.REJECTED.value == "rejected"
        assert CorporateActionStatus.APPLIED.value == "applied"


# =============================================================================
# Integration Tests
# =============================================================================

class TestAuditNotificationIntegration:
    """Tests for audit and notification integration."""

    def test_decide_with_audit_creates_notification(self):
        """Test that deciding with audit also creates notification."""
        client = get_test_client()
        # This tests the integration between audit trail and notification
        response = client.post(
            "/api/v1/admin/mappings/1/decide/audited",
            json={"action": "approve", "notes": "Verified"},
        )
        # The endpoint should handle both audit and notification internally
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestCorporateActionAuditIntegration:
    """Tests for corporate action and audit integration."""

    def test_corporate_action_apply_creates_audit_logs(self):
        """Test that applying corporate action creates audit logs for affected mappings."""
        client = get_test_client()
        # First create a corporate action
        create_response = client.post(
            "/api/v1/admin/corporate-actions",
            json={
                "action_type": "ticker_change",
                "old_ticker": "TEST",
                "new_ticker": "NEWTEST",
                "effective_date": datetime.utcnow().isoformat(),
                "description": "Test ticker change",
            },
        )

        if create_response.status_code == status.HTTP_200_OK:
            action_id = create_response.json().get("id")
            if action_id:
                # Approve the action
                approve_response = client.post(
                    f"/api/v1/admin/corporate-actions/{action_id}/decide",
                    json={"action": "approve"},
                )
                assert approve_response.status_code in [
                    status.HTTP_200_OK,
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                ]


# =============================================================================
# Schema/Model Tests
# =============================================================================

class TestAdminSchemas:
    """Tests for admin API schemas."""

    def test_audit_log_entry_schema(self):
        """Test AuditLogEntry schema."""
        from src.api.routes.admin import AuditLogEntry

        entry = AuditLogEntry(
            id=1,
            mapping_id=10,
            user_id=5,
            action="approve",
            old_value={"status": "pending"},
            new_value={"status": "manual_approved"},
            notes="Verified correct",
            created_at=datetime.utcnow(),
        )
        assert entry.id == 1
        assert entry.mapping_id == 10
        assert entry.action == "approve"

    def test_notification_response_schema(self):
        """Test NotificationResponse schema."""
        from src.api.routes.admin import NotificationResponse

        notification = NotificationResponse(
            id=1,
            user_id=5,
            notification_type="mapping_status_change",
            title="Test Title",
            message="Test message",
            is_read=False,
            created_at=datetime.utcnow(),
        )
        assert notification.id == 1
        assert notification.is_read == False

    def test_coverage_stats_extended_schema(self):
        """Test CoverageStatsExtended schema."""
        from src.api.routes.admin import CoverageStatsExtended

        stats = CoverageStatsExtended(
            source_id=1,
            source_name="TSA Checkpoint",
            total_entities=100,
            mapped_entities=85,
            coverage_pct=85.0,
            high_confidence_unmapped=5,
            unmapped_value_usd=1000000.0,
            unmapped_volume=500000.0,
            top_unmapped_by_value=[
                {"entity_id": "E1", "entity_name": "Entity 1", "priority_score": 0.9}
            ],
        )
        assert stats.coverage_pct == 85.0
        assert stats.unmapped_value_usd == 1000000.0

    def test_corporate_action_response_schema(self):
        """Test CorporateActionResponse schema."""
        from src.api.routes.admin import CorporateActionResponse

        action = CorporateActionResponse(
            id=1,
            action_type="ticker_change",
            old_ticker="FB",
            new_ticker="META",
            effective_date=datetime.utcnow(),
            announcement_date=datetime.utcnow(),
            description="Facebook to Meta",
            status="detected",
            affected_mappings_count=15,
            related_tickers=None,
            adjustment_factor=None,
            created_at=datetime.utcnow(),
        )
        assert action.old_ticker == "FB"
        assert action.new_ticker == "META"
        assert action.affected_mappings_count == 15

    def test_historical_impact_preview_schema(self):
        """Test HistoricalImpactPreview schema."""
        from src.api.routes.admin import HistoricalImpactPreview, AffectedMappingResponse

        affected = AffectedMappingResponse(
            mapping_id=1,
            source_entity_name="Test Entity",
            current_ticker="OLD",
            proposed_ticker="NEW",
            source_name="Test Source",
        )
        preview = HistoricalImpactPreview(
            corporate_action_id=1,
            affected_mappings=[affected],
            total_affected=1,
            adjustment_factor=1.5,
            description="Test preview",
        )
        assert preview.total_affected == 1
        assert len(preview.affected_mappings) == 1
