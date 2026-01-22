# Implementation Prompt for Alternative Data Platform MVP

Use this prompt with Claude or another AI coding assistant to implement the MVP of the Alternative Data Platform. The prompt instructs the agent to work iteratively, testing at each stage.

---

## The Prompt

Copy and paste the following prompt to begin implementation:

```
You are implementing the MVP of an Alternative Data Platform for quantitative trading. This is a comprehensive project that will be built iteratively with testing at each stage.

## Project Overview
Build a platform that:
1. Collects data from SEC EDGAR, ADS-B Exchange, and FRED
2. Transforms raw data into quantitative factors
3. Serves factors via a REST API
4. Displays data in a web dashboard

## Implementation Approach
- Work in focused stages, completing one before moving to the next
- After each stage, verify functionality with tests before proceeding
- If tests fail, debug and fix before continuing
- Commit working code at each checkpoint

## Your Working Loop
For each stage:
1. READ: Review the stage requirements
2. IMPLEMENT: Write the code
3. TEST: Run tests to verify
4. FIX: If tests fail, diagnose and fix
5. VERIFY: Confirm everything works
6. PROCEED: Move to next stage only when current stage is complete

---

## STAGE 1: Project Setup & Infrastructure
**Goal:** Set up the development environment and verify all dependencies work.

### Tasks:
1. Create Python virtual environment with Python 3.11+
2. Install core dependencies (see requirements below)
3. Set up PostgreSQL database with TimescaleDB extension
4. Set up Redis for caching
5. Create project directory structure
6. Create configuration management

### Required Directory Structure:
```
altdata-platform/
├── src/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── collectors/
│   │   ├── __init__.py
│   │   └── base.py
│   ├── transformations/
│   │   ├── __init__.py
│   │   └── base.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── main.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── database.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── tests/
│   ├── __init__.py
│   └── conftest.py
├── scripts/
│   └── init_db.py
├── requirements.txt
└── .env
```

### Key Dependencies:
```
fastapi>=0.104.0
uvicorn>=0.24.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
redis>=5.0.0
httpx>=0.25.0
pandas>=2.1.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
pytest>=7.4.0
pytest-asyncio>=0.21.0
alembic>=1.12.0
```

### Verification Tests:
```python
# tests/test_stage1.py
import pytest

def test_database_connection():
    """Verify PostgreSQL connection works."""
    from src.models.database import get_db_connection
    conn = get_db_connection()
    result = conn.execute("SELECT 1")
    assert result.fetchone()[0] == 1
    conn.close()

def test_redis_connection():
    """Verify Redis connection works."""
    from src.config.settings import settings
    import redis
    r = redis.from_url(settings.redis_url)
    r.set("test_key", "test_value")
    assert r.get("test_key") == b"test_value"
    r.delete("test_key")

def test_config_loaded():
    """Verify configuration loads correctly."""
    from src.config.settings import settings
    assert settings.database_url is not None
    assert settings.redis_url is not None
```

**Checkpoint 1:** All tests pass, database and Redis are connected.

---

## STAGE 2: Database Models & Migrations
**Goal:** Create database schema for storing raw data and computed factors.

### Tasks:
1. Create SQLAlchemy models for:
   - `raw_data_catalog` - tracks raw data files
   - `factors` - stores computed factor values
   - `entities` - company/ticker mapping
   - `sec_form4_transactions` - parsed insider transactions
2. Create Alembic migrations
3. Initialize database with schema

### Models to Create:

```python
# src/models/schemas.py
from sqlalchemy import Column, String, Float, DateTime, Integer, BigInteger, ARRAY, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class RawDataCatalog(Base):
    __tablename__ = "raw_data_catalog"
    id = Column(BigInteger, primary_key=True)
    source = Column(String(50), nullable=False)
    file_path = Column(String, nullable=False)
    fetch_timestamp = Column(DateTime(timezone=True), nullable=False)
    data_timestamp = Column(DateTime(timezone=True))
    checksum = Column(String(64), nullable=False)
    record_count = Column(Integer)
    metadata = Column(JSON)

class Factor(Base):
    __tablename__ = "factors"
    id = Column(BigInteger, primary_key=True)
    factor_name = Column(String(100), nullable=False, index=True)
    entity_id = Column(String(50), nullable=False, index=True)
    entity_type = Column(String(20), nullable=False)
    value = Column(Float)
    effective_date = Column(DateTime, nullable=False)
    computed_at = Column(DateTime(timezone=True), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    source_data_ids = Column(ARRAY(BigInteger))
    metadata = Column(JSON)

class Entity(Base):
    __tablename__ = "entities"
    id = Column(String(50), primary_key=True)
    entity_type = Column(String(20), nullable=False)
    name = Column(String(255), nullable=False)
    ticker = Column(String(20), index=True)
    cik = Column(String(20), index=True)
    aliases = Column(JSON)
    metadata = Column(JSON)

class SECForm4Transaction(Base):
    __tablename__ = "sec_form4_transactions"
    id = Column(BigInteger, primary_key=True)
    cik = Column(String(20), nullable=False, index=True)
    ticker = Column(String(20), index=True)
    insider_name = Column(String(255))
    insider_title = Column(String(100))
    transaction_type = Column(String(10))  # P=Purchase, S=Sale
    shares = Column(Float)
    price = Column(Float)
    transaction_date = Column(DateTime)
    filed_date = Column(DateTime)
    raw_data_id = Column(BigInteger)
```

### Verification Tests:
```python
# tests/test_stage2.py
def test_tables_created():
    """Verify all tables exist."""
    from src.models.database import engine
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    assert "raw_data_catalog" in tables
    assert "factors" in tables
    assert "entities" in tables
    assert "sec_form4_transactions" in tables

def test_can_insert_entity():
    """Verify entity insertion works."""
    from src.models.database import SessionLocal
    from src.models.schemas import Entity
    
    session = SessionLocal()
    entity = Entity(
        id="AAPL",
        entity_type="company",
        name="Apple Inc.",
        ticker="AAPL",
        cik="0000320193"
    )
    session.add(entity)
    session.commit()
    
    result = session.query(Entity).filter_by(id="AAPL").first()
    assert result.name == "Apple Inc."
    session.delete(result)
    session.commit()
    session.close()
```

**Checkpoint 2:** All tables created, can insert and query data.

---

## STAGE 3: SEC EDGAR Collector
**Goal:** Build a working collector for SEC Form 4 filings.

### Tasks:
1. Create base collector abstract class
2. Implement SEC EDGAR collector
3. Parse Form 4 XML into structured data
4. Store raw data and parsed transactions
5. Handle rate limiting (10 req/sec)

### Key Implementation:

```python
# src/collectors/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)

class BaseCollector(ABC):
    """Abstract base class for data collectors."""
    
    SOURCE_NAME: str = "base"
    
    @abstractmethod
    async def fetch(self) -> Any:
        """Fetch raw data from source."""
        pass
    
    @abstractmethod
    def parse(self, raw_data: Any) -> Dict:
        """Parse raw data into structured format."""
        pass
    
    async def run(self) -> None:
        """Main collection loop."""
        logger.info(f"Starting {self.SOURCE_NAME} collector")
        raw_data = await self.fetch()
        parsed_data = self.parse(raw_data)
        await self.store(parsed_data)
        logger.info(f"Completed {self.SOURCE_NAME} collection")
```

```python
# src/collectors/sec_edgar.py
import httpx
import asyncio
from xml.etree import ElementTree
from datetime import datetime
from typing import List, Dict, Any
from .base import BaseCollector

class SECEdgarCollector(BaseCollector):
    SOURCE_NAME = "sec_edgar"
    BASE_URL = "https://www.sec.gov"
    RATE_LIMIT = 0.1  # seconds between requests
    
    def __init__(self, user_agent: str):
        self.user_agent = user_agent
        self.headers = {"User-Agent": user_agent}
    
    async def fetch_recent_form4s(self, limit: int = 100) -> List[Dict]:
        """Fetch recent Form 4 filings from RSS feed."""
        # Implementation
        pass
    
    def parse_form4_xml(self, xml_content: str) -> Dict:
        """Parse Form 4 XML into transaction data."""
        # Implementation
        pass
```

### Verification Tests:
```python
# tests/test_stage3.py
import pytest

def test_parse_form4_xml():
    """Test Form 4 XML parsing."""
    from src.collectors.sec_edgar import SECEdgarCollector
    
    sample_xml = '''<?xml version="1.0"?>
    <ownershipDocument>
        <issuer>
            <issuerCik>0001318605</issuerCik>
            <issuerName>Tesla, Inc.</issuerName>
            <issuerTradingSymbol>TSLA</issuerTradingSymbol>
        </issuer>
        <reportingOwner>
            <reportingOwnerId>
                <rptOwnerName>Musk Elon</rptOwnerName>
            </reportingOwnerId>
        </reportingOwner>
        <nonDerivativeTable>
            <nonDerivativeTransaction>
                <transactionAmounts>
                    <transactionShares><value>10000</value></transactionShares>
                    <transactionPricePerShare><value>250.00</value></transactionPricePerShare>
                </transactionAmounts>
                <transactionCoding>
                    <transactionCode>P</transactionCode>
                </transactionCoding>
            </nonDerivativeTransaction>
        </nonDerivativeTable>
    </ownershipDocument>'''
    
    collector = SECEdgarCollector(user_agent="Test test@test.com")
    result = collector.parse_form4_xml(sample_xml)
    
    assert result["issuer_cik"] == "0001318605"
    assert result["ticker"] == "TSLA"
    assert len(result["transactions"]) > 0
    assert result["transactions"][0]["shares"] == 10000

@pytest.mark.asyncio
async def test_fetch_rate_limiting():
    """Test that rate limiting is enforced."""
    from src.collectors.sec_edgar import SECEdgarCollector
    import time
    
    collector = SECEdgarCollector(user_agent="Test test@test.com")
    
    start = time.time()
    # This should take at least 0.3 seconds due to rate limiting
    # Mocked to not actually hit SEC
    elapsed = time.time() - start
    
    # Rate limiting should slow things down
    # (Implementation-dependent test)
```

**Checkpoint 3:** SEC collector fetches and parses Form 4 data correctly.

---

## STAGE 4: FRED Collector
**Goal:** Build collector for Federal Reserve Economic Data.

### Tasks:
1. Implement FRED API client
2. Fetch key economic series (yield curve, etc.)
3. Store with proper timestamps
4. Handle series with different frequencies

### Key Series to Collect:
- GS10, GS2 (Treasury yields)
- BAA10Y (Credit spread)
- M2SL (Money supply)
- ICSA, IC4WSA (Jobless claims)
- NFCI (Financial conditions)
- T10YIE (Inflation expectations)

### Verification Tests:
```python
# tests/test_stage4.py
@pytest.mark.asyncio
async def test_fetch_fred_series():
    """Test FRED series fetching."""
    from src.collectors.fred import FREDCollector
    
    collector = FREDCollector(api_key="test_key")  # Use mock/fixture
    
    # Test with mocked response
    data = await collector.fetch_series("GS10", limit=10)
    
    assert len(data) > 0
    assert "date" in data[0]
    assert "value" in data[0]
```

**Checkpoint 4:** FRED collector fetches economic data correctly.

---

## STAGE 5: Factor Computations
**Goal:** Implement factor calculation engine and first set of factors.

### Tasks:
1. Create factor computation framework
2. Implement SEC factors:
   - insider_transaction_momentum
   - insider_clustering_score
   - 8k_event_velocity
3. Implement FRED factors:
   - yield_curve_slope
   - credit_spread_index

### Verification Tests:
```python
# tests/test_stage5.py
def test_insider_momentum_calculation():
    """Test insider momentum factor."""
    from src.transformations.factors.sec_factors import calc_insider_momentum
    from datetime import date, timedelta
    
    # Setup test data
    transactions = [
        {"type": "P", "shares": 1000, "price": 100},  # Buy
        {"type": "P", "shares": 500, "price": 105},   # Buy
        {"type": "S", "shares": 200, "price": 110},   # Sell
    ]
    
    result = calc_insider_momentum(transactions)
    
    # Net buy value should be positive
    expected = (1000*100 + 500*105) - (200*110)
    assert result == expected

def test_yield_curve_slope():
    """Test yield curve slope calculation."""
    from src.transformations.factors.macro_factors import calc_yield_curve_slope
    
    gs10 = 4.5
    gs2 = 4.2
    
    result = calc_yield_curve_slope(gs10, gs2)
    assert result == 0.3
```

**Checkpoint 5:** Factor calculations produce correct results.

---

## STAGE 6: REST API
**Goal:** Build FastAPI endpoints to serve factor data.

### Tasks:
1. Create FastAPI application structure
2. Implement endpoints:
   - GET /health
   - GET /api/v1/factors
   - GET /api/v1/factors/{name}
   - GET /api/v1/entities
   - GET /api/v1/entities/{id}
3. Add API key authentication
4. Add response caching

### Verification Tests:
```python
# tests/test_stage6.py
from fastapi.testclient import TestClient

def test_health_endpoint(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_list_factors(api_client, api_key):
    response = api_client.get(
        "/api/v1/factors",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200
    assert "factors" in response.json()

def test_get_factor_values(api_client, api_key, seed_factor_data):
    response = api_client.get(
        "/api/v1/factors/insider_momentum",
        params={"entity_id": "AAPL"},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["factor_name"] == "insider_momentum"
    assert len(data["values"]) > 0
```

**Checkpoint 6:** API endpoints respond correctly with proper authentication.

---

## STAGE 7: Integration & End-to-End Testing
**Goal:** Verify complete data flow from collection to API response.

### Tasks:
1. Run collectors to populate database
2. Run factor computations
3. Query factors via API
4. Verify data consistency

### End-to-End Test:
```python
# tests/test_e2e.py
@pytest.mark.asyncio
async def test_full_pipeline():
    """Test complete data pipeline."""
    # 1. Run SEC collector (with mocked data)
    # 2. Verify raw data stored
    # 3. Run factor computation
    # 4. Verify factor computed
    # 5. Query via API
    # 6. Verify response matches expected
    pass
```

**Checkpoint 7:** Full pipeline works end-to-end.

---

## STAGE 8: Dashboard (Optional for MVP)
**Goal:** Create basic React dashboard for data visualization.

### Tasks:
1. Set up React project with Vite
2. Create factor time series chart
3. Create entity search
4. Connect to API

**Checkpoint 8:** Dashboard displays factor data.

---

## Commands to Run Tests

After implementing each stage:

```bash
# Run tests for specific stage
pytest tests/test_stage1.py -v

# Run all tests
pytest tests/ -v

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test
pytest tests/test_stage3.py::test_parse_form4_xml -v
```

## Troubleshooting

If tests fail:
1. Check the error message carefully
2. Verify environment variables are set
3. Confirm database is running
4. Check API keys are valid
5. Review logs for detailed errors

## Success Criteria

MVP is complete when:
- [ ] All 7 stage checkpoints pass
- [ ] SEC EDGAR collector runs successfully
- [ ] FRED collector runs successfully  
- [ ] 5+ factors compute correctly
- [ ] API serves factor data
- [ ] Response time < 500ms
- [ ] Tests have > 80% coverage
```

---

## How to Use This Prompt

1. **Copy the entire prompt** from the code block above
2. **Paste into Claude** or your preferred AI coding assistant
3. **Let the agent work** through each stage
4. **Intervene if needed** when tests fail repeatedly
5. **Save progress** at each checkpoint

The agent will loop through implementation → testing → fixing until each stage is complete before moving on.
