"""Stage 6 Tests: REST API verification."""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime


@pytest.fixture(scope="module")
def client():
    """Create test client."""
    from src.api.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def api_key():
    """Get test API key."""
    return "test-api-key"


def test_health_endpoint(client):
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "timestamp" in data
    assert data["version"] == "1.0.0"


def test_health_includes_redis(client):
    """Test health endpoint includes Redis status."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "redis" in data
    assert data["redis"] in ["connected", "disconnected"]


def test_list_factors(client, api_key):
    """Test listing factors."""
    response = client.get(
        "/api/v1/factors",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200

    data = response.json()
    assert "factors" in data
    assert "total" in data
    assert data["total"] >= 5  # We have at least 5 registered factors


def test_list_factors_filter_by_category(client, api_key):
    """Test filtering factors by category."""
    response = client.get(
        "/api/v1/factors",
        params={"category": "sec"},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200

    data = response.json()
    assert all(f["category"] == "sec" for f in data["factors"])


def test_list_factors_requires_auth():
    """Test that factor list requires authentication in production mode."""
    from src.api.main import app
    from src.config.settings import settings

    # Only test if not in development mode
    if not settings.is_development:
        with TestClient(app) as client:
            response = client.get("/api/v1/factors")
            assert response.status_code == 401


def test_get_factor_values(client, api_key):
    """Test getting factor values for an entity."""
    response = client.get(
        "/api/v1/factors/insider_transaction_momentum",
        params={"entity_id": "AAPL"},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200

    data = response.json()
    assert data["factor_name"] == "insider_transaction_momentum"
    assert data["entity_id"] == "AAPL"
    assert "values" in data
    assert "entity_type" in data


def test_get_factor_not_found(client, api_key):
    """Test 404 for unknown factor."""
    response = client.get(
        "/api/v1/factors/nonexistent_factor",
        params={"entity_id": "AAPL"},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 404


def test_get_factor_requires_entity_id(client, api_key):
    """Test that entity_id is required."""
    response = client.get(
        "/api/v1/factors/insider_transaction_momentum",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 422  # Validation error


def test_list_entities_empty(client, api_key):
    """Test listing entities when empty."""
    response = client.get(
        "/api/v1/entities",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200

    data = response.json()
    assert "entities" in data
    assert "total" in data
    assert data["page"] == 1


def test_list_entities_with_data(client, api_key):
    """Test listing entities with data in database."""
    from src.models.database import SessionLocal
    from src.models.schemas import Entity

    session = SessionLocal()
    try:
        # Add test entity
        entity = Entity(
            id="TEST_API",
            entity_type="company",
            name="Test API Company",
            ticker="TAPI",
        )
        session.add(entity)
        session.commit()

        # Query API
        response = client.get(
            "/api/v1/entities",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] >= 1

        # Cleanup
        session.delete(entity)
        session.commit()

    finally:
        session.close()


def test_list_entities_search(client, api_key):
    """Test entity search."""
    from src.models.database import SessionLocal
    from src.models.schemas import Entity

    session = SessionLocal()
    try:
        # Add test entity
        entity = Entity(
            id="SEARCHABLE",
            entity_type="company",
            name="Unique Searchable Company XYZ",
            ticker="SRCH",
        )
        session.add(entity)
        session.commit()

        # Search by name
        response = client.get(
            "/api/v1/entities",
            params={"search": "Searchable"},
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert any(e["id"] == "SEARCHABLE" for e in data["entities"])

        # Search by ticker
        response = client.get(
            "/api/v1/entities",
            params={"search": "SRCH"},
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert any(e["id"] == "SEARCHABLE" for e in data["entities"])

        # Cleanup
        session.delete(entity)
        session.commit()

    finally:
        session.close()


def test_get_entity(client, api_key):
    """Test getting single entity."""
    from src.models.database import SessionLocal
    from src.models.schemas import Entity

    session = SessionLocal()
    try:
        # Add test entity
        entity = Entity(
            id="GET_TEST",
            entity_type="company",
            name="Get Test Company",
            ticker="GETT",
            sector="Technology",
            industry="Software",
        )
        session.add(entity)
        session.commit()

        # Get by ID
        response = client.get(
            "/api/v1/entities/GET_TEST",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "GET_TEST"
        assert data["name"] == "Get Test Company"
        assert data["sector"] == "Technology"

        # Get by ticker
        response = client.get(
            "/api/v1/entities/GETT",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "GET_TEST"

        # Cleanup
        session.delete(entity)
        session.commit()

    finally:
        session.close()


def test_get_entity_not_found(client, api_key):
    """Test 404 for unknown entity."""
    response = client.get(
        "/api/v1/entities/NONEXISTENT",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 404


def test_list_sources(client, api_key):
    """Test listing data sources."""
    response = client.get(
        "/api/v1/sources",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200

    data = response.json()
    assert "sources" in data
    assert len(data["sources"]) >= 2

    # Check SEC EDGAR is listed
    sec = next((s for s in data["sources"] if s["id"] == "sec_edgar"), None)
    assert sec is not None
    assert sec["status"] == "active"


def test_invalid_api_key(client):
    """Test invalid API key rejection."""
    response = client.get(
        "/api/v1/factors",
        headers={"X-API-Key": "invalid-key"}
    )
    assert response.status_code == 401


def test_api_response_time():
    """Test API response time is reasonable."""
    import time
    from src.api.main import app

    with TestClient(app) as client:
        start = time.time()
        response = client.get("/health")
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 0.5  # Less than 500ms


def test_factor_with_stored_data(client, api_key):
    """Test factor endpoint with stored factor data."""
    from src.models.database import SessionLocal
    from src.models.schemas import Factor
    from datetime import datetime

    session = SessionLocal()
    try:
        # Add test factor value
        factor = Factor(
            factor_name="insider_transaction_momentum",
            entity_id="FACTOR_TEST",
            entity_type="company",
            value=123456.78,
            effective_date=datetime(2024, 1, 15),
            computed_at=datetime.utcnow(),
            version=1,
        )
        session.add(factor)
        session.commit()

        # Query API
        response = client.get(
            "/api/v1/factors/insider_transaction_momentum",
            params={
                "entity_id": "FACTOR_TEST",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["factor_name"] == "insider_transaction_momentum"
        assert len(data["values"]) >= 1
        assert any(v["value"] == 123456.78 for v in data["values"])

        # Cleanup
        session.delete(factor)
        session.commit()

    finally:
        session.close()
