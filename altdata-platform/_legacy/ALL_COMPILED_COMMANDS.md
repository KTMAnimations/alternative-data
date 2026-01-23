# COMPILED RALPH COMMANDS
# Copy the command for your current task

# ============================================================
# TASK 1: REACT DASHBOARD
# ============================================================

ralph "You are an expert software engineer building the Alternative Data Platform.

REPO: https://github.com/KTMAnimations/alternative-data
STATUS: Phase 1 & 2 complete | 200+ tests | 80+ factors | API at localhost:8000
STACK: Python 3.11, FastAPI, PostgreSQL+TimescaleDB, Redis

CURRENT TASK: Create React Dashboard

Create dashboard in altdata-platform/dashboard/ directory.

TECH STACK:
- Vite + React 18
- React Router v6
- TanStack Query (data fetching)
- Recharts (charts)
- Tailwind CSS
- Axios

REQUIRED STRUCTURE:
dashboard/
├── src/
│   ├── components/
│   │   ├── Layout.jsx          # Nav + sidebar
│   │   ├── FactorCard.jsx      # Summary card
│   │   ├── FactorChart.jsx     # Time series chart
│   │   ├── EntityTable.jsx     # Sortable table
│   │   ├── SourceStatus.jsx    # Health indicators
│   │   └── SearchBar.jsx       # Global search
│   ├── pages/
│   │   ├── Dashboard.jsx       # / - Overview
│   │   ├── Factors.jsx         # /factors - List
│   │   ├── FactorDetail.jsx    # /factors/:id
│   │   ├── Entities.jsx        # /entities - List
│   │   ├── EntityDetail.jsx    # /entities/:id
│   │   └── Sources.jsx         # /sources - Status
│   ├── hooks/
│   │   ├── useFactors.js
│   │   └── useEntities.js
│   ├── api/client.js           # Axios with VITE_API_URL
│   └── App.jsx                 # Router
├── package.json
├── vite.config.js
├── tailwind.config.js
└── .env.example                # VITE_API_URL=http://localhost:8000

API ENDPOINTS:
- GET /api/v1/factors
- GET /api/v1/factors/{name}?entity_id=X
- GET /api/v1/entities
- GET /api/v1/entities/{id}
- GET /api/v1/sources/status

SUCCESS: npm run dev works, all pages render, charts display data.

START: Create the dashboard with all components and pages."


# ============================================================
# TASK 2: PYTHON SDK
# ============================================================

ralph "You are an expert software engineer building the Alternative Data Platform.

REPO: https://github.com/KTMAnimations/alternative-data
STATUS: Phase 1 & 2 complete | 200+ tests | 80+ factors | API at localhost:8000
STACK: Python 3.11, FastAPI, PostgreSQL+TimescaleDB, Redis

CURRENT TASK: Create Python SDK

Create pip-installable SDK in altdata-sdk/ directory.

REQUIRED STRUCTURE:
altdata-sdk/
├── altdata/
│   ├── __init__.py
│   ├── client.py           # AltDataClient class
│   ├── models.py           # Pydantic models
│   └── exceptions.py       # Custom exceptions
├── tests/test_client.py
├── pyproject.toml
└── README.md

CLIENT INTERFACE:
from altdata import AltDataClient
client = AltDataClient(api_key='xxx', base_url='http://localhost:8000')
factors = client.list_factors(category='sec')
data = client.get_factor('insider_transaction_momentum', entity_id='AAPL')
df = data.to_dataframe()  # pandas DataFrame
entities = client.list_entities(search='Apple')

API ENDPOINTS TO WRAP:
GET /api/v1/factors
GET /api/v1/factors/{name}?entity_id=X&start_date=Y&end_date=Z
GET /api/v1/entities
GET /api/v1/entities/{id}
GET /api/v1/sources/status

SUCCESS: pip install -e . works, pytest passes 90%+ coverage.

START: Examine src/api/main.py for endpoints, then create SDK."


# ============================================================
# TASK 3: AWS DEPLOYMENT
# ============================================================

ralph "You are an expert software engineer building the Alternative Data Platform.

REPO: https://github.com/KTMAnimations/alternative-data
STATUS: Phase 1 & 2 complete | 200+ tests | 80+ factors
STACK: Python 3.11, FastAPI, PostgreSQL+TimescaleDB, Redis

CURRENT TASK: AWS Infrastructure with Terraform

Create terraform/ directory with production infrastructure.

REQUIRED STRUCTURE:
terraform/
├── main.tf
├── variables.tf
├── outputs.tf
├── modules/
│   ├── vpc/main.tf           # VPC, subnets, IGW, NAT
│   ├── rds/main.tf           # PostgreSQL 15 + TimescaleDB
│   ├── elasticache/main.tf   # Redis cluster
│   ├── ecs/main.tf           # Fargate cluster + service
│   ├── alb/main.tf           # Load balancer + HTTPS
│   ├── s3/main.tf            # Raw data bucket
│   └── cloudwatch/main.tf    # Logs + alarms
└── environments/
    ├── staging.tfvars
    └── production.tfvars

ALSO CREATE:
.github/workflows/deploy.yml  # CI/CD pipeline

RESOURCES:
- VPC: 2 AZs, public/private subnets
- RDS: db.t3.medium (staging), db.r5.large Multi-AZ (prod)
- Redis: cache.t3.micro (staging), cache.r5.large (prod)
- ECS: 2 Fargate tasks with autoscaling
- ALB: HTTPS with ACM certificate
- S3: Bucket for raw data storage

ECS CONTAINER:
- Image from ECR
- Port 8000
- Health check: /health
- Environment vars from Secrets Manager

SUCCESS: terraform init && terraform plan works with valid output.

START: Create terraform modules and GitHub Actions workflow."


# ============================================================
# TASK 4: ALERTING SYSTEM
# ============================================================

ralph "You are an expert software engineer building the Alternative Data Platform.

REPO: https://github.com/KTMAnimations/alternative-data
STATUS: Phase 1 & 2 complete | 200+ tests | 80+ factors
STACK: Python 3.11, FastAPI, PostgreSQL+TimescaleDB, Redis

CURRENT TASK: Alerting System

Add alerting to src/alerts/ directory.

DATABASE TABLES (add migration):
alert_rules: id, name, factor_name, entity_id, condition, threshold, lookback_days, is_active
alert_notifications: id, rule_id, entity_id, factor_value, triggered_at, notification_channel, status

REQUIRED FILES:
src/alerts/
├── __init__.py
├── models.py           # SQLAlchemy models
├── engine.py           # AlertEngine class
├── notifiers.py        # Slack, Email, Webhook notifiers
└── routes.py           # FastAPI endpoints

ALERTENGINE:
class AlertEngine:
    def check_all_rules(self) -> List[AlertNotification]
    def check_rule(self, rule: AlertRule) -> Optional[AlertNotification]
    def calculate_zscore(self, factor_name, entity_id, lookback) -> float

CONDITIONS SUPPORTED:
- gt (greater than)
- lt (less than)
- eq (equals)
- zscore_gt (z-score above threshold)
- zscore_lt (z-score below threshold)

API ENDPOINTS:
POST   /api/v1/alerts/rules
GET    /api/v1/alerts/rules
GET    /api/v1/alerts/rules/{id}
PUT    /api/v1/alerts/rules/{id}
DELETE /api/v1/alerts/rules/{id}
GET    /api/v1/alerts/notifications

AIRFLOW DAG:
Add to dags/altdata_dags.py - run check_alerts every 5 minutes

SUCCESS: pytest tests/test_alerts.py passes, can create rule via API.

START: Create models, engine, notifiers, routes, and tests."


# ============================================================
# TASK 5: BACKTESTING FRAMEWORK
# ============================================================

ralph "You are an expert software engineer building the Alternative Data Platform.

REPO: https://github.com/KTMAnimations/alternative-data
STATUS: Phase 1 & 2 complete | 200+ tests | 80+ factors
STACK: Python 3.11, FastAPI, PostgreSQL+TimescaleDB, Redis

CURRENT TASK: Backtesting Framework

Add backtesting to src/backtest/ directory.

REQUIRED FILES:
src/backtest/
├── __init__.py
├── engine.py           # BacktestEngine
├── metrics.py          # Sharpe, drawdown, IC
├── prices.py           # PriceProvider (yfinance)
├── models.py           # BacktestResult
└── routes.py           # API endpoints

BACKTESTENGINE:
class BacktestEngine:
    def run(
        self,
        factor_name: str,
        universe: List[str],      # Entity IDs
        start_date: date,
        end_date: date,
        rebalance_freq: str,      # daily, weekly, monthly
        long_short: bool = True,
        top_n: int = 10
    ) -> BacktestResult

BACKTESTRESULT:
class BacktestResult:
    returns: pd.Series
    cumulative_returns: pd.Series
    sharpe_ratio: float
    max_drawdown: float
    turnover: float
    ic_mean: float
    positions: pd.DataFrame
    
    def to_dict(self) -> dict

METRICS:
def calculate_sharpe(returns, risk_free=0.0) -> float
def calculate_max_drawdown(cumulative) -> float
def calculate_ic(factor_values, forward_returns) -> float
def calculate_turnover(positions) -> float

API ENDPOINTS:
POST /api/v1/backtest/run
{factor_name, universe, start_date, end_date, rebalance_freq, top_n}
Returns: {job_id, status}

GET /api/v1/backtest/results/{job_id}
Returns: {status, sharpe_ratio, max_drawdown, ic_mean, ...}

SUCCESS: pytest tests/test_backtest.py passes, can run backtest via API.

START: Create engine, metrics, prices provider, and tests."


# ============================================================
# TASK 6: DOCUMENTATION SITE
# ============================================================

ralph "You are an expert software engineer building the Alternative Data Platform.

REPO: https://github.com/KTMAnimations/alternative-data
STATUS: Phase 1 & 2 complete | 200+ tests | 80+ factors
STACK: Python 3.11, FastAPI, PostgreSQL+TimescaleDB, Redis

CURRENT TASK: Documentation Site with MkDocs

Create docs/ directory with full documentation.

REQUIRED STRUCTURE:
docs/
├── mkdocs.yml              # Material theme config
└── docs/
    ├── index.md            # Home page
    ├── getting-started/
    │   ├── quickstart.md
    │   ├── authentication.md
    │   └── rate-limits.md
    ├── api-reference/
    │   ├── overview.md
    │   ├── factors.md
    │   ├── entities.md
    │   ├── alerts.md
    │   └── backtest.md
    ├── factors/
    │   ├── index.md        # Full catalog
    │   ├── sec.md          # 8 factors
    │   ├── macro.md        # 7 factors
    │   ├── aviation.md     # 4 factors
    │   ├── energy.md       # 8 factors
    │   ├── patents.md      # 8 factors
    │   ├── environmental.md # 6 factors
    │   ├── weather.md      # 6 factors
    │   ├── trends.md       # 5 factors
    │   ├── sentiment.md    # 5 factors
    │   ├── shipping.md     # 5 factors
    │   ├── github.md       # 5 factors
    │   └── satellite.md    # 4 factors
    ├── sdk/
    │   ├── installation.md
    │   └── usage.md
    └── data-sources/
        └── overview.md

MKDOCS.YML CONFIG:
- theme: material
- plugins: search
- nav with all sections
- GitHub Pages deployment

CONTENT REQUIREMENTS:
- Every API endpoint with request/response examples
- Every factor with: description, formula, frequency, entity_type
- SDK installation: pip install altdata
- Code examples throughout

SUCCESS: mkdocs serve works, all pages render, search works.

START: Create mkdocs.yml and all markdown files."


# ============================================================
# EXECUTION ORDER (Recommended)
# ============================================================
# 1. TASK 2: Python SDK (smallest, standalone)
# 2. TASK 6: Documentation (can do while SDK ships)
# 3. TASK 1: Dashboard (needs working API to test)
# 4. TASK 3: AWS Deployment (deploys everything)
# 5. TASK 4: Alerting (needs production DB)
# 6. TASK 5: Backtesting (needs price data, can be last)
