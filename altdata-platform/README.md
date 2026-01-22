# Alternative Data Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-200%2B-green.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Status:** Phase 3 Complete | 200+ tests | 80+ factors | Dashboard + SDK + Alerts + Backtesting

A platform that aggregates free alternative data (SEC filings, flight tracking, economic indicators, weather, sentiment, shipping, satellites) and computes quantitative factors for backtesting trading strategies.

## 🎯 Overview

This platform collects data from 12+ alternative data sources, computes 80+ quantitative factors, and serves them via REST API.

### Key Features

- **12+ Data Sources**: SEC EDGAR, FRED, ADS-B, Power Grid, USPTO, OpenAQ, Weather, Google Trends, Reddit, Shipping, GitHub, Satellite
- **80+ Factors**: Pre-computed quantitative signals across multiple categories
- **REST API**: FastAPI-powered endpoints with authentication
- **Point-in-Time**: All data stored with publication timestamps to prevent look-ahead bias
- **Backfill**: 6+ months of historical data available

## 📊 Data Sources

### Tier 1 (Highest Priority)
| Source | Category | Update Frequency | Factors |
|--------|----------|-----------------|---------|
| ADS-B Exchange | Aviation / M&A Signals | Real-time | 6 |
| SEC EDGAR | Regulatory / Fundamentals | Real-time | 8 |
| FRED | Macroeconomic | Daily-Quarterly | 7 |
| US Power Grid ISOs | Energy / Industrial | Real-time (5-min) | 8 |
| USPTO & EPO | Innovation / R&D | Weekly | 8 |
| OpenAQ | Environmental / Industrial Proxy | Hourly | 6 |
| BTS Freight | Transportation | Monthly | 6 |

### Tier 2 (High Priority)
- NOAA/NWS Weather Data
- Sentinel-2 Satellite Imagery
- Google Trends
- Reddit API
- MarineTraffic / AIS Data
- GitHub API

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │   Web    │  │  Python  │  │  Excel   │  │    R     │        │
│  │Dashboard │  │   SDK    │  │  Plugin  │  │ Package  │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
└───────┼─────────────┼─────────────┼─────────────┼───────────────┘
        │             │             │             │
┌───────┴─────────────┴─────────────┴─────────────┴───────────────┐
│                         API LAYER                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              FastAPI REST + GraphQL + WebSocket            │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                    TRANSFORMATION LAYER                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Factor    │  │     ML      │  │   Entity    │             │
│  │   Engine    │  │  Pipelines  │  │ Resolution  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                      STORAGE LAYER                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Raw Data │  │ Processed│  │Time-Series│ │  Cache   │        │
│  │  (S3)    │  │(Snowflake)│ │(Timescale)│ │ (Redis)  │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                     INGESTION LAYER                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │   API    │  │   Web    │  │   File   │  │  Stream  │        │
│  │Collectors│  │ Scrapers │  │Downloaders│ │Processors│        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with TimescaleDB extension
- Redis 7+
- Docker (recommended)

### Installation

```bash
# Clone repository
git clone https://github.com/KTMAnimations/alternative-data.git
cd alternative-data/altdata-platform

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your configuration

# Initialize database
python scripts/init_db.py

# Run migrations
alembic upgrade head

# Start collectors (development)
python -m src.collectors.run_all

# Start API server
uvicorn src.api.main:app --reload
```

### Verify Installation

```bash
# Run tests
pytest tests/ -v

# Check API health
curl http://localhost:8000/health

# Query a factor
curl http://localhost:8000/api/v1/factors/insider_momentum?ticker=AAPL
```

## 📁 Project Structure

```
altdata-platform/
├── README.md
├── PRD.md                    # Project requirements (source of truth)
├── ARCHITECTURE.md
├── DEVELOPMENT.md
├── DATA_SOURCES.md
├── DEPLOYMENT.md
├── requirements.txt
├── docker-compose.yml
├── src/
│   ├── __init__.py
│   ├── config/               # Settings and configuration
│   ├── collectors/           # Data source collectors
│   ├── transformations/      # Factor computations
│   │   └── factors/
│   ├── api/                  # FastAPI endpoints
│   ├── models/               # SQLAlchemy models
│   └── utils/
├── tests/                    # 200+ tests
├── scripts/
│   ├── init_db.py
│   └── backfill.py
└── dags/                     # Airflow DAGs
```

## 📈 Sample API Queries

```bash
# List all factors
curl http://localhost:8000/api/v1/factors

# Get factor values for an entity
curl "http://localhost:8000/api/v1/factors/insider_transaction_momentum?entity_id=AAPL&start_date=2024-01-01"

# List entities
curl http://localhost:8000/api/v1/entities

# Check data source status
curl http://localhost:8000/api/v1/sources/status
```

## 🗺️ Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| MVP | SEC EDGAR + FRED collectors, basic API | ✅ Complete |
| Phase 1 | +ADS-B, Power Grid, USPTO, OpenAQ | ✅ Complete |
| Phase 2 | +Weather, Trends, Reddit, Shipping, GitHub, Satellite | ✅ Complete |
| Phase 3 | Dashboard, Python SDK, Alerts, Backtesting | ✅ Complete |
| Phase 4 | AWS Deployment, Production Hardening | ⏳ Next |

## 🤝 Contributing

See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup and guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## ⚠️ Disclaimer

This platform is for informational purposes only and does not constitute investment advice. Alternative data strategies involve significant risks. Past performance does not guarantee future results.
