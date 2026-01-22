# Ralph Loop Execution Guide

## Quick Start

### 1. Save the prompt to a file
```bash
# Save RALPH_PROMPT.md to your project root
cp RALPH_PROMPT.md ~/alternative-data/RALPH_PROMPT.md
```

### 2. Run ralph with a specific task

**Task 1: Dashboard**
```bash
ralph "$(cat RALPH_PROMPT.md)

Complete: TASK 1 - React Dashboard

Create the dashboard in altdata-platform/dashboard/ with:
- Vite + React 18 + Tailwind + Recharts + TanStack Query
- All 6 pages (Dashboard, Factors, FactorDetail, Entities, EntityDetail, Sources)
- FactorChart component with time series visualization
- EntityTable with sorting and search
- API client configured for VITE_API_URL
- Run: npm run dev should work
- All components render without errors"
```

**Task 2: Python SDK**
```bash
ralph "$(cat RALPH_PROMPT.md)

Complete: TASK 2 - Python SDK

Create altdata-sdk/ package with:
- AltDataClient class with methods: list_factors, get_factor, list_entities, get_entity, get_source_status
- Pydantic models: Factor, FactorValue, FactorData, Entity
- .to_dataframe() method returning pandas DataFrame
- Custom exceptions: AltDataError, AuthenticationError, RateLimitError
- pyproject.toml with all metadata
- README.md with usage examples
- tests/ with 90%+ coverage
- Run: pip install -e . should work"
```

**Task 3: AWS Deployment**
```bash
ralph "$(cat RALPH_PROMPT.md)

Complete: TASK 3 - AWS Deployment

Create terraform/ with modules for:
- VPC (2-3 AZs, public/private subnets)
- RDS PostgreSQL 15 with TimescaleDB
- ElastiCache Redis
- ECS Fargate cluster and service
- Application Load Balancer with HTTPS
- S3 bucket for raw data
- CloudWatch logs and alarms
- Secrets Manager for API keys

Plus .github/workflows/deploy.yml for CI/CD.
Run: terraform plan should work with AWS credentials"
```

**Task 4: Alerting System**
```bash
ralph "$(cat RALPH_PROMPT.md)

Complete: TASK 4 - Alerting System

Add to src/alerts/:
- Database migrations for alert_rules and alert_notifications tables
- AlertEngine class with check_all_rules() and calculate_zscore()
- SlackNotifier, EmailNotifier, WebhookNotifier classes
- API endpoints: POST/GET/PUT/DELETE /api/v1/alerts/rules
- Airflow DAG running every 5 minutes
- Tests for all alert logic
Run: pytest tests/test_alerts.py should pass"
```

**Task 5: Backtesting Framework**
```bash
ralph "$(cat RALPH_PROMPT.md)

Complete: TASK 5 - Backtesting Framework

Add to src/backtest/:
- BacktestEngine with run() method
- BacktestResult with sharpe_ratio, max_drawdown, ic_mean, turnover
- PriceProvider using yfinance for historical prices
- Metrics module: calculate_sharpe, calculate_max_drawdown, calculate_ic
- API endpoints: POST /api/v1/backtest/run, GET /api/v1/backtest/results/{id}
- Tests with mock price data
Run: pytest tests/test_backtest.py should pass"
```

**Task 6: Documentation Site**
```bash
ralph "$(cat RALPH_PROMPT.md)

Complete: TASK 6 - Documentation Site

Create docs/ with MkDocs:
- mkdocs.yml with material theme
- index.md, getting-started/, api-reference/, factors/, sdk/
- Document all 80+ factors with descriptions
- Document all API endpoints with examples
- SDK installation and usage guide
- GitHub Pages deployment config
Run: mkdocs serve should work"
```

---

## Single Command Format

If your ralph tool takes a single string:

```bash
ralph "You are an expert software engineer continuing development of the Alternative Data Platform.

Repository: https://github.com/KTMAnimations/alternative-data
Status: Phase 1 & 2 complete, 200+ tests, 80+ factors

Tech: Python 3.11, FastAPI, PostgreSQL+TimescaleDB, Redis, React

TASK: [TASK NUMBER] - [TASK NAME]

Requirements:
[PASTE SPECIFIC REQUIREMENTS FROM PRD.md]

Before starting:
cd altdata-platform && source venv/bin/activate && docker-compose up -d

Begin by examining existing code, implement the task, write tests, ensure all tests pass."
```

---

## Using with Claude Code CLI

If using Claude Code directly:

```bash
# Start Claude Code in the repo
cd ~/alternative-data/altdata-platform
claude

# Then paste the prompt + task
```

---

## Verification Commands

After each task, verify with:

```bash
# Task 1: Dashboard
cd dashboard && npm install && npm run dev

# Task 2: SDK  
cd altdata-sdk && pip install -e . && pytest tests/ -v

# Task 3: Deployment
cd terraform && terraform init && terraform plan

# Task 4: Alerting
pytest tests/test_alerts.py -v

# Task 5: Backtesting
pytest tests/test_backtest.py -v

# Task 6: Docs
cd docs && mkdocs serve
```

---

## Full Automated Loop

To run all tasks sequentially:

```bash
#!/bin/bash
# run_all_tasks.sh

TASKS=("dashboard" "sdk" "deployment" "alerting" "backtesting" "docs")

for task in "${TASKS[@]}"; do
    echo "Starting task: $task"
    ralph "$(cat RALPH_PROMPT.md)
    
Complete: TASK - $task
See PRD.md for detailed requirements."
    
    echo "Task $task complete. Verify and press enter to continue..."
    read
done

echo "All tasks complete!"
```
