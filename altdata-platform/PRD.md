# Alternative Data Platform - Agentic PRD

**Repository:** https://github.com/KTMAnimations/alternative-data  
**Status:** Phase 2 Complete | 200+ tests | 80+ factors

---

## Project Summary

A platform that aggregates free alternative data (SEC filings, flight tracking, economic indicators, weather, sentiment, shipping, satellites) and computes quantitative factors for backtesting trading strategies.

**Tech Stack:** Python 3.11, FastAPI, PostgreSQL + TimescaleDB, Redis, SQLAlchemy, Airflow

---

## Completed Work

| Phase | What's Done | Tests |
|-------|-------------|-------|
| MVP | SEC EDGAR + FRED collectors, basic API | 73 |
| Phase 1 | +ADS-B, Power Grid, USPTO, OpenAQ | 165 |
| Phase 2 | +Weather, Trends, Reddit, Shipping, GitHub, Satellite | 200+ |
| Backfill | 6+ months historical data | - |

---

## Remaining Tasks

### TASK 1: React Dashboard
### TASK 2: Python SDK  
### TASK 3: Production Deployment (AWS)
### TASK 4: Alerting System
### TASK 5: Backtesting Framework
### TASK 6: Documentation Site

---

## TASK 1: React Dashboard

**Goal:** Web UI to visualize factors, search entities, configure alerts.

### Requirements

**Pages:**
1. `/` - Dashboard home with key factor summaries
2. `/factors` - Browse all factors with filters
3. `/factors/:id` - Factor detail with time series chart
4. `/entities` - Search and browse entities
5. `/entities/:id` - Entity detail with all available factors
6. `/sources` - Data source health status

**Components Needed:**
```
src/
├── components/
│   ├── Layout.jsx           # Nav + sidebar wrapper
│   ├── FactorCard.jsx       # Factor summary card
│   ├── FactorChart.jsx      # Recharts time series
│   ├── EntityTable.jsx      # Sortable entity list
│   ├── SourceStatus.jsx     # Health indicators
│   ├── SearchBar.jsx        # Global search
│   └── DateRangePicker.jsx  # Date filter
├── pages/
│   ├── Dashboard.jsx
│   ├── Factors.jsx
│   ├── FactorDetail.jsx
│   ├── Entities.jsx
│   ├── EntityDetail.jsx
│   └── Sources.jsx
├── hooks/
│   ├── useFactors.js        # Factor API calls
│   ├── useEntities.js       # Entity API calls
│   └── useSources.js        # Source status calls
├── api/
│   └── client.js            # Axios instance with API key
└── App.jsx                  # Router setup
```

**Tech Stack:**
- React 18 + Vite
- React Router v6
- Recharts (charts)
- TanStack Query (data fetching)
- Tailwind CSS
- Axios

**API Endpoints to Consume:**
```
GET /api/v1/factors
GET /api/v1/factors/{name}?entity_id=X&start_date=Y&end_date=Z
GET /api/v1/entities
GET /api/v1/entities/{id}
GET /api/v1/sources/status
GET /health
```

**Success Criteria:**
- [ ] All 6 pages render without errors
- [ ] Factor charts display time series data
- [ ] Entity search works with debouncing
- [ ] Source status shows green/red indicators
- [ ] Responsive on mobile
- [ ] Connects to API at configurable `VITE_API_URL`

**Output Location:** `altdata-platform/dashboard/`

---

## TASK 2: Python SDK

**Goal:** pip-installable client library for the API.

### Requirements

**Package Structure:**
```
altdata-sdk/
├── altdata/
│   ├── __init__.py          # Exports AltDataClient
│   ├── client.py            # Main client class
│   ├── models.py            # Pydantic response models
│   ├── exceptions.py        # Custom exceptions
│   └── factors.py           # Factor constants/enums
├── tests/
│   ├── test_client.py
│   └── test_models.py
├── pyproject.toml           # Modern packaging
├── README.md
└── examples/
    ├── basic_usage.py
    └── backtest_example.py
```

**Client Interface:**
```python
from altdata import AltDataClient

client = AltDataClient(api_key="xxx", base_url="https://api.example.com")

# List factors
factors = client.list_factors(category="sec")

# Get factor values
data = client.get_factor(
    "insider_transaction_momentum",
    entity_id="AAPL",
    start_date="2024-01-01",
    end_date="2024-06-30"
)

# Returns pandas DataFrame
df = data.to_dataframe()

# List entities
entities = client.list_entities(entity_type="company", search="Apple")

# Get entity details
entity = client.get_entity("AAPL")

# Check source status
status = client.get_source_status()
```

**Response Models:**
```python
class Factor(BaseModel):
    id: str
    name: str
    category: str
    entity_type: str
    frequency: str
    description: Optional[str]

class FactorValue(BaseModel):
    date: date
    value: float
    computed_at: datetime

class FactorData(BaseModel):
    factor: str
    entity_id: str
    values: List[FactorValue]
    
    def to_dataframe(self) -> pd.DataFrame:
        ...

class Entity(BaseModel):
    id: str
    name: str
    ticker: Optional[str]
    entity_type: str
    sector: Optional[str]
```

**Success Criteria:**
- [ ] `pip install altdata` works
- [ ] All API endpoints wrapped
- [ ] Returns Pydantic models
- [ ] `.to_dataframe()` returns pandas DataFrame
- [ ] Proper error handling with custom exceptions
- [ ] Type hints throughout
- [ ] README with usage examples
- [ ] 90%+ test coverage

**Output Location:** `altdata-sdk/`

---

## TASK 3: Production Deployment (AWS)

**Goal:** Deploy platform to AWS with auto-scaling and monitoring.

### Requirements

**Infrastructure (Terraform):**
```
terraform/
├── main.tf
├── variables.tf
├── outputs.tf
├── modules/
│   ├── vpc/
│   ├── rds/
│   ├── elasticache/
│   ├── ecs/
│   ├── alb/
│   ├── s3/
│   └── cloudwatch/
└── environments/
    ├── staging.tfvars
    └── production.tfvars
```

**Resources to Create:**
| Resource | Staging | Production |
|----------|---------|------------|
| VPC | 2 AZs | 3 AZs |
| RDS PostgreSQL 15 | db.t3.medium | db.r5.large Multi-AZ |
| ElastiCache Redis | cache.t3.micro | cache.r5.large Multi-AZ |
| ECS Fargate | 2 tasks | 4 tasks + autoscaling |
| ALB | 1 | 1 |
| S3 | 1 bucket | 1 bucket + replication |
| CloudWatch | Basic | Dashboards + alarms |
| Secrets Manager | API keys | API keys |

**ECS Task Definition:**
```json
{
  "family": "altdata-api",
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [{
    "name": "api",
    "image": "${ECR_REPO}:${TAG}",
    "portMappings": [{"containerPort": 8000}],
    "healthCheck": {
      "command": ["CMD-SHELL", "curl -f http://localhost:8000/health"]
    },
    "logConfiguration": {
      "logDriver": "awslogs"
    }
  }]
}
```

**CI/CD (GitHub Actions):**
```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov

  deploy-staging:
    needs: test
    if: github.ref == 'refs/heads/main'
    steps:
      - run: docker build -t altdata .
      - run: aws ecr push
      - run: aws ecs update-service --cluster staging

  deploy-prod:
    needs: deploy-staging
    environment: production
    steps:
      - run: aws ecs update-service --cluster production
```

**Success Criteria:**
- [ ] `terraform apply` creates all resources
- [ ] API accessible at `https://api.altdata.example.com`
- [ ] Health check passing
- [ ] Auto-scaling triggers at 70% CPU
- [ ] CloudWatch alarms configured
- [ ] Secrets not in code
- [ ] SSL/TLS enabled
- [ ] GitHub Actions deploys on merge to main

**Output Location:** `altdata-platform/terraform/` and `.github/workflows/`

---

## TASK 4: Alerting System

**Goal:** Real-time notifications when factors hit thresholds or anomalies detected.

### Requirements

**Database Tables:**
```sql
CREATE TABLE alert_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    factor_name VARCHAR(100) NOT NULL,
    entity_id VARCHAR(50),          -- NULL = all entities
    condition VARCHAR(20) NOT NULL, -- gt, lt, eq, zscore_gt, zscore_lt
    threshold FLOAT NOT NULL,
    lookback_days INT DEFAULT 30,   -- For zscore calculations
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE alert_notifications (
    id SERIAL PRIMARY KEY,
    rule_id INT REFERENCES alert_rules(id),
    entity_id VARCHAR(50),
    factor_value FLOAT,
    threshold FLOAT,
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    notified_at TIMESTAMPTZ,
    notification_channel VARCHAR(20), -- email, slack, webhook
    notification_status VARCHAR(20)   -- pending, sent, failed
);
```

**Alert Engine:**
```python
# src/alerts/engine.py
class AlertEngine:
    def check_all_rules(self) -> List[AlertNotification]:
        """Run all active rules against latest factor values."""
        
    def check_rule(self, rule: AlertRule) -> Optional[AlertNotification]:
        """Check single rule."""
        
    def calculate_zscore(self, factor_name: str, entity_id: str, lookback: int) -> float:
        """Calculate z-score for anomaly detection."""

# src/alerts/notifiers.py
class SlackNotifier:
    def send(self, alert: AlertNotification) -> bool: ...

class EmailNotifier:
    def send(self, alert: AlertNotification) -> bool: ...

class WebhookNotifier:
    def send(self, alert: AlertNotification) -> bool: ...
```

**API Endpoints:**
```
POST /api/v1/alerts/rules          # Create rule
GET  /api/v1/alerts/rules          # List rules
GET  /api/v1/alerts/rules/{id}     # Get rule
PUT  /api/v1/alerts/rules/{id}     # Update rule
DELETE /api/v1/alerts/rules/{id}   # Delete rule
GET  /api/v1/alerts/notifications  # List triggered alerts
```

**Airflow DAG:**
```python
# Run every 5 minutes
@dag(schedule="*/5 * * * *")
def check_alerts():
    engine = AlertEngine()
    alerts = engine.check_all_rules()
    for alert in alerts:
        notifier.send(alert)
```

**Success Criteria:**
- [ ] Can create rules via API
- [ ] Rules support: gt, lt, eq, zscore_gt, zscore_lt
- [ ] Alerts trigger within 5 minutes of condition met
- [ ] Slack notifications work
- [ ] Email notifications work
- [ ] Webhook notifications work
- [ ] No duplicate notifications for same event
- [ ] Dashboard shows alert history

**Output Location:** `altdata-platform/src/alerts/`

---

## TASK 5: Backtesting Framework

**Goal:** Evaluate factor performance against historical returns.

### Requirements

**Core Classes:**
```python
# src/backtest/engine.py
class BacktestEngine:
    def __init__(self, start_date: date, end_date: date):
        self.start_date = start_date
        self.end_date = end_date
    
    def run(
        self,
        factor_name: str,
        universe: List[str],      # Entity IDs
        rebalance_freq: str,      # daily, weekly, monthly
        long_short: bool = True,
        top_n: int = 10
    ) -> BacktestResult:
        """Run factor backtest."""

class BacktestResult:
    returns: pd.Series           # Daily returns
    cumulative_returns: pd.Series
    sharpe_ratio: float
    max_drawdown: float
    turnover: float
    ic_mean: float               # Information coefficient
    ic_ir: float                 # IC information ratio
    factor_values: pd.DataFrame
    positions: pd.DataFrame
    
    def plot(self) -> Figure: ...
    def to_dict(self) -> dict: ...

# src/backtest/metrics.py
def calculate_sharpe(returns: pd.Series, risk_free: float = 0.0) -> float: ...
def calculate_max_drawdown(cumulative: pd.Series) -> float: ...
def calculate_ic(factor_values: pd.Series, forward_returns: pd.Series) -> float: ...
def calculate_turnover(positions: pd.DataFrame) -> float: ...
```

**Price Data Integration:**
```python
# src/backtest/prices.py
class PriceProvider:
    """Fetch historical prices for return calculation."""
    
    def get_prices(
        self,
        tickers: List[str],
        start_date: date,
        end_date: date
    ) -> pd.DataFrame:
        """Returns DataFrame with columns = tickers, index = dates."""
        # Uses yfinance or similar
    
    def get_returns(self, ...) -> pd.DataFrame:
        """Daily returns."""
```

**API Endpoints:**
```
POST /api/v1/backtest/run
Request:
{
  "factor_name": "insider_transaction_momentum",
  "universe": ["AAPL", "MSFT", "GOOGL", ...],
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "rebalance_freq": "weekly",
  "long_short": true,
  "top_n": 10
}

Response:
{
  "job_id": "abc123",
  "status": "running"
}

GET /api/v1/backtest/results/{job_id}
Response:
{
  "status": "complete",
  "sharpe_ratio": 1.45,
  "max_drawdown": -0.12,
  "cumulative_return": 0.23,
  "ic_mean": 0.05,
  ...
}
```

**Success Criteria:**
- [ ] Can run backtest for any factor
- [ ] Supports daily/weekly/monthly rebalance
- [ ] Calculates Sharpe, drawdown, IC, turnover
- [ ] Returns time series of positions and returns
- [ ] Handles missing data gracefully
- [ ] Results cached for re-retrieval
- [ ] Dashboard shows backtest results with charts

**Output Location:** `altdata-platform/src/backtest/`

---

## TASK 6: Documentation Site

**Goal:** Public docs site with API reference, guides, factor catalog.

### Requirements

**Structure (MkDocs):**
```
docs/
├── mkdocs.yml
├── docs/
│   ├── index.md                 # Home
│   ├── getting-started/
│   │   ├── quickstart.md
│   │   ├── authentication.md
│   │   └── rate-limits.md
│   ├── api-reference/
│   │   ├── overview.md
│   │   ├── factors.md
│   │   ├── entities.md
│   │   ├── alerts.md
│   │   └── backtest.md
│   ├── factors/
│   │   ├── index.md             # Factor catalog
│   │   ├── sec.md
│   │   ├── macro.md
│   │   ├── aviation.md
│   │   ├── energy.md
│   │   ├── patents.md
│   │   ├── environmental.md
│   │   ├── weather.md
│   │   ├── trends.md
│   │   ├── sentiment.md
│   │   ├── shipping.md
│   │   ├── github.md
│   │   └── satellite.md
│   ├── sdk/
│   │   ├── installation.md
│   │   ├── usage.md
│   │   └── examples.md
│   └── data-sources/
│       └── overview.md
└── overrides/                   # Custom theme
```

**Content Requirements:**
- Every API endpoint documented with request/response examples
- Every factor documented with description, formula, use case
- Python SDK usage with code examples
- Data source descriptions with update frequencies

**Success Criteria:**
- [ ] `mkdocs serve` runs locally
- [ ] Deploys to GitHub Pages or Netlify
- [ ] Search works
- [ ] All 80+ factors documented
- [ ] All API endpoints documented
- [ ] SDK installation and usage guides
- [ ] Mobile responsive

**Output Location:** `altdata-platform/docs/`

---

## Task Execution Order

```
TASK 1: Dashboard       (2-3 sessions)  ──┐
TASK 2: Python SDK      (1-2 sessions)  ──┼── Can parallelize
TASK 6: Documentation   (1-2 sessions)  ──┘
              │
              ▼
TASK 3: AWS Deployment  (2-3 sessions)  ◄── Needs working API
              │
              ▼
TASK 4: Alerting        (1-2 sessions)  ◄── Needs production DB
TASK 5: Backtesting     (2-3 sessions)  ◄── Needs price data access
```

**Recommended Order:** 2 → 6 → 1 → 3 → 4 → 5

---

## Environment Setup

**Required for all tasks:**
```bash
cd altdata-platform
source venv/bin/activate
docker-compose up -d db redis
```

**API must be running:**
```bash
uvicorn src.api.main:app --reload --port 8000
```

**Verify with:**
```bash
curl http://localhost:8000/health
# {"status":"healthy","database":"connected","cache":"connected"}
```

---

## Success Metrics

| Task | Done When |
|------|-----------|
| Dashboard | All pages render, charts work, deployed |
| SDK | pip installable, 90% coverage, on PyPI |
| Deployment | terraform apply works, API live on AWS |
| Alerting | Rules trigger notifications within 5 min |
| Backtesting | Can run backtest, see Sharpe/IC results |
| Docs | All factors + endpoints documented, live site |

**Project Complete When:**
- [ ] 200+ tests passing
- [ ] 80+ factors documented
- [ ] API live at production URL
- [ ] SDK on PyPI
- [ ] Docs site live
- [ ] Alerts working
- [ ] Backtest working
- [ ] Dashboard deployed
