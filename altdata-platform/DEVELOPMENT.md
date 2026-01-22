# Development Guide

This document covers setting up your development environment, coding standards, testing practices, and contribution guidelines.

## Prerequisites

### Required Software
- Python 3.11 or higher
- PostgreSQL 15+ with TimescaleDB extension
- Redis 7+
- Node.js 18+ (for dashboard)
- Docker & Docker Compose (recommended)
- Git

### Optional but Recommended
- pyenv (Python version management)
- nvm (Node.js version management)
- VS Code or PyCharm

## Environment Setup

### Option 1: Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps

# View logs
docker-compose logs -f api
```

### Option 2: Manual Setup

#### 1. Python Environment
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

#### 2. PostgreSQL + TimescaleDB
```bash
# Using Docker
docker run -d --name timescaledb \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=devpassword \
  timescale/timescaledb:latest-pg15

# Or install locally and add TimescaleDB extension
# See: https://docs.timescale.com/install/
```

#### 3. Redis
```bash
# Using Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Or install locally
# See: https://redis.io/docs/getting-started/
```

#### 4. Environment Variables
```bash
# Copy template
cp .env.example .env

# Edit with your values
vim .env
```

#### 5. Database Setup
```bash
# Create database
createdb altdata_dev

# Run migrations
alembic upgrade head

# Seed reference data
python scripts/seed_data.py
```

## Project Configuration

### Environment Variables (.env)

```bash
# Core Settings
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Database
DATABASE_URL=postgresql://postgres:devpassword@localhost:5432/altdata_dev
DATABASE_POOL_SIZE=5

# Redis
REDIS_URL=redis://localhost:6379/0

# AWS/GCS (for data lake)
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
S3_BUCKET=altdata-dev-raw
AWS_REGION=us-east-1

# External APIs
SEC_EDGAR_USER_AGENT=YourName your@email.com
FRED_API_KEY=your-fred-api-key
ADSB_EXCHANGE_API_KEY=your-adsb-key

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=true
```

## Running the Application

### Start API Server
```bash
# Development mode with auto-reload
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Or use the convenience script
python -m src.api.run
```

### Start Collectors
```bash
# Run all collectors
python -m src.collectors.run_all

# Run specific collector
python -m src.collectors.sec_edgar

# Run with Airflow (production-like)
airflow standalone  # Development mode
```

### Start Dashboard
```bash
cd dashboard
npm install
npm run dev
```

## Testing

### Test Structure
```
tests/
├── conftest.py           # Shared fixtures
├── unit/                 # Unit tests
│   ├── test_collectors/
│   ├── test_transformations/
│   └── test_api/
├── integration/          # Integration tests
│   ├── test_database.py
│   └── test_api_endpoints.py
└── e2e/                  # End-to-end tests
    └── test_factor_pipeline.py
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_collectors/test_sec_edgar.py

# Run tests matching pattern
pytest -k "test_insider"

# Run only unit tests
pytest tests/unit/

# Run with verbose output
pytest -v

# Run and stop on first failure
pytest -x
```

### Writing Tests
```python
# tests/unit/test_collectors/test_sec_edgar.py
import pytest
from unittest.mock import Mock, patch
from src.collectors.sec_edgar import SECEdgarCollector

@pytest.fixture
def collector():
    """Create collector instance for testing."""
    return SECEdgarCollector(api_key="test-key")

@pytest.fixture
def sample_form4_xml():
    """Sample Form 4 XML response."""
    return """<?xml version="1.0"?>
    <ownershipDocument>...</ownershipDocument>
    """

class TestSECEdgarCollector:
    """Tests for SEC EDGAR collector."""
    
    def test_parse_form4_valid(self, collector, sample_form4_xml):
        """Test parsing valid Form 4 XML."""
        result = collector.parse_form4(sample_form4_xml)
        
        assert result.issuer_cik == "0001318605"
        assert result.transaction_type == "P"
        assert result.shares > 0
    
    def test_parse_form4_missing_fields(self, collector):
        """Test handling of missing required fields."""
        invalid_xml = "<ownershipDocument></ownershipDocument>"
        
        with pytest.raises(ValidationError):
            collector.parse_form4(invalid_xml)
    
    @patch('src.collectors.sec_edgar.requests.get')
    async def test_fetch_filings(self, mock_get, collector):
        """Test fetching filings from SEC API."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {...}
        
        filings = await collector.fetch()
        
        assert len(filings) > 0
        mock_get.assert_called_once()
```

### Test Fixtures
```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session")
def test_db():
    """Create test database."""
    engine = create_engine("postgresql://localhost/altdata_test")
    # Setup tables
    yield engine
    # Cleanup

@pytest.fixture
def db_session(test_db):
    """Create database session for test."""
    Session = sessionmaker(bind=test_db)
    session = Session()
    yield session
    session.rollback()
    session.close()

@pytest.fixture
def api_client():
    """Create FastAPI test client."""
    from fastapi.testclient import TestClient
    from src.api.main import app
    return TestClient(app)
```

## Code Style

### Python Style Guide
- Follow PEP 8
- Use type hints for all functions
- Maximum line length: 100 characters
- Use docstrings (Google style)

### Linting & Formatting
```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint
flake8 src/ tests/
mypy src/

# Run all checks
pre-commit run --all-files
```

### Example Code Style
```python
"""Module for SEC EDGAR data collection.

This module provides collectors for various SEC filing types
including Form 4 (insider transactions) and Form 8-K (material events).
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.collectors.base import BaseCollector
from src.models.schemas import Form4Transaction


@dataclass
class Form4Filing:
    """Represents a parsed Form 4 filing.
    
    Attributes:
        cik: Central Index Key of the issuer.
        filed_date: Date the form was filed.
        transactions: List of transactions in the filing.
    """
    cik: str
    filed_date: date
    transactions: list[Form4Transaction]


class SECEdgarCollector(BaseCollector):
    """Collector for SEC EDGAR filings.
    
    This collector fetches and parses SEC filings, supporting Form 4
    (insider transactions), Form 8-K (material events), and 10-K/10-Q
    (annual/quarterly reports).
    
    Example:
        >>> collector = SECEdgarCollector(user_agent="YourName email@example.com")
        >>> filings = await collector.fetch_form4_filings(cik="0001318605")
        >>> for filing in filings:
        ...     print(filing.transactions)
    """
    
    BASE_URL = "https://www.sec.gov"
    
    def __init__(self, user_agent: str, rate_limit: float = 0.1) -> None:
        """Initialize the collector.
        
        Args:
            user_agent: Required by SEC. Format: "Name email@example.com".
            rate_limit: Seconds between requests (SEC limit: 10/sec).
        """
        self.user_agent = user_agent
        self.rate_limit = rate_limit
    
    async def fetch_form4_filings(
        self,
        cik: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[Form4Filing]:
        """Fetch Form 4 filings for a company.
        
        Args:
            cik: Central Index Key of the company.
            start_date: Start of date range (inclusive).
            end_date: End of date range (inclusive).
            
        Returns:
            List of Form4Filing objects.
            
        Raises:
            RateLimitError: If SEC rate limit exceeded.
            ValidationError: If response format unexpected.
        """
        # Implementation here
        pass
```

## Database Migrations

### Creating Migrations
```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add new column to factors"

# Create empty migration for manual SQL
alembic revision -m "Custom data migration"
```

### Running Migrations
```bash
# Upgrade to latest
alembic upgrade head

# Upgrade to specific version
alembic upgrade abc123

# Downgrade one version
alembic downgrade -1

# Show current version
alembic current

# Show migration history
alembic history
```

## Adding a New Data Source

### 1. Create Collector
```python
# src/collectors/new_source.py
from src.collectors.base import BaseCollector

class NewSourceCollector(BaseCollector):
    """Collector for New Data Source."""
    
    SOURCE_NAME = "new_source"
    
    async def fetch(self) -> RawData:
        # Implement data fetching
        pass
    
    def parse(self, raw: RawData) -> ParsedData:
        # Implement parsing
        pass
```

### 2. Create Tests
```python
# tests/unit/test_collectors/test_new_source.py
class TestNewSourceCollector:
    def test_fetch_success(self):
        pass
    
    def test_parse_valid_data(self):
        pass
```

### 3. Create Database Models
```python
# src/models/new_source.py
from sqlalchemy import Column, String, Float, DateTime
from src.models.base import Base

class NewSourceData(Base):
    __tablename__ = "new_source_data"
    
    id = Column(Integer, primary_key=True)
    # ... fields
```

### 4. Create Migration
```bash
alembic revision --autogenerate -m "Add new_source_data table"
alembic upgrade head
```

### 5. Create Factors
```python
# src/transformations/factors/new_source_factors.py
from src.transformations.base import factor

@factor(name="new_factor", entity_type="company")
def calc_new_factor(entity_id: str, date: date, ctx: FactorContext) -> float:
    # Implement factor calculation
    pass
```

### 6. Register in API
```python
# src/api/routes/factors.py
# Factor is auto-discovered from decorator
```

### 7. Update Documentation
- Add to DATA_SOURCES.md
- Update README.md with new factor count
- Add to API documentation

## Debugging

### Logging
```python
import logging

logger = logging.getLogger(__name__)

# Use structured logging
logger.info("Processing filing", extra={
    "cik": cik,
    "filing_type": "Form 4",
    "transaction_count": len(transactions)
})
```

### Database Queries
```python
# Enable SQL logging
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)

# Or in .env
DATABASE_ECHO=true
```

### API Debugging
```bash
# Interactive API docs
open http://localhost:8000/docs

# Request debugging
curl -v http://localhost:8000/api/v1/factors/insider_momentum?ticker=AAPL
```

## Performance Profiling

```python
# Profile a function
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()
# ... code to profile
profiler.disable()

stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

## Troubleshooting

### Common Issues

**Database connection refused**
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Check Docker container
docker ps | grep timescaledb
```

**Redis connection failed**
```bash
# Check Redis is running
redis-cli ping
```

**API rate limit errors**
- Check collector rate limiting configuration
- Verify API keys are valid
- Review external API documentation for limits

**Factor computation errors**
- Check input data availability
- Verify entity mapping exists
- Review factor dependencies
