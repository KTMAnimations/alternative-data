"""Pytest configuration and shared fixtures."""

import os
import pytest
from typing import Generator
from fastapi.testclient import TestClient


# Set test environment before imports
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "postgresql://postgres:devpassword@localhost:5432/altdata_dev"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["USE_LOCAL_STORAGE"] = "true"
os.environ["SKIP_RATE_LIMITS"] = "true"
os.environ["API_KEY_DEFAULT"] = "test-api-key"
os.environ["API_KEY_ADMIN"] = "admin-test-key-12345"

# Import all models to ensure SQLAlchemy relationships are properly configured
# This must happen before any model instantiation in tests
from src.auth.models import User  # noqa: F401 - Required for APIKey relationship
from src.models.database import Base  # noqa: F401


@pytest.fixture(scope="session")
def api_key() -> str:
    """Get test API key."""
    return "test-api-key"


@pytest.fixture(scope="session")
def api_client() -> Generator[TestClient, None, None]:
    """Create FastAPI test client."""
    from src.api.main import app
    
    with TestClient(app) as client:
        yield client


@pytest.fixture
def authenticated_client(api_client: TestClient, api_key: str) -> TestClient:
    """Client with API key header set."""
    api_client.headers["X-API-Key"] = api_key
    return api_client


@pytest.fixture(scope="session")
def db_engine():
    """Create test database engine.

    Note: Requires PostgreSQL to be running with test database created.
    """
    from sqlalchemy import create_engine

    test_db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:devpassword@localhost:5432/altdata_dev"
    )

    engine = create_engine(test_db_url, echo=False)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Create database session for test.
    
    Each test gets a fresh session that's rolled back after.
    """
    from sqlalchemy.orm import sessionmaker
    
    Session = sessionmaker(bind=db_engine)
    session = Session()
    
    yield session
    
    session.rollback()
    session.close()


@pytest.fixture
def sample_form4_xml() -> str:
    """Sample SEC Form 4 XML for testing."""
    return '''<?xml version="1.0"?>
<ownershipDocument>
    <schemaVersion>X0306</schemaVersion>
    <documentType>4</documentType>
    <periodOfReport>2024-01-15</periodOfReport>
    <issuer>
        <issuerCik>0001318605</issuerCik>
        <issuerName>Tesla, Inc.</issuerName>
        <issuerTradingSymbol>TSLA</issuerTradingSymbol>
    </issuer>
    <reportingOwner>
        <reportingOwnerId>
            <rptOwnerCik>0001494730</rptOwnerCik>
            <rptOwnerName>Musk Elon</rptOwnerName>
        </reportingOwnerId>
        <reportingOwnerAddress>
            <rptOwnerCity>Austin</rptOwnerCity>
            <rptOwnerState>TX</rptOwnerState>
        </reportingOwnerAddress>
        <reportingOwnerRelationship>
            <isDirector>1</isDirector>
            <isOfficer>1</isOfficer>
            <officerTitle>CEO</officerTitle>
        </reportingOwnerRelationship>
    </reportingOwner>
    <nonDerivativeTable>
        <nonDerivativeTransaction>
            <securityTitle>
                <value>Common Stock</value>
            </securityTitle>
            <transactionDate>
                <value>2024-01-15</value>
            </transactionDate>
            <transactionCoding>
                <transactionFormType>4</transactionFormType>
                <transactionCode>P</transactionCode>
                <equitySwapInvolved>0</equitySwapInvolved>
            </transactionCoding>
            <transactionAmounts>
                <transactionShares>
                    <value>10000</value>
                </transactionShares>
                <transactionPricePerShare>
                    <value>250.00</value>
                </transactionPricePerShare>
                <transactionAcquiredDisposedCode>
                    <value>A</value>
                </transactionAcquiredDisposedCode>
            </transactionAmounts>
            <postTransactionAmounts>
                <sharesOwnedFollowingTransaction>
                    <value>500000000</value>
                </sharesOwnedFollowingTransaction>
            </postTransactionAmounts>
            <ownershipNature>
                <directOrIndirectOwnership>
                    <value>D</value>
                </directOrIndirectOwnership>
            </ownershipNature>
        </nonDerivativeTransaction>
    </nonDerivativeTable>
</ownershipDocument>'''


@pytest.fixture
def sample_fred_response() -> dict:
    """Sample FRED API response for testing."""
    return {
        "realtime_start": "2024-01-01",
        "realtime_end": "2024-01-26",
        "observation_start": "2024-01-01",
        "observation_end": "2024-01-26",
        "units": "lin",
        "output_type": 1,
        "file_type": "json",
        "order_by": "observation_date",
        "sort_order": "asc",
        "count": 5,
        "offset": 0,
        "limit": 100000,
        "observations": [
            {"realtime_start": "2024-01-26", "realtime_end": "2024-01-26", "date": "2024-01-19", "value": "4.12"},
            {"realtime_start": "2024-01-26", "realtime_end": "2024-01-26", "date": "2024-01-22", "value": "4.15"},
            {"realtime_start": "2024-01-26", "realtime_end": "2024-01-26", "date": "2024-01-23", "value": "4.10"},
            {"realtime_start": "2024-01-26", "realtime_end": "2024-01-26", "date": "2024-01-24", "value": "4.08"},
            {"realtime_start": "2024-01-26", "realtime_end": "2024-01-26", "date": "2024-01-25", "value": "4.14"},
        ]
    }


@pytest.fixture
def mock_entity() -> dict:
    """Sample entity data for testing."""
    return {
        "id": "AAPL",
        "entity_type": "company",
        "name": "Apple Inc.",
        "ticker": "AAPL",
        "cik": "0000320193",
        "sector": "Technology",
        "industry": "Consumer Electronics",
    }


@pytest.fixture
def mock_transactions() -> list:
    """Sample insider transactions for testing."""
    return [
        {
            "cik": "0000320193",
            "ticker": "AAPL",
            "insider_name": "Tim Cook",
            "transaction_type": "S",  # Sale
            "shares": 50000,
            "price_per_share": 185.50,
            "transaction_date": "2024-01-15",
        },
        {
            "cik": "0000320193",
            "ticker": "AAPL",
            "insider_name": "Luca Maestri",
            "transaction_type": "S",  # Sale
            "shares": 10000,
            "price_per_share": 186.00,
            "transaction_date": "2024-01-14",
        },
        {
            "cik": "0000320193",
            "ticker": "AAPL",
            "insider_name": "Katherine Adams",
            "transaction_type": "P",  # Purchase
            "shares": 5000,
            "price_per_share": 183.00,
            "transaction_date": "2024-01-12",
        },
    ]


# ===========================================
# MARKERS
# ===========================================

# ===========================================
# AUTH FIXTURES
# ===========================================

@pytest.fixture
def test_user_data() -> dict:
    """Test user registration data."""
    return {
        "email": "test@example.com",
        "password": "TestPassword123",
        "full_name": "Test User",
    }


@pytest.fixture
def create_test_user(api_client: TestClient, test_user_data: dict):
    """Create a test user and return user data."""
    response = api_client.post("/api/v1/auth/register", json=test_user_data)
    if response.status_code == 200:
        return response.json()
    # User might already exist, try to get via login
    return None


@pytest.fixture
def auth_tokens(api_client: TestClient, test_user_data: dict) -> dict:
    """Get auth tokens for test user."""
    # First register (ignore if already exists)
    api_client.post("/api/v1/auth/register", json=test_user_data)

    # Login to get tokens
    login_data = {
        "username": test_user_data["email"],
        "password": test_user_data["password"],
    }
    response = api_client.post(
        "/api/v1/auth/login",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return response.json()


@pytest.fixture
def auth_headers(auth_tokens: dict) -> dict:
    """Get authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {auth_tokens['access_token']}"}


@pytest.fixture
def jwt_authenticated_client(api_client: TestClient, auth_headers: dict) -> TestClient:
    """Client with JWT auth header set."""
    api_client.headers.update(auth_headers)
    return api_client


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )
    config.addinivalue_line(
        "markers", "auth: marks tests as authentication tests"
    )
