#!/bin/bash
# Claude Loop - Complete All Remaining Tasks
# Usage: ./run_claude_loop.sh

set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

GREEN='\033[0;32m'
NC='\033[0m'
log() { echo -e "${GREEN}[CLAUDE]${NC} $1"; }

log "=========================================="
log "CLAUDE LOOP - Alternative Data Platform"
log "=========================================="
log "Tasks: SDK → Docs → Dashboard → Deploy → Alerts → Backtest"
log "=========================================="

# Task 2: Python SDK
log "Starting TASK 2: Python SDK"
claude --dangerously-skip-permissions --print "You are an expert software engineer. Create a Python SDK in altdata-sdk/ directory (sibling to altdata-platform/).

Requirements:
- Create altdata-sdk/ with: altdata/__init__.py, altdata/client.py, altdata/models.py, altdata/exceptions.py
- AltDataClient class with methods: list_factors(), get_factor(name, entity_id), list_entities(), get_entity(id), get_source_status()
- Pydantic models for responses with .to_dataframe() returning pandas DataFrame
- pyproject.toml for pip install
- tests/test_client.py with 90%+ coverage
- README.md with usage examples

Check src/api/main.py for endpoint details. Run: pip install -e . && pytest to verify."

log "TASK 2 completed"

# Task 6: Documentation
log "Starting TASK 6: Documentation Site"
claude --dangerously-skip-permissions --print "You are an expert software engineer. Create MkDocs documentation in altdata-platform/docs/ directory.

Requirements:
- mkdocs.yml with material theme
- docs/index.md, getting-started/, api-reference/, factors/, sdk/
- Document all 80+ factors from src/transformations/factors/
- Document all API endpoints from src/api/
- Include code examples

Run: pip install mkdocs mkdocs-material && mkdocs serve to verify."

log "TASK 6 completed"

# Task 1: Dashboard
log "Starting TASK 1: React Dashboard"
claude --dangerously-skip-permissions --print "You are an expert software engineer. Create React dashboard in altdata-platform/dashboard/ directory.

Requirements:
- Vite + React 18 + Tailwind + Recharts + TanStack Query + React Router v6
- Pages: Dashboard(/), Factors(/factors), FactorDetail(/factors/:id), Entities(/entities), EntityDetail(/entities/:id), Sources(/sources)
- Components: Layout, FactorCard, FactorChart, EntityTable, SourceStatus, SearchBar
- API client connecting to VITE_API_URL (default http://localhost:8000)
- All API endpoints: /api/v1/factors, /api/v1/entities, /api/v1/sources/status

Run: npm install && npm run dev to verify."

log "TASK 1 completed"

# Task 3: AWS Deployment
log "Starting TASK 3: AWS Deployment"
claude --dangerously-skip-permissions --print "You are an expert software engineer. Create Terraform infrastructure in altdata-platform/terraform/ directory.

Requirements:
- modules/: vpc, rds, elasticache, ecs, alb, s3, cloudwatch
- main.tf, variables.tf, outputs.tf
- environments/staging.tfvars and production.tfvars
- Resources: VPC (2-3 AZs), RDS PostgreSQL 15, ElastiCache Redis, ECS Fargate, ALB with HTTPS, S3, CloudWatch
- Create .github/workflows/deploy.yml for CI/CD

Run: terraform init && terraform validate to verify."

log "TASK 3 completed"

# Task 4: Alerting
log "Starting TASK 4: Alerting System"
claude --dangerously-skip-permissions --print "You are an expert software engineer. Create alerting system in altdata-platform/src/alerts/ directory.

Requirements:
- models.py: AlertRule, AlertNotification SQLAlchemy models
- engine.py: AlertEngine with check_all_rules(), check_rule(), calculate_zscore()
- notifiers.py: SlackNotifier, EmailNotifier, WebhookNotifier classes
- routes.py: CRUD endpoints for /api/v1/alerts/rules and /api/v1/alerts/notifications
- Register routes in src/api/main.py
- Create tests/test_alerts.py
- Add Airflow DAG to dags/ for 5-minute checks

Run: pytest tests/test_alerts.py to verify."

log "TASK 4 completed"

# Task 5: Backtesting
log "Starting TASK 5: Backtesting Framework"
claude --dangerously-skip-permissions --print "You are an expert software engineer. Create backtesting framework in altdata-platform/src/backtest/ directory.

Requirements:
- engine.py: BacktestEngine.run(factor_name, universe, start_date, end_date, rebalance_freq, top_n)
- models.py: BacktestResult with returns, cumulative_returns, sharpe_ratio, max_drawdown, ic_mean, positions
- metrics.py: calculate_sharpe(), calculate_max_drawdown(), calculate_ic(), calculate_turnover()
- prices.py: PriceProvider using yfinance for historical prices
- routes.py: POST /api/v1/backtest/run, GET /api/v1/backtest/results/{job_id}
- Register routes in src/api/main.py
- Create tests/test_backtest.py

Run: pytest tests/test_backtest.py to verify."

log "TASK 5 completed"

log "=========================================="
log "ALL TASKS COMPLETED"
log "=========================================="
log "Verify:"
log "  SDK:       cd ../altdata-sdk && pip install -e . && pytest"
log "  Docs:      cd docs && mkdocs serve"
log "  Dashboard: cd dashboard && npm run dev"
log "  Terraform: cd terraform && terraform init && terraform plan"
log "  Alerting:  pytest tests/test_alerts.py"
log "  Backtest:  pytest tests/test_backtest.py"
log "=========================================="
