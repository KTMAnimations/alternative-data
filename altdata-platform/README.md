# Alternative Data Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive alternative data platform that aggregates free and low-cost data sources, transforms raw data into actionable quantitative factors, and delivers signals to institutional investors.

## 🎯 Overview

This platform collects data from 15+ alternative data categories across 50+ sources, computes 200+ pre-built factors, and provides multiple access channels (REST API, Python SDK, Excel plugin).

### Key Value Propositions

- **Breadth**: Coverage across transportation, regulatory, environmental, energy, and macroeconomic data
- **Depth**: 200+ pre-computed factors with full transformation transparency
- **Ease of Use**: Unified API, web dashboard, and SDKs
- **Unique Data**: Novel factor combinations from under-exploited free sources
- **Point-in-Time**: All data stored with publication timestamps to prevent look-ahead bias

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
- Node.js 18+ (for dashboard)

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/altdata-platform.git
cd altdata-platform

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

# Start dashboard (separate terminal)
cd dashboard && npm install && npm run dev
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
├── ARCHITECTURE.md
├── DEVELOPMENT.md
├── DATA_SOURCES.md
├── IMPLEMENTATION_PROMPT.md
├── requirements.txt
├── .env.example
├── config/
│   ├── settings.py
│   └── logging.yaml
├── src/
│   ├── __init__.py
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── sec_edgar.py
│   │   ├── adsb_exchange.py
│   │   ├── fred.py
│   │   └── ...
│   ├── transformations/
│   │   ├── __init__.py
│   │   ├── factors/
│   │   │   ├── sec_factors.py
│   │   │   ├── aviation_factors.py
│   │   │   └── macro_factors.py
│   │   └── entity_resolution.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── routes/
│   │   └── middleware/
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── tests/
│   ├── __init__.py
│   ├── test_collectors/
│   ├── test_transformations/
│   └── test_api/
├── scripts/
│   ├── init_db.py
│   └── backfill.py
├── dashboard/
│   └── (React app)
└── docs/
    └── (Additional documentation)
```

## 📈 Sample Factor Query

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-key")

# Get insider trading momentum for AAPL
factor = client.get_factor(
    name="insider_transaction_momentum",
    ticker="AAPL",
    start_date="2024-01-01",
    end_date="2024-12-31"
)

# Get multiple factors
factors = client.get_factors(
    names=["insider_momentum", "8k_event_velocity", "filing_delay_score"],
    ticker="TSLA",
    start_date="2024-01-01"
)
```

## 🗺️ Roadmap

| Phase | Duration | Focus | Status |
|-------|----------|-------|--------|
| MVP | 8 weeks | Core infrastructure + SEC, ADS-B, FRED | 🚧 In Progress |
| Phase 1 | 6 weeks | Complete Tier 1 sources | ⏳ Planned |
| Phase 2 | 8 weeks | Tier 2 sources + Python SDK | ⏳ Planned |
| Phase 3 | 6 weeks | Scale + Excel/R plugins | ⏳ Planned |

## 🤝 Contributing

See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup and guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## ⚠️ Disclaimer

This platform is for informational purposes only and does not constitute investment advice. Alternative data strategies involve significant risks. Past performance does not guarantee future results.
