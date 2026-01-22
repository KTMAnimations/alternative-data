# Alternative Data Platform - Full Completion Prompt

Use this prompt with Ralph Loop to complete the entire Alternative Data Platform project.

## Reference Documents
- **PRD (source of truth):** /Users/kaivaid/alternative-data/ALTERNATIVE_DATA_PLATFORM_PRD.md
- **Architecture:** altdata-platform/ARCHITECTURE.md
- **Data Sources:** altdata-platform/DATA_SOURCES.md
- **Development Guide:** altdata-platform/DEVELOPMENT.md

## Current Status
The core platform is 90% complete:
- ✅ 13 collectors implemented (all Tier 1 + Tier 2 sources)
- ✅ 40+ database models
- ✅ 56 factors (need 80+)
- ✅ 32+ API endpoints
- ✅ 393 tests passing
- ✅ Basic Docker deployment
- 🟡 8 DAGs (need 12)
- ❌ Dashboard (React + Recharts)
- ❌ Python SDK
- ❌ Production Infrastructure (Terraform)
- ❌ CI/CD Pipeline

## Completion Tasks

### PHASE A: Factor Completion (Target: 80+ factors)

Reference PRD section "Factor Catalog" for the complete list. Currently at 56 factors, need ~24 more.

**Missing SEC Factors (add to src/transformations/factors/sec_factors.py):**
- insider_buy_ratio: Buys / (Buys + Sells)
- filing_sentiment_score: NLP sentiment from filing text
- insider_size_percentile: Transaction size vs historical
- cxo_transaction_flag: C-suite specific transactions
- form4_timing_score: Days between trade and filing

**Missing Macro Factors (add to src/transformations/factors/macro_factors.py):**
- yield_curve_inversion: Binary inverted or not
- money_supply_growth: M2 YoY change
- jobless_claims_momentum: 4-week vs 12-week average
- inflation_expectations: 10Y breakeven rate
- financial_conditions_index: NFCI value

**Missing Energy Factors (add to src/transformations/factors/energy_factors.py):**
- industrial_load_index: Overnight base load
- weather_adjusted_demand: Actual minus predicted
- peak_demand_ratio: Current vs historical peak
- grid_stress_indicator: Load vs capacity margin
- cross_iso_flow: Inter-regional transfers

**Missing Patent Factors (add to src/transformations/factors/patent_factors.py):**
- patent_grant_rate: Grants / Applications
- patent_breadth_index: CPC code diversity
- r_and_d_intensity_proxy: Patents / Revenue estimate
- inventor_retention: Repeat inventors percentage

**Missing Environmental Factors (add to src/transformations/factors/air_quality_factors.py):**
- pollution_yoy_change: Year-over-year comparison
- seasonal_adjusted_aqi: Deseasonalized air quality
- cross_border_pollution: Regional spillover

**Missing Weather Factors (add to src/transformations/factors/weather_factors.py):**
- severe_weather_exposure: Company location alerts

After adding factors:
- Export all new factors in src/transformations/factors/__init__.py
- Import in src/api/main.py
- Run: pytest tests/ -v
- Verify factor count via GET /api/v1/factors

### PHASE B: Complete Airflow DAGs

Add missing DAGs to dags/altdata_dags.py following existing patterns:

```python
# Missing DAGs to add:
dag_weather = DAG("altdata_weather", schedule_interval="0 * * * *", ...)  # Hourly
dag_trends = DAG("altdata_trends", schedule_interval="0 6 * * *", ...)    # Daily 6 AM
dag_reddit = DAG("altdata_reddit", schedule_interval="0 * * * *", ...)   # Hourly
dag_shipping = DAG("altdata_shipping", schedule_interval="0 * * * *", ...) # Hourly
dag_github = DAG("altdata_github", schedule_interval="0 6 * * *", ...)   # Daily 6 AM
dag_satellite = DAG("altdata_satellite", schedule_interval="0 6 * * MON", ...) # Weekly Monday
```

Also add these sources to run_collector() helper function.

### PHASE C: React Dashboard

Create dashboard/ directory with React + Vite + Recharts:

```
dashboard/
├── package.json
├── vite.config.js
├── index.html
├── src/
│   ├── main.jsx
│   ├── App.jsx
│   ├── api/
│   │   └── client.js          # API client with auth
│   ├── components/
│   │   ├── Layout.jsx         # Header, sidebar, main content
│   │   ├── FactorChart.jsx    # Time series chart (Recharts)
│   │   ├── FactorTable.jsx    # Factor values table
│   │   ├── EntitySearch.jsx   # Search entities
│   │   ├── SourceStatus.jsx   # Data source health
│   │   └── CategoryFilter.jsx # Filter by category
│   ├── pages/
│   │   ├── Dashboard.jsx      # Overview with key metrics
│   │   ├── Factors.jsx        # Factor browser
│   │   ├── Entities.jsx       # Entity explorer
│   │   └── Sources.jsx        # Data source status
│   └── styles/
│       └── globals.css
└── README.md
```

**Dashboard Features:**
- Factor time series visualization with Recharts
- Entity search and selection
- Category filtering
- Data source status monitoring
- Responsive design (Tailwind CSS)
- API key configuration

### PHASE D: Python SDK

Create altdata_sdk/ package:

```
altdata_sdk/
├── setup.py
├── pyproject.toml
├── README.md
├── altdata/
│   ├── __init__.py
│   ├── client.py              # Main AltDataClient class
│   ├── factors.py             # Factor retrieval methods
│   ├── entities.py            # Entity methods
│   ├── exceptions.py          # Custom exceptions
│   └── models.py              # Pydantic response models
└── tests/
    └── test_client.py
```

**SDK Features:**
```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-key", base_url="https://api.example.com")

# Get factor values
df = client.get_factor("insider_transaction_momentum", entity_id="AAPL",
                       start_date="2024-01-01", as_dataframe=True)

# Search entities
entities = client.search_entities(query="Apple", entity_type="company")

# List factors by category
factors = client.list_factors(category="sec")

# Get multiple factors
df = client.get_factors(["yield_curve_slope", "credit_spread_index"],
                        entity_id="MARKET", as_dataframe=True)
```

### PHASE E: Production Infrastructure

Create infrastructure/ directory with Terraform:

```
infrastructure/
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── modules/
│   │   ├── rds/              # PostgreSQL + TimescaleDB
│   │   ├── elasticache/      # Redis
│   │   ├── ecs/              # Fargate cluster
│   │   ├── alb/              # Load balancer
│   │   ├── s3/               # Raw data storage
│   │   └── cloudwatch/       # Monitoring
│   └── environments/
│       ├── staging.tfvars
│       └── production.tfvars
└── README.md
```

**Infrastructure Components (per PRD):**
- RDS PostgreSQL 15 with TimescaleDB (db.r5.large Multi-AZ for prod)
- ElastiCache Redis (cache.r5.large Multi-AZ for prod)
- ECS Fargate (4+ tasks, 1 vCPU, 2GB each)
- Application Load Balancer with SSL
- S3 bucket for raw data (1TB)
- CloudWatch alarms and dashboards
- VPC with private subnets
- Secrets Manager for API keys

### PHASE F: CI/CD Pipeline

Create .github/workflows/:

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: timescale/timescaledb:latest-pg15
      redis:
        image: redis:7-alpine
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v3

# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy-staging:
    # Build, push to ECR, deploy to ECS staging
  deploy-production:
    needs: deploy-staging
    if: github.ref == 'refs/heads/main'
    # Deploy to production with approval gate
```

## Working Loop

For each phase:
1. READ the PRD section for specifications
2. IMPLEMENT following existing patterns in the codebase
3. TEST thoroughly (unit + integration)
4. VERIFY against PRD requirements
5. COMMIT working code
6. PROCEED to next phase

## Progress Checkpoints

After each phase, verify:

**Phase A:** `GET /api/v1/factors` returns 80+ factors
**Phase B:** All 12 DAGs defined in altdata_dags.py
**Phase C:** Dashboard runs with `npm run dev`, displays factor charts
**Phase D:** SDK installs with `pip install -e altdata_sdk/`, tests pass
**Phase E:** `terraform plan` succeeds for staging environment
**Phase F:** GitHub Actions workflow runs on push

## Success Criteria (from PRD)

Technical KPIs:
- [ ] API latency p95 < 200ms
- [ ] 80+ factors computing
- [ ] 200+ tests passing (currently 393 ✓)
- [ ] Test coverage > 80%
- [ ] All 12 data sources active

Deliverables:
- [ ] REST API (complete ✓)
- [ ] Web Dashboard (React + Recharts)
- [ ] Python SDK v1.0
- [ ] Production deployment ready
- [ ] CI/CD pipeline operational

## Notes

- Prioritize working code over perfect code
- Follow existing patterns in the codebase
- Reference PRD for exact specifications
- Run tests frequently: `pytest tests/ -v`
- Check API health: `curl http://localhost:8000/health`
