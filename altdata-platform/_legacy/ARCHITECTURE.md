# Architecture Documentation

## System Overview

The Alternative Data Platform is designed as a modular, horizontally scalable system with clear separation of concerns. This document details the technical architecture, data flows, and design decisions.

## Design Principles

### 1. Point-in-Time Accuracy
All data is stored with publication timestamps to prevent look-ahead bias in backtesting. When a factor is computed, we record both the calculation timestamp and the effective date of the underlying data.

### 2. Idempotent Processing
All transformation jobs can be re-run without side effects. This enables:
- Easy recovery from failures
- Historical recomputation when factor logic changes
- Parallel processing without race conditions

### 3. Schema Evolution
Factor definitions are versioned. Breaking changes are deployed as new versions rather than modifying existing factors. This ensures backward compatibility for production systems.

### 4. Horizontal Scalability
The compute layer is stateless and scales with demand. All state is stored in persistent storage systems (PostgreSQL, Redis, S3).

### 5. Full Audit Trail
Complete lineage from raw source to computed factor. Every data point can be traced back to its origin.

## Component Details

### Data Ingestion Layer

```
┌─────────────────────────────────────────────────────────────┐
│                    COLLECTOR FRAMEWORK                       │
│                                                              │
│  ┌────────────────┐    ┌────────────────┐                   │
│  │  BaseCollector │    │  ScheduleMixin │                   │
│  │  - fetch()     │    │  - cron        │                   │
│  │  - parse()     │    │  - interval    │                   │
│  │  - store()     │    │  - retry       │                   │
│  │  - validate()  │    └────────────────┘                   │
│  └───────┬────────┘                                         │
│          │                                                   │
│  ┌───────┴───────┬───────────────┬───────────────┐         │
│  ▼               ▼               ▼               ▼         │
│ SEC           ADS-B           FRED           Power         │
│ Collector    Collector      Collector       Collector      │
└─────────────────────────────────────────────────────────────┘
```

#### Collector Base Class
```python
class BaseCollector(ABC):
    """Abstract base class for all data collectors."""
    
    @abstractmethod
    async def fetch(self) -> RawData:
        """Fetch data from source."""
        pass
    
    @abstractmethod
    def parse(self, raw: RawData) -> ParsedData:
        """Parse raw data into structured format."""
        pass
    
    async def store(self, data: ParsedData) -> None:
        """Store parsed data with lineage metadata."""
        pass
    
    def validate(self, data: ParsedData) -> ValidationResult:
        """Validate data quality and completeness."""
        pass
```

### Storage Layer

#### Raw Data Lake (S3/GCS)
- Stores original API responses and downloaded files
- Organized by: `/{source}/{year}/{month}/{day}/{timestamp}_{hash}.json`
- Immutable - never modified after write
- Retention: 7 years minimum

#### Processed Data Warehouse (PostgreSQL + TimescaleDB)
- Normalized, queryable data
- Partitioned by time for efficient queries
- Point-in-time versioning enabled

**Core Tables:**
```sql
-- Raw data references
CREATE TABLE raw_data_catalog (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    s3_path TEXT NOT NULL,
    fetch_timestamp TIMESTAMPTZ NOT NULL,
    data_timestamp TIMESTAMPTZ,
    checksum VARCHAR(64) NOT NULL,
    record_count INTEGER,
    metadata JSONB
);

-- Computed factors (TimescaleDB hypertable)
CREATE TABLE factors (
    id BIGSERIAL,
    factor_name VARCHAR(100) NOT NULL,
    entity_id VARCHAR(50) NOT NULL,
    entity_type VARCHAR(20) NOT NULL,
    value DOUBLE PRECISION,
    effective_date DATE NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL,
    version INTEGER NOT NULL,
    source_data_ids BIGINT[],
    metadata JSONB,
    PRIMARY KEY (id, effective_date)
);
SELECT create_hypertable('factors', 'effective_date');

-- Entity mapping
CREATE TABLE entities (
    id VARCHAR(50) PRIMARY KEY,
    entity_type VARCHAR(20) NOT NULL,
    name VARCHAR(255) NOT NULL,
    ticker VARCHAR(20),
    cik VARCHAR(20),
    lei VARCHAR(20),
    isin VARCHAR(20),
    aliases JSONB,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Cache Layer (Redis)
- Recent factor values for fast API response
- Rate limiting counters
- Session storage
- TTL: 1 hour for factors, 24 hours for static data

### Transformation Layer

```
┌─────────────────────────────────────────────────────────────┐
│                  TRANSFORMATION PIPELINE                     │
│                                                              │
│  Raw Data ──► Parsing ──► Validation ──► Factor Calc ──► Store
│                              │                               │
│                              ▼                               │
│                        Entity Resolution                     │
│                        (Company → Ticker)                    │
└─────────────────────────────────────────────────────────────┘
```

#### Factor Computation Engine
- Declarative factor definitions in YAML/Python
- Dependency resolution for complex factors
- Parallel execution where possible
- Automatic recomputation on dependency updates

**Factor Definition Example:**
```python
@factor(
    name="insider_transaction_momentum",
    entity_type="company",
    frequency="daily",
    lookback_days=30,
    dependencies=["sec_form4_transactions"]
)
def calc_insider_momentum(entity_id: str, date: date, ctx: FactorContext) -> float:
    """Net insider buying/selling from Form 4 filings."""
    form4s = ctx.get_data("sec_form4_transactions", entity_id, days=30)
    
    buy_value = sum(t.shares * t.price for t in form4s if t.type == 'P')
    sell_value = sum(t.shares * t.price for t in form4s if t.type == 'S')
    
    return buy_value - sell_value
```

### API Layer

```
┌─────────────────────────────────────────────────────────────┐
│                       API GATEWAY                            │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │   Auth   │  │   Rate   │  │  Cache   │  │  Logging │    │
│  │Middleware│  │ Limiter  │  │Middleware│  │Middleware│    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       └─────────────┴─────────────┴─────────────┘          │
│                          │                                  │
│  ┌───────────────────────┴───────────────────────┐         │
│  │              ROUTE HANDLERS                    │         │
│  │  /factors    /entities    /sources    /health │         │
│  └───────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

#### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/factors` | GET | List available factors |
| `/api/v1/factors/{name}` | GET | Get factor values |
| `/api/v1/entities` | GET | Search entities |
| `/api/v1/entities/{id}` | GET | Get entity details |
| `/api/v1/sources` | GET | List data sources |
| `/api/v1/sources/{name}/status` | GET | Source health status |
| `/health` | GET | System health check |

#### Response Format
```json
{
  "data": {
    "factor_name": "insider_transaction_momentum",
    "entity_id": "AAPL",
    "values": [
      {"date": "2024-01-15", "value": 1250000.0, "version": 1},
      {"date": "2024-01-16", "value": 980000.0, "version": 1}
    ]
  },
  "metadata": {
    "computed_at": "2024-01-17T08:00:00Z",
    "source_freshness": "2024-01-16T23:59:59Z"
  },
  "pagination": {
    "page": 1,
    "page_size": 100,
    "total": 250
  }
}
```

## Data Flow Example: SEC Form 4 → Insider Momentum Factor

```
1. COLLECTION
   ┌─────────────────────────────────────────────────────────┐
   │ SEC EDGAR Collector                                      │
   │ - Polls RSS feed every 5 minutes                        │
   │ - Downloads new Form 4 filings                          │
   │ - Stores raw XML to S3                                  │
   │ - Records metadata in raw_data_catalog                  │
   └─────────────────────────┬───────────────────────────────┘
                             ▼
2. PARSING
   ┌─────────────────────────────────────────────────────────┐
   │ Form 4 Parser                                           │
   │ - Extracts: issuer CIK, insider name, transaction type  │
   │ - Extracts: shares, price, transaction date             │
   │ - Validates required fields present                     │
   │ - Stores to sec_form4_transactions table                │
   └─────────────────────────┬───────────────────────────────┘
                             ▼
3. ENTITY RESOLUTION
   ┌─────────────────────────────────────────────────────────┐
   │ Entity Resolver                                          │
   │ - Maps CIK → company entity ID                          │
   │ - Maps CIK → ticker symbol(s)                           │
   │ - Handles multi-class shares, ADRs                      │
   └─────────────────────────┬───────────────────────────────┘
                             ▼
4. FACTOR COMPUTATION
   ┌─────────────────────────────────────────────────────────┐
   │ Factor Engine                                            │
   │ - Triggered by new Form 4 data                          │
   │ - Computes insider_transaction_momentum                 │
   │ - Computes insider_clustering_score                     │
   │ - Stores to factors table with lineage                  │
   └─────────────────────────┬───────────────────────────────┘
                             ▼
5. CACHE UPDATE
   ┌─────────────────────────────────────────────────────────┐
   │ Cache Invalidation                                       │
   │ - Invalidates affected entity factor cache              │
   │ - Pre-warms cache for frequently accessed entities      │
   └─────────────────────────┬───────────────────────────────┘
                             ▼
6. API SERVING
   ┌─────────────────────────────────────────────────────────┐
   │ API Response                                             │
   │ - Client requests factor via REST API                   │
   │ - Returns latest value + historical series              │
   │ - Includes metadata (freshness, version, sources)       │
   └─────────────────────────────────────────────────────────┘
```

## Deployment Architecture

### Development
- Docker Compose for local services
- SQLite for simple testing
- Mocked external APIs

### Production
```
┌─────────────────────────────────────────────────────────────┐
│                        CLOUD (AWS/GCP)                       │
│                                                              │
│  ┌──────────────────┐    ┌──────────────────┐              │
│  │   Load Balancer  │    │   CDN (Static)   │              │
│  └────────┬─────────┘    └──────────────────┘              │
│           │                                                  │
│  ┌────────┴─────────┐                                       │
│  │  API Servers     │  (Auto-scaling group)                 │
│  │  (ECS/GKE)       │                                       │
│  └────────┬─────────┘                                       │
│           │                                                  │
│  ┌────────┴─────────────────────┬─────────────────┐        │
│  │                              │                  │        │
│  ▼                              ▼                  ▼        │
│ PostgreSQL                    Redis            S3/GCS       │
│ (RDS/Cloud SQL)            (ElastiCache)     (Data Lake)   │
│                                                              │
│  ┌──────────────────────────────────────────────┐          │
│  │           Airflow (Collectors/Jobs)           │          │
│  │                 (ECS/GKE)                     │          │
│  └──────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

## Security Considerations

### Authentication
- API key authentication for programmatic access
- JWT tokens for dashboard sessions
- Key rotation policy: 90 days

### Data Protection
- Encryption at rest (AES-256)
- Encryption in transit (TLS 1.3)
- PII handling compliant with GDPR/CCPA

### Access Control
- Role-based access control (RBAC)
- Audit logging of all data access
- IP allowlisting for enterprise clients

## Monitoring & Observability

### Metrics (Prometheus)
- API latency percentiles (p50, p95, p99)
- Collector success/failure rates
- Factor computation duration
- Cache hit rates

### Logging (ELK/CloudWatch)
- Structured JSON logs
- Correlation IDs across services
- Log retention: 90 days

### Alerting
- Collector failures
- API error rate > 1%
- Factor staleness > threshold
- Database connection issues

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| API Response Time (p95) | < 200ms | Factor queries |
| API Response Time (p99) | < 500ms | Complex queries |
| Collector Uptime | > 99.5% | Per source |
| Data Freshness | < 15 min | For real-time sources |
| Factor Computation | < 5 min | After new data arrives |
