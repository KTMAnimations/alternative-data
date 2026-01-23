# Alternative Data Platform - Ralph Loop Prompt

Copy everything below the line into your ralph session.

---

You are an expert software engineer continuing development of the Alternative Data Platform.

## Repository
https://github.com/KTMAnimations/alternative-data

## Current State
- Phase 1 & 2: ✅ COMPLETE
- Tests: 200+ passing
- Factors: 80+ computing
- Backfill: 6+ months of historical data
- API: Running at localhost:8000

## Tech Stack
- Python 3.11, FastAPI, SQLAlchemy
- PostgreSQL 15 + TimescaleDB
- Redis 7
- React 18 + Vite (for dashboard)

## Project Structure
```
altdata-platform/
├── src/
│   ├── api/main.py              # FastAPI app
│   ├── collectors/              # 12 data collectors
│   ├── models/                  # SQLAlchemy models
│   ├── transformations/factors/ # 80+ factor computations
│   └── config/settings.py       # Pydantic settings
├── tests/                       # 200+ tests
├── scripts/                     # backfill.py, init_db.py
├── dags/                        # Airflow DAGs
├── docker-compose.yml
└── requirements.txt
```

## Remaining Tasks

### TASK 1: React Dashboard
Create `dashboard/` with:
- React 18 + Vite + Tailwind + Recharts
- Pages: /, /factors, /factors/:id, /entities, /entities/:id, /sources
- Components: FactorChart, EntityTable, SourceStatus, SearchBar
- Connects to API at VITE_API_URL

### TASK 2: Python SDK
Create `altdata-sdk/` with:
- pip-installable package
- AltDataClient class wrapping all API endpoints
- Pydantic models for responses
- .to_dataframe() returns pandas
- pyproject.toml for modern packaging

### TASK 3: AWS Deployment
Create `terraform/` with:
- VPC, RDS, ElastiCache, ECS, ALB, S3, CloudWatch
- staging.tfvars and production.tfvars
- GitHub Actions CI/CD in .github/workflows/

### TASK 4: Alerting System
Add to `src/alerts/`:
- alert_rules and alert_notifications tables
- AlertEngine to check rules against factors
- Notifiers: Slack, Email, Webhook
- API endpoints: CRUD for rules
- Airflow DAG to run every 5 minutes

### TASK 5: Backtesting Framework
Add to `src/backtest/`:
- BacktestEngine to run factor backtests
- PriceProvider using yfinance
- Metrics: Sharpe, drawdown, IC, turnover
- API endpoints to run and retrieve backtests

### TASK 6: Documentation Site
Create `docs/` with:
- MkDocs + Material theme
- API reference for all endpoints
- Factor catalog (80+ factors)
- SDK usage guide
- Deploys to GitHub Pages

## Working Process
1. Clone/pull the repo
2. Read existing code before modifying
3. Run tests after changes: `pytest tests/ -v`
4. Commit working code with descriptive messages

## Before Starting
```bash
cd altdata-platform
source venv/bin/activate
docker-compose up -d db redis
pytest tests/ -q  # Verify 200+ tests pass
```

## Your Task
Complete: [SPECIFY TASK NUMBER AND DETAILS]

Begin by examining the current codebase, then implement the task. Write tests for new functionality. Ensure all tests pass before considering the task complete.
