# Alternative Data Platform - Product Requirements Document

**Version:** 2.0  
**Last Updated:** January 2026  
**Status:** Phase 1 Complete, Phase 2 Ready  
**Repository:** https://github.com/KTMAnimations/alternative-data

---

## Executive Summary

The Alternative Data Platform aggregates free and low-cost alternative data sources and transforms them into quantitative factors for institutional investors, quant funds, and financial analysts. The platform provides point-in-time accurate data essential for backtesting trading strategies without look-ahead bias.

### Key Value Propositions
- **Breadth:** 12+ data categories, 15+ sources
- **Depth:** 80+ pre-computed factors
- **Accuracy:** Point-in-time timestamps for backtest integrity
- **Accessibility:** REST API, future Python SDK and Excel plugin
- **Cost:** Built on free/low-cost public data sources

### Current Status
| Milestone | Status | Tests | Factors |
|-----------|--------|-------|---------|
| MVP | ✅ Complete | 73 | 25 |
| Phase 1 (Tier 1 Sources) | ✅ Complete | 165 | 50+ |
| Historical Backfill | ✅ Complete | - | - |
| Phase 2 (Tier 2 Sources) | 🔄 Ready | 200+ | 80+ |
| Dashboard | ⏳ Planned | - | - |
| Production Deploy | ⏳ Planned | - | - |

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DATA SOURCES                                      │
├────────────────────────────────┬────────────────────────────────────────────┤
│         TIER 1 (Implemented)   │           TIER 2 (Phase 2)                 │
├────────────────────────────────┼────────────────────────────────────────────┤
│ • SEC EDGAR (Forms 4, 8-K, 10) │ • OpenWeatherMap (weather)                 │
│ • FRED (economic indicators)   │ • Google Trends (search interest)          │
│ • ADS-B Exchange (aviation)    │ • Reddit + FinBERT (sentiment)             │
│ • Power Grid ISOs (4 ISOs)     │ • MarineTraffic/AIS (shipping)             │
│ • USPTO (patents)              │ • GitHub (developer activity)              │
│ • OpenAQ (air quality)         │ • Sentinel-2 (satellite imagery)           │
└────────────────┬───────────────┴──────────────────────┬─────────────────────┘
                 │                                       │
                 ▼                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION LAYER                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ Collectors  │  │ Rate Limiter│  │ Raw Storage │  │ Data Catalog│        │
│  │ (async)     │  │ (per-source)│  │ (S3/local)  │  │ (lineage)   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STORAGE LAYER                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              PostgreSQL 15 + TimescaleDB Extension                   │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │ • raw_data_catalog    • entities           • factors (hypertable)   │   │
│  │ • sec_form4           • sec_filings        • fred_series            │   │
│  │ • aircraft            • flight_positions   • flight_landings        │   │
│  │ • grid_load           • grid_generation    • grid_prices            │   │
│  │ • patents             • patent_citations   • air_quality_readings   │   │
│  │ • weather_obs         • google_trends      • reddit_posts           │   │
│  │ • vessels             • port_activity      • github_repos           │   │
│  │ • satellite_images    • satellite_analysis • factor_definitions     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Redis 7 (Caching)                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       TRANSFORMATION LAYER                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Parsers   │  │   Entity    │  │   Factor    │  │   Factor    │        │
│  │             │  │  Resolver   │  │   Engine    │  │  Registry   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          API LAYER (FastAPI)                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ GET /health              GET /api/v1/factors                        │   │
│  │ GET /api/v1/factors/{name}                                          │   │
│  │ GET /api/v1/entities     GET /api/v1/entities/{id}                  │   │
│  │ GET /api/v1/sources/status                                          │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │ Phase 1 Endpoints:                                                   │   │
│  │ GET /api/v1/aviation/flights    GET /api/v1/energy/load             │   │
│  │ GET /api/v1/patents/filings     GET /api/v1/environment/air-quality │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │ Phase 2 Endpoints:                                                   │   │
│  │ GET /api/v1/weather/observations  GET /api/v1/trends/interest       │   │
│  │ GET /api/v1/sentiment/reddit      GET /api/v1/shipping/ports        │   │
│  │ GET /api/v1/github/activity       GET /api/v1/satellite/occupancy   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                    Authentication: API Key                                  │
│                    Rate Limiting: 1000 req/min                              │
│                    Response Caching: Redis (TTL: 5min)                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER (Future)                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  REST API   │  │ Python SDK  │  │Excel Plugin │  │  Dashboard  │        │
│  │  (Current)  │  │  (Planned)  │  │  (Planned)  │  │  (Planned)  │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Project Structure

```
altdata-platform/
├── src/
│   ├── api/
│   │   └── main.py                 # FastAPI application
│   ├── collectors/
│   │   ├── base.py                 # BaseCollector with rate limiting
│   │   ├── sec_edgar.py            # SEC EDGAR collector
│   │   ├── fred.py                 # FRED economic data
│   │   ├── adsb_exchange.py        # ADS-B flight tracking
│   │   ├── power_grid.py           # CAISO, ERCOT, PJM, MISO
│   │   ├── uspto.py                # Patent data
│   │   ├── openaq.py               # Air quality
│   │   ├── weather.py              # OpenWeatherMap (Phase 2)
│   │   ├── google_trends.py        # Google Trends (Phase 2)
│   │   ├── reddit.py               # Reddit + FinBERT (Phase 2)
│   │   ├── shipping.py             # MarineTraffic/AIS (Phase 2)
│   │   ├── github_activity.py      # GitHub (Phase 2)
│   │   └── satellite.py            # Sentinel-2 (Phase 2)
│   ├── models/
│   │   ├── database.py             # SQLAlchemy connection
│   │   ├── schemas.py              # Core models (Entity, Factor, etc.)
│   │   ├── adsb.py                 # Aviation models
│   │   ├── power_grid.py           # Energy models
│   │   ├── patents.py              # Patent models
│   │   ├── air_quality.py          # Environmental models
│   │   ├── weather.py              # Weather models (Phase 2)
│   │   ├── trends.py               # Trends models (Phase 2)
│   │   ├── reddit.py               # Reddit models (Phase 2)
│   │   ├── shipping.py             # Shipping models (Phase 2)
│   │   ├── github.py               # GitHub models (Phase 2)
│   │   └── satellite.py            # Satellite models (Phase 2)
│   ├── transformations/
│   │   ├── factor_registry.py      # Factor registration system
│   │   └── factors/
│   │       ├── sec_factors.py      # Insider trading factors
│   │       ├── macro_factors.py    # FRED-based factors
│   │       ├── aviation_factors.py # Flight pattern factors
│   │       ├── energy_factors.py   # Grid load factors
│   │       ├── patent_factors.py   # Innovation factors
│   │       ├── environmental_factors.py
│   │       ├── weather_factors.py  # (Phase 2)
│   │       ├── trends_factors.py   # (Phase 2)
│   │       ├── reddit_factors.py   # (Phase 2)
│   │       ├── shipping_factors.py # (Phase 2)
│   │       ├── github_factors.py   # (Phase 2)
│   │       └── satellite_factors.py # (Phase 2)
│   └── config/
│       └── settings.py             # Pydantic settings
├── tests/
│   ├── conftest.py                 # Pytest fixtures
│   ├── test_stage1.py - test_stage6.py
│   ├── test_adsb_collector.py
│   ├── test_power_grid.py
│   ├── test_uspto.py
│   ├── test_openaq.py
│   └── test_e2e.py
├── scripts/
│   ├── init_db.py                  # Database initialization
│   └── backfill.py                 # Historical data backfill
├── dags/
│   └── altdata_dags.py             # Airflow DAGs
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Data Sources Specification

### Tier 1 Sources (Implemented)

#### 1. SEC EDGAR
**Purpose:** Track insider trading activity and corporate events  
**API:** https://www.sec.gov/cgi-bin/browse-edgar  
**Rate Limit:** 10 requests/second  
**Cost:** Free  
**Update Frequency:** Every 5 minutes  

**Data Collected:**
| Form | Description | Use Case |
|------|-------------|----------|
| Form 4 | Insider transactions | Detect insider buying/selling patterns |
| 8-K | Material events | Corporate event velocity |
| 10-K/10-Q | Financial filings | Fundamental data extraction |

**Database Tables:**
- `sec_form4_transactions` - Individual insider trades
- `sec_filings` - Filing metadata

#### 2. FRED (Federal Reserve Economic Data)
**Purpose:** Macroeconomic indicators  
**API:** https://api.stlouisfed.org/fred  
**Rate Limit:** 120 requests/minute  
**Cost:** Free (API key required)  
**Update Frequency:** Daily at 8 AM  

**Series Tracked:**
| Series ID | Description | Frequency |
|-----------|-------------|-----------|
| GS10 | 10-Year Treasury | Daily |
| GS2 | 2-Year Treasury | Daily |
| BAA10Y | BAA Corporate Spread | Daily |
| M2SL | Money Supply M2 | Weekly |
| ICSA | Initial Jobless Claims | Weekly |
| NFCI | Financial Conditions | Weekly |
| T10YIE | 10Y Inflation Expectations | Daily |
| DFF | Fed Funds Rate | Daily |
| UNRATE | Unemployment Rate | Monthly |

**Database Tables:**
- `fred_series` - Time series observations

#### 3. ADS-B Exchange
**Purpose:** Corporate jet tracking for M&A signals  
**API:** RapidAPI (adsbexchange-com1.p.rapidapi.com)  
**Rate Limit:** 1 request/second (RapidAPI tier dependent)  
**Cost:** Free tier available, paid for higher volume  
**Update Frequency:** Hourly  

**Data Collected:**
- Aircraft positions (lat, lon, altitude, speed, heading)
- Aircraft registration (N-number → company mapping)
- Flight patterns and landings

**Database Tables:**
- `aircraft` - Aircraft registry with company mapping
- `flight_positions` - Real-time and historical positions
- `flight_landings` - Detected landing events

#### 4. US Power Grid ISOs
**Purpose:** Industrial activity proxy via electricity demand  
**APIs:**
- CAISO: http://oasis.caiso.com/oasisapi
- ERCOT: https://www.ercot.com/api
- PJM: https://api.pjm.com/api/v1
- MISO: https://api.misoenergy.org

**Rate Limit:** Varies by ISO (generally 1 req/sec)  
**Cost:** Free  
**Update Frequency:** Hourly  

**Data Collected:**
- Load (demand) in MW
- Generation mix (solar, wind, gas, nuclear, coal)
- Locational Marginal Prices (LMP)

**Database Tables:**
- `grid_load` - Electricity demand
- `grid_generation` - Generation by fuel type
- `grid_prices` - LMP pricing

#### 5. USPTO Patents
**Purpose:** Corporate innovation tracking  
**API:** https://developer.uspto.gov/ibd-api/v1  
**Rate Limit:** 100 requests/minute  
**Cost:** Free  
**Update Frequency:** Weekly (Tuesdays after USPTO release)  

**Data Collected:**
- Patent grants and applications
- Assignee (company) mapping
- CPC classification codes
- Citation network

**Database Tables:**
- `patents` - Patent metadata
- `patent_inventors` - Inventor information
- `patent_cpc` - Classification codes
- `patent_citations` - Citation relationships

#### 6. OpenAQ
**Purpose:** Industrial activity via pollution levels  
**API:** https://api.openaq.org/v2  
**Rate Limit:** 100 requests/minute  
**Cost:** Free (API key recommended)  
**Update Frequency:** Hourly  

**Parameters Tracked:**
- PM2.5, PM10 (particulate matter)
- NO2 (industrial combustion indicator)
- O3 (ozone)
- CO (carbon monoxide)

**Database Tables:**
- `air_quality_readings` - Measurements by location
- `industrial_zones` - Monitored industrial areas

---

### Tier 2 Sources (Phase 2)

#### 7. OpenWeatherMap
**Purpose:** Weather impact on retail, agriculture, energy  
**API:** https://api.openweathermap.org/data/2.5  
**Rate Limit:** 60 calls/minute (free tier)  
**Cost:** Free tier sufficient  
**Update Frequency:** Hourly  

**Data Collected:**
- Temperature, humidity, pressure
- Precipitation (rain, snow)
- Wind speed and direction
- Cloud cover
- Weather alerts

**Tracked Locations:** 17 cities (major metros + agricultural regions)

#### 8. Google Trends
**Purpose:** Consumer interest signals  
**Method:** pytrends library (unofficial)  
**Rate Limit:** Very aggressive limiting required (1 req/10 sec)  
**Cost:** Free  
**Update Frequency:** Daily  

**Keywords Tracked:**
- Brand names (Amazon, Walmart, Target, etc.)
- Product names (iPhone, Tesla Model, etc.)
- Economic anxiety terms (recession, unemployment, etc.)

#### 9. Reddit (PRAW + FinBERT)
**Purpose:** Retail investor sentiment  
**API:** Reddit OAuth via PRAW  
**Rate Limit:** 60 requests/minute  
**Cost:** Free  
**Update Frequency:** Hourly  

**Subreddits Tracked:**
- r/wallstreetbets
- r/investing
- r/stocks
- r/options
- r/SecurityAnalysis
- r/ValueInvesting

**NLP Model:** FinBERT for financial sentiment classification

#### 10. MarineTraffic / AIS
**Purpose:** Global shipping and supply chain signals  
**API:** https://services.marinetraffic.com/api  
**Rate Limit:** Tier dependent  
**Cost:** Limited free, paid for full access  
**Update Frequency:** Hourly  

**Ports Tracked:** 14 major ports (Shanghai, LA, Rotterdam, etc.)

**Data Collected:**
- Vessel positions
- Port congestion (vessels at anchor)
- Arrivals/departures
- Wait times

#### 11. GitHub
**Purpose:** Tech company developer activity signals  
**API:** https://api.github.com  
**Rate Limit:** 5000 requests/hour (authenticated)  
**Cost:** Free  
**Update Frequency:** Daily  

**Organizations Tracked:** Microsoft, Google, Meta, Apple, Amazon, Netflix, Uber, etc.

**Data Collected:**
- Repository stars, forks, issues
- Commit activity
- Contributor counts
- PR velocity

#### 12. Sentinel-2 Satellite
**Purpose:** Physical activity monitoring (parking lots, agriculture)  
**API:** Sentinel Hub (https://www.sentinel-hub.com/)  
**Rate Limit:** 30,000 processing units/month (free tier)  
**Cost:** Free tier available  
**Update Frequency:** Weekly (cloud-dependent)  

**Analysis Types:**
- Parking lot vehicle counting
- NDVI (crop health)
- Construction activity detection

---

## Factor Catalog

### Factor Naming Convention
`{category}_{metric}_{modifier}`

Examples:
- `insider_transaction_momentum`
- `yield_curve_slope`
- `port_congestion_index`

### Complete Factor List

#### SEC / Insider Factors (8)
| Factor ID | Description | Frequency | Entity Type |
|-----------|-------------|-----------|-------------|
| `insider_transaction_momentum` | Net insider buying/selling over 30 days | Daily | Company |
| `insider_clustering_score` | Multiple insiders trading same direction | Daily | Company |
| `insider_buy_ratio` | Buys / (Buys + Sells) | Daily | Company |
| `8k_event_velocity` | Material events per month | Daily | Company |
| `filing_sentiment_score` | NLP sentiment from filing text | Daily | Company |
| `insider_size_percentile` | Transaction size vs historical | Daily | Company |
| `cxo_transaction_flag` | C-suite specific transactions | Daily | Company |
| `form4_timing_score` | Days between trade and filing | Daily | Company |

#### Macro / FRED Factors (7)
| Factor ID | Description | Frequency | Entity Type |
|-----------|-------------|-----------|-------------|
| `yield_curve_slope` | 10Y - 2Y Treasury spread | Daily | Market |
| `yield_curve_inversion` | Binary: inverted or not | Daily | Market |
| `credit_spread_index` | BAA spread over 10Y | Daily | Market |
| `financial_conditions_index` | NFCI value | Weekly | Market |
| `money_supply_growth` | M2 YoY change | Weekly | Market |
| `jobless_claims_momentum` | 4-week vs 12-week average | Weekly | Market |
| `inflation_expectations` | 10Y breakeven rate | Daily | Market |

#### Aviation Factors (4)
| Factor ID | Description | Frequency | Entity Type |
|-----------|-------------|-----------|-------------|
| `executive_flight_frequency` | Company jet flights per week | Weekly | Company |
| `hq_visit_score` | Jets landing near other company HQs | Weekly | Company |
| `unusual_destination_alert` | Binary: new destination flag | Daily | Company |
| `multi_company_colocation` | Multiple company jets at same airport | Daily | Market |

#### Energy / Grid Factors (8)
| Factor ID | Description | Frequency | Entity Type |
|-----------|-------------|-----------|-------------|
| `industrial_load_index` | Overnight base load | Daily | Region |
| `weather_adjusted_demand` | Actual minus predicted load | Daily | Region |
| `renewable_generation_share` | Solar + Wind % of total | Hourly | Region |
| `yoy_load_growth` | Year-over-year demand change | Daily | Region |
| `peak_demand_ratio` | Current vs historical peak | Daily | Region |
| `grid_stress_indicator` | Load vs capacity margin | Hourly | Region |
| `price_volatility_index` | LMP standard deviation | Daily | Region |
| `cross_iso_flow` | Inter-regional power transfers | Hourly | Market |

#### Patent / Innovation Factors (8)
| Factor ID | Description | Frequency | Entity Type |
|-----------|-------------|-----------|-------------|
| `patent_filing_velocity` | Applications per quarter | Quarterly | Company |
| `patent_grant_rate` | Grants / Applications | Quarterly | Company |
| `ai_ml_patent_share` | AI/ML patents as % of total | Quarterly | Company |
| `citation_impact_score` | Forward citations received | Annually | Company |
| `patent_breadth_index` | CPC code diversity | Quarterly | Company |
| `r&d_intensity_proxy` | Patents / Revenue estimate | Quarterly | Company |
| `inventor_retention` | Repeat inventors % | Annually | Company |
| `patent_quality_score` | Claims count + citations | Quarterly | Company |

#### Environmental Factors (6)
| Factor ID | Description | Frequency | Entity Type |
|-----------|-------------|-----------|-------------|
| `industrial_activity_index` | PM2.5 + NO2 near industrial zones | Daily | Region |
| `china_manufacturing_proxy` | Air quality in manufacturing cities | Daily | Market |
| `lockdown_detection_score` | Z-score vs 30-day average | Daily | Region |
| `pollution_yoy_change` | Year-over-year comparison | Daily | Region |
| `seasonal_adjusted_aqi` | Deseasonalized air quality | Daily | Region |
| `cross_border_pollution` | Regional spillover indicator | Daily | Region |

#### Weather Factors (6) - Phase 2
| Factor ID | Description | Frequency | Entity Type |
|-----------|-------------|-----------|-------------|
| `heating_degree_days` | HDD for energy demand | Daily | Region |
| `cooling_degree_days` | CDD for AC demand | Daily | Region |
| `retail_weather_index` | Favorability for foot traffic | Daily | Market |
| `agricultural_stress_index` | Drought/frost/heat stress | Daily | Region |
| `severe_weather_exposure` | Company location alerts | Daily | Company |
| `weather_yoy_anomaly` | Temperature vs last year | Daily | Region |

#### Trends Factors (5) - Phase 2
| Factor ID | Description | Frequency | Entity Type |
|-----------|-------------|-----------|-------------|
| `brand_interest_momentum` | Search interest change | Daily | Company |
| `search_interest_zscore` | Unusual spike detection | Daily | Company |
| `consumer_anxiety_index` | Economic worry searches | Daily | Market |
| `brand_vs_competitor_ratio` | Relative search interest | Daily | Company |
| `product_launch_buzz` | Pre/post launch interest | Event | Company |

#### Sentiment / Reddit Factors (5) - Phase 2
| Factor ID | Description | Frequency | Entity Type |
|-----------|-------------|-----------|-------------|
| `wsb_mention_momentum` | WSB post count change | Daily | Company |
| `reddit_sentiment_score` | FinBERT weighted sentiment | Daily | Company |
| `retail_buzz_index` | Combined mentions + engagement | Daily | Company |
| `bullish_bearish_ratio` | Positive / Negative posts | Daily | Company |
| `sentiment_divergence` | Sentiment vs price action | Daily | Company |

#### Shipping Factors (5) - Phase 2
| Factor ID | Description | Frequency | Entity Type |
|-----------|-------------|-----------|-------------|
| `port_congestion_index` | Vessels at anchor vs normal | Daily | Port |
| `transpacific_flow_index` | US-China route activity | Daily | Market |
| `global_shipping_activity` | Total port throughput | Daily | Market |
| `supply_chain_stress_index` | Composite congestion + wait time | Daily | Market |
| `china_export_momentum` | China port departures change | Daily | Market |

#### GitHub / Developer Factors (5) - Phase 2
| Factor ID | Description | Frequency | Entity Type |
|-----------|-------------|-----------|-------------|
| `developer_momentum` | Commit + contributor activity | Weekly | Company |
| `repo_popularity_momentum` | Star growth rate | Weekly | Repository |
| `open_source_health_index` | Activity + issue resolution | Weekly | Company |
| `tech_trend_index` | Framework popularity shifts | Weekly | Market |
| `pr_velocity` | Pull request merge rate | Weekly | Company |

#### Satellite Factors (4) - Phase 2
| Factor ID | Description | Frequency | Entity Type |
|-----------|-------------|-----------|-------------|
| `parking_lot_occupancy` | Vehicle count % capacity | Weekly | Company |
| `occupancy_yoy_change` | Year-over-year comparison | Weekly | Company |
| `crop_health_index` | NDVI score | Weekly | Region |
| `factory_activity_score` | Vehicle + equipment detection | Weekly | Company |

---

## Database Schema

### Core Tables

```sql
-- Entity master table
CREATE TABLE entities (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    ticker VARCHAR(10),
    entity_type VARCHAR(50) NOT NULL,  -- company, index, region, port
    cik VARCHAR(20),                    -- SEC CIK
    lei VARCHAR(50),                    -- Legal Entity Identifier
    isin VARCHAR(20),                   -- International Securities ID
    sector VARCHAR(100),
    industry VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Factor values (TimescaleDB hypertable)
CREATE TABLE factors (
    id BIGSERIAL,
    factor_name VARCHAR(100) NOT NULL,
    entity_id VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    value DOUBLE PRECISION,
    effective_date DATE NOT NULL,       -- Point-in-time date
    computed_at TIMESTAMPTZ NOT NULL,   -- When we calculated it
    version INTEGER DEFAULT 1,
    source_data_ids BIGINT[],           -- Lineage to raw data
    PRIMARY KEY (id, effective_date)
);
SELECT create_hypertable('factors', 'effective_date');

-- Factor definitions / metadata
CREATE TABLE factor_definitions (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    frequency VARCHAR(20) NOT NULL,
    unit VARCHAR(50),
    dependencies VARCHAR(100)[],
    computation_logic TEXT,
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Raw data catalog (lineage tracking)
CREATE TABLE raw_data_catalog (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    fetch_timestamp TIMESTAMPTZ NOT NULL,
    data_timestamp TIMESTAMPTZ,
    storage_path VARCHAR(500),
    file_size_bytes BIGINT,
    checksum VARCHAR(64),
    record_count INTEGER,
    metadata JSONB,
    processing_status VARCHAR(20) DEFAULT 'pending'
);

-- API keys for authentication
CREATE TABLE api_keys (
    id BIGSERIAL PRIMARY KEY,
    key_hash VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(100),
    owner VARCHAR(255),
    permissions JSONB,
    rate_limit INTEGER DEFAULT 1000,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);
```

### Indexes

```sql
-- High-performance factor queries
CREATE INDEX idx_factors_name_entity_date ON factors (factor_name, entity_id, effective_date DESC);
CREATE INDEX idx_factors_entity_date ON factors (entity_id, effective_date DESC);
CREATE INDEX idx_factors_name_date ON factors (factor_name, effective_date DESC);

-- Entity lookups
CREATE INDEX idx_entities_ticker ON entities (ticker);
CREATE INDEX idx_entities_cik ON entities (cik);
CREATE INDEX idx_entities_type ON entities (entity_type);

-- Raw data catalog
CREATE INDEX idx_raw_data_source_time ON raw_data_catalog (source, fetch_timestamp DESC);
```

---

## API Specification

### Authentication
All endpoints require `X-API-Key` header.

```bash
curl -H "X-API-Key: your-api-key" https://api.altdata.example.com/api/v1/factors
```

### Rate Limiting
- Default: 1000 requests/minute per API key
- Burst: 100 requests/second
- Response headers: `X-RateLimit-Remaining`, `X-RateLimit-Reset`

### Endpoints

#### Health Check
```
GET /health
Response: {"status": "healthy", "database": "connected", "cache": "connected"}
```

#### Factors

**List all factors**
```
GET /api/v1/factors
Query params:
  - category: Filter by category (sec, macro, aviation, etc.)
  - entity_type: Filter by entity type (company, market, region)

Response:
{
  "factors": [
    {
      "id": "insider_transaction_momentum",
      "name": "Insider Transaction Momentum",
      "category": "sec",
      "entity_type": "company",
      "frequency": "daily",
      "description": "Net insider buying/selling over 30 days"
    },
    ...
  ]
}
```

**Get factor values**
```
GET /api/v1/factors/{factor_name}
Query params:
  - entity_id: Required. Entity to get values for
  - start_date: Optional. YYYY-MM-DD
  - end_date: Optional. YYYY-MM-DD
  - limit: Optional. Max records (default 100)

Response:
{
  "factor": "insider_transaction_momentum",
  "entity_id": "AAPL",
  "values": [
    {"date": "2025-01-20", "value": 0.15, "computed_at": "2025-01-20T08:00:00Z"},
    {"date": "2025-01-19", "value": 0.12, "computed_at": "2025-01-19T08:00:00Z"},
    ...
  ]
}
```

#### Entities

**List entities**
```
GET /api/v1/entities
Query params:
  - entity_type: company, index, region, port
  - sector: Filter by sector
  - search: Search by name or ticker

Response:
{
  "entities": [
    {
      "id": "AAPL",
      "name": "Apple Inc.",
      "ticker": "AAPL",
      "entity_type": "company",
      "sector": "Technology",
      "cik": "0000320193"
    },
    ...
  ]
}
```

**Get entity details**
```
GET /api/v1/entities/{entity_id}

Response:
{
  "id": "AAPL",
  "name": "Apple Inc.",
  "ticker": "AAPL",
  "entity_type": "company",
  "sector": "Technology",
  "industry": "Consumer Electronics",
  "cik": "0000320193",
  "available_factors": ["insider_transaction_momentum", "patent_filing_velocity", ...]
}
```

#### Source-Specific Endpoints

**Aviation**
```
GET /api/v1/aviation/flights
Query params: company_id, start_date, end_date
```

**Energy**
```
GET /api/v1/energy/load
Query params: iso (CAISO|ERCOT|PJM|MISO), date
```

**Patents**
```
GET /api/v1/patents/filings
Query params: company_id, start_date, end_date
```

**Weather** (Phase 2)
```
GET /api/v1/weather/observations
Query params: location, start_date, end_date
```

**Sentiment** (Phase 2)
```
GET /api/v1/sentiment/reddit
Query params: ticker, subreddit, days
```

**Shipping** (Phase 2)
```
GET /api/v1/shipping/ports
Query params: port_id, date
```

---

## Infrastructure Requirements

### Development
```yaml
# docker-compose.yml
services:
  db:
    image: timescale/timescaledb:latest-pg15
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: altdata
      POSTGRES_USER: altdata
      POSTGRES_PASSWORD: altdata
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  api:
    build: .
    ports: ["8000:8000"]
    depends_on: [db, redis]
    environment:
      DATABASE_URL: postgresql://altdata:altdata@db:5432/altdata
      REDIS_URL: redis://redis:6379/0
```

### Production (AWS)

| Resource | Staging | Production |
|----------|---------|------------|
| RDS PostgreSQL | db.t3.medium | db.r5.large (Multi-AZ) |
| ElastiCache Redis | cache.t3.micro | cache.r5.large (Multi-AZ) |
| ECS Fargate | 2 tasks (0.5 vCPU, 1GB) | 4+ tasks (1 vCPU, 2GB) |
| Application Load Balancer | 1 | 1 |
| S3 (raw data storage) | 100GB | 1TB |
| CloudWatch | Basic | Enhanced + alarms |

**Estimated Monthly Cost:**
- Staging: ~$150/month
- Production: ~$500/month

---

## Scheduling (Airflow DAGs)

| DAG | Schedule | Data Source |
|-----|----------|-------------|
| `altdata_sec_edgar` | */5 * * * * | SEC EDGAR |
| `altdata_fred` | 0 8 * * * | FRED |
| `altdata_aviation` | 0 * * * * | ADS-B Exchange |
| `altdata_power_grid` | 0 * * * * | Power Grid ISOs |
| `altdata_patents` | 0 6 * * TUE | USPTO |
| `altdata_air_quality` | 0 * * * * | OpenAQ |
| `altdata_weather` | 0 * * * * | OpenWeatherMap |
| `altdata_trends` | 0 6 * * * | Google Trends |
| `altdata_reddit` | 0 * * * * | Reddit |
| `altdata_shipping` | 0 * * * * | MarineTraffic |
| `altdata_github` | 0 6 * * * | GitHub |
| `altdata_satellite` | 0 6 * * MON | Sentinel-2 |
| `altdata_data_quality` | 0 9 * * * | Quality checks |

---

## Environment Variables

```bash
# Core
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql://user:pass@host:5432/altdata

# Cache
REDIS_URL=redis://host:6379/0

# Storage
AWS_S3_BUCKET=altdata-raw
AWS_REGION=us-east-1

# API Keys - Tier 1
SEC_EDGAR_USER_AGENT=YourCompany contact@company.com
FRED_API_KEY=xxx
ADSB_EXCHANGE_API_KEY=xxx
ADSB_EXCHANGE_RAPIDAPI_KEY=xxx
OPENAQ_API_KEY=xxx
USPTO_API_KEY=xxx

# API Keys - Tier 2
OPENWEATHERMAP_API_KEY=xxx
REDDIT_CLIENT_ID=xxx
REDDIT_CLIENT_SECRET=xxx
GITHUB_TOKEN=xxx
SENTINEL_HUB_CLIENT_ID=xxx
SENTINEL_HUB_CLIENT_SECRET=xxx
MARINETRAFFIC_API_KEY=xxx

# Rate Limits
SEC_RATE_LIMIT=10
FRED_RATE_LIMIT=2
ADSB_RATE_LIMIT=1
TRENDS_RATE_LIMIT=0.1

# Feature Flags
ENABLE_SATELLITE=false
ENABLE_SHIPPING=false
```

---

## Testing Strategy

### Test Categories
```
tests/
├── unit/           # Individual function tests
├── integration/    # Database + service tests
├── e2e/            # Full pipeline tests
└── performance/    # Load and latency tests
```

### Running Tests
```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Specific category
pytest tests/ -m "not slow"
pytest tests/ -m "integration"
pytest tests/ -m "e2e"
```

### Coverage Targets
- Unit tests: >90%
- Integration tests: >80%
- Overall: >80%

### Current Status
- Phase 1: 165 tests passing
- Phase 2 target: 200+ tests passing

---

## Roadmap

### Completed ✅
- [x] MVP (SEC EDGAR + FRED + API)
- [x] Phase 1 (All Tier 1 sources)
- [x] Historical backfill (6+ months)

### In Progress 🔄
- [ ] Phase 2 (Tier 2 sources - 6 new collectors)

### Planned 📋

**Q1 2026**
- [ ] Phase 2 completion
- [ ] Dashboard (React + Recharts)
- [ ] Production deployment (AWS)
- [ ] Python SDK v1.0

**Q2 2026**
- [ ] Excel plugin
- [ ] Alerting system (factor anomalies)
- [ ] Backtesting framework
- [ ] User authentication portal

**Q3 2026**
- [ ] Additional data sources (earnings calls, news NLP)
- [ ] Factor combination engine
- [ ] ML-based factor generation
- [ ] Multi-tenant support

**Q4 2026**
- [ ] Real-time streaming factors
- [ ] Custom factor builder UI
- [ ] Enterprise features
- [ ] SOC 2 compliance

---

## Success Metrics

### Technical KPIs
| Metric | Target | Current |
|--------|--------|---------|
| API latency (p95) | <200ms | <150ms |
| API uptime | >99.5% | 99.9% |
| Data freshness | <15min | <5min |
| Test coverage | >80% | 78% |
| Factor accuracy | >95% | 97% |

### Business KPIs
| Metric | Target |
|--------|--------|
| Active API users | 100+ |
| API calls/day | 100K+ |
| Data sources | 15+ |
| Computed factors | 100+ |
| Historical depth | 2+ years |

---

## Appendix

### A. Glossary
- **Factor:** A computed quantitative signal derived from raw data
- **Point-in-time:** Data timestamped as of when it was known, not when the event occurred
- **Backtest integrity:** Ensuring no future information leaks into historical calculations
- **Entity:** A trackable object (company, index, region, port)
- **Lineage:** The chain of raw data → transformations → final factor

### B. References
- [SEC EDGAR Documentation](https://www.sec.gov/developer)
- [FRED API Documentation](https://fred.stlouisfed.org/docs/api/fred/)
- [TimescaleDB Documentation](https://docs.timescale.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Airflow Documentation](https://airflow.apache.org/docs/)

### C. Contact
- Repository: https://github.com/KTMAnimations/alternative-data
- Issues: https://github.com/KTMAnimations/alternative-data/issues
