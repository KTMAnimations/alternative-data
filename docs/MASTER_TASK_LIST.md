# Alternative Data Platform - Master Task List

> **Source of Truth** for all implementation tasks.
> Aligned with PRD.md user stories and acceptance criteria.

---

## Table of Contents

1. [Foundation: Data Infrastructure](#foundation-data-infrastructure)
2. [Epic 1: Data Catalog Discovery](#epic-1-data-catalog-discovery)
3. [Epic 2: Factor Analysis](#epic-2-factor-analysis)
4. [Epic 3: Real-Time Monitoring](#epic-3-real-time-monitoring)
5. [Epic 4: Geographic Visualization](#epic-4-geographic-visualization)
6. [Epic 5: Backtesting & Research](#epic-5-backtesting--research)
7. [Epic 6: API Integration](#epic-6-api-integration)
8. [Epic 7: Entity Mapping](#epic-7-entity-mapping)
9. [Epic 8: Disaster & Event Signals](#epic-8-disaster--event-signals)
10. [Epic 9: Data Catalog Management](#epic-9-data-catalog-management)
11. [Epic 10: User Management & Tiers](#epic-10-user-management--tiers)

---

## Progress Summary

| Epic | User Stories | Status |
|------|--------------|--------|
| Foundation | 8 data sources | Complete |
| Epic 1 | US-001 to US-004 | Complete |
| Epic 2 | US-005 to US-008 | Complete |
| Epic 3 | US-009 to US-013 | Complete |
| Epic 4 | US-014 to US-016 | Complete |
| Epic 5 | US-017 to US-021 | Complete |
| Epic 6 | US-022 to US-026 | Complete |
| Epic 7 | US-027 to US-030 | Not Started |
| Epic 8 | US-031 to US-032 | Not Started |
| Epic 9 | US-033 to US-035 | Not Started |
| Epic 10 | US-036 to US-037 | Not Started |

---

## Foundation: Data Infrastructure

**Goal**: Implement Phase 1 data sources (8 free APIs) that power all platform features.
**Dependencies**: None
**Required for**: All Epics

---

### F-001: TSA Checkpoint Data

**Frequency**: Daily | **Latency**: 12h | **Entities**: DAL, UAL, AAL, LUV, JBLU, JETS

#### Data Acquisition
- [x] Research TSA.gov page structure at `https://www.tsa.gov/travel/passenger-volumes`
- [x] Test scraping approach and rate limits
- [x] Document data format (daily throughput, YoY comparison)

#### Collector Implementation
- [x] Create `src/collectors/tsa_checkpoint.py`
- [x] Inherit from `BaseCollector`
- [x] Implement `fetch()` with requests/BeautifulSoup
- [x] Implement `parse()` to extract daily figures
- [x] Add error handling for missing days
- [x] Implement historical backfill (2019-present)
- [x] Register in scheduler (daily at 10:00 AM ET)

#### Data Model
- [x] Create SQLAlchemy model `TSACheckpoint`
  - `date`, `current_year_throughput`, `prior_year_throughput`
  - `yoy_change_pct`, `day_of_week`, `is_holiday_period`
- [x] Create composite index on (date, day_of_week)
- [x] Generate and run Alembic migration

#### Factors
- [x] `TSAThroughputMomentum`: 7d rolling avg vs prior year
- [x] `TSAWeekdayWeekendRatio`: Business vs leisure travel mix
- [x] `TSAAirlineEnplanementNowcast`: Monthly enplanement estimate

#### Testing
- [x] Unit tests for collector and factors
- [x] Validate throughput in range 1M-4M
- [x] Verify no data gaps > 1 day

---

### F-002: OpenTable Reservations

**Frequency**: Weekly | **Latency**: 2d | **Entities**: DRI, MCD, SBUX, CMG, YUM

#### Data Acquisition
- [x] Research OpenTable State of Industry page
- [x] Identify JavaScript-rendered content requiring Playwright
- [x] Map available metrics (YoY seated diners by region)

#### Collector Implementation
- [x] Create `src/collectors/opentable.py`
- [x] Implement Playwright headless browser scraping
- [x] Parse regional breakdown (US, UK, Germany, Australia, Canada)
- [x] Handle anti-bot measures
- [x] Register in scheduler (weekly on Tuesday)
- [x] Implement historical backfill (2020-present)

#### Data Model
- [x] Create SQLAlchemy model `OpenTableMetrics`
  - `week_ending`, `region`, `city`, `yoy_seated_diners_pct`
- [x] Create composite index on (week_ending, region)
- [x] Generate and run Alembic migration

#### Factors
- [x] `SeatedDinersMomentum`: WoW change in YoY seated diners
- [x] `RegionalDiningSpread`: Max-min YoY across regions
- [x] `RestaurantSectorHealth`: 4-week rolling avg (0-100)

#### Testing
- [x] Unit tests for Playwright scraper
- [x] Validate YoY in range -100% to +200%
- [x] Backtest correlation with DRI earnings

---

### F-003: USGS Earthquake API

**Frequency**: Continuous | **Latency**: 15min | **Real-Time**: Yes | **Entities**: ALL, TRV, CB, PGR

#### Data Acquisition
- [x] Review USGS API at `https://earthquake.usgs.gov/fdsnws/event/1/`
- [x] Test GeoJSON endpoints
- [x] Document query parameters

#### Collector Implementation
- [x] Create `src/collectors/usgs_earthquake.py`
- [x] Implement REST API client
- [x] Query params: minmagnitude=4.0, format=geojson
- [x] Parse magnitude, location, depth, timestamp
- [x] Register for continuous polling (15-min intervals)
- [x] Implement historical backfill

#### Data Model
- [x] Create SQLAlchemy model `EarthquakeEvent`
  - `event_id`, `timestamp`, `latitude`, `longitude`
  - `depth_km`, `magnitude`, `magnitude_type`
  - `place_description`, `felt_reports`, `tsunami_flag`
- [x] Generate and run Alembic migration

#### Factors
- [x] `SeismicRiskExposure`: Asset proximity to events
- [x] `DisasterImpactEstimate`: Economic damage + insurer loss model

#### Testing
- [x] Unit tests for API client
- [x] Verify data arrives within 15 minutes of event
- [x] Validate magnitude values (0-10 scale)

---

### F-004: UK Carbon Intensity API

**Frequency**: 30min | **Latency**: 30min | **Entities**: NG.L, SSE.L

#### Data Acquisition
- [x] Review API at `https://carbonintensity.org.uk/`
- [x] Test endpoints: `/intensity`, `/generation`, `/regional`
- [x] Verify no authentication required

#### Collector Implementation
- [x] Create `src/collectors/carbon_intensity.py`
- [x] Fetch national and regional intensity data
- [x] Fetch generation mix (biomass, coal, gas, nuclear, solar, wind)
- [x] Register collector (30-minute intervals)
- [x] Implement historical backfill (2018-present)

#### Data Model
- [x] Create SQLAlchemy model `CarbonIntensityReading`
  - `timestamp`, `region`, `intensity_forecast`, `intensity_actual`
  - `intensity_index`, `generation_mix` (JSON)
- [x] Generate and run Alembic migration

#### Factors
- [x] `CarbonIntensityTrend`: MoM carbon intensity change
- [x] `RenewableShareGrowth`: % renewable trend

#### Testing
- [x] Unit tests for API client
- [x] Verify 30-minute data intervals
- [x] Validate intensity values (0-500 gCO2/kWh)

---

### F-005: FRED Building Permits

**Frequency**: Monthly | **Latency**: 3wk | **Entities**: DHI, LEN, PHM, HD, LOW

#### Data Acquisition
- [x] Review FRED API for PERMIT series
- [x] Identify related series (PERMITNSA, regional)
- [x] Verify FRED API key configuration

#### Collector Implementation
- [x] Extend `src/collectors/fred_collector.py`
- [x] Add PERMIT, PERMITNSA series
- [x] Add regional permit series
- [x] Verify historical backfill (1960-present)

#### Data Model
- [x] Create SQLAlchemy model `BuildingPermitData`
  - `period`, `geography_level`, `geography_code`
  - `permit_type`, `units_authorized`, `valuation`
- [x] Generate and run Alembic migration

#### Factors
- [x] `PermitMomentum`: MoM change in permit volume
- [x] `PermitToStartRatio`: Permits / housing starts
- [x] `RenovationShareIndex`: Renovation / new construction

#### Testing
- [x] Unit tests for extended FRED collector
- [x] Verify monthly data freshness
- [x] Validate permit values against Census BPS

---

### F-006: Movie Box Office

**Frequency**: Daily | **Latency**: 1d | **Entities**: DIS, WBD, PARA, CMCSA, SONY

#### Data Acquisition
- [x] Research TheNumbers page at `https://www.the-numbers.com/box-office-chart/daily`
- [x] Map available data (daily gross, theater count)
- [x] Document update schedule

#### Collector Implementation
- [x] Create `src/collectors/boxoffice.py`
- [x] Implement web scraper for daily/weekend charts
- [x] Parse movie title, distributor, gross, theaters
- [x] Handle cumulative gross tracking
- [x] Register collector (daily)
- [x] Implement historical backfill (1995-present)

#### Data Model
- [x] Create SQLAlchemy model `BoxOfficeDaily`
  - `date`, `movie_title`, `distributor`, `distributor_ticker`
  - `daily_gross`, `cumulative_gross`, `theater_count`
  - `per_theater_avg`, `days_in_release`
- [x] Generate and run Alembic migration

#### Factors
- [x] `OpeningWeekendSurprise`: Actual vs forecast
- [x] `StudioMarketShare`: Studio gross / total market

#### Entity Mapping
- [x] Create studio-to-ticker mapping (Disney→DIS, Warner→WBD, etc.)

#### Testing
- [x] Unit tests for scraper
- [x] Verify daily data freshness
- [x] Cross-reference with public announcements

---

### F-007: Cloudflare Radar API

**Frequency**: Hourly | **Latency**: 1h | **Real-Time**: Yes | **Entities**: NET, CRWD, PANW, ZS

#### Data Acquisition
- [x] Review Cloudflare Radar API documentation
- [x] Register for free API token
- [x] Test endpoints: `/traffic`, `/attacks`, `/outages`

#### Collector Implementation
- [x] Create `src/collectors/cloudflare_radar.py`
- [x] Implement REST API client with auth
- [x] Fetch global traffic, attack trends, outage data
- [x] Register collector (hourly)

#### Data Model
- [x] Create SQLAlchemy model `CloudflareRadarMetrics`
  - `timestamp`, `metric_type`, `region`, `value`, `metadata` (JSON)
- [x] Generate and run Alembic migration

#### Factors
- [x] `TrafficAnomalyIndex`: Deviation from baseline
- [x] `SecurityThreatLevel`: DDoS attack volume trends

#### Testing
- [x] Unit tests for API client
- [x] Verify hourly data collection
- [x] Validate anomaly detection accuracy

---

### F-008: Zillow Rental Data

**Frequency**: Monthly | **Latency**: 1mo | **Entities**: EQR, AVB, MAA, INVH, AMH

#### Data Acquisition
- [x] Review Zillow Research data at `https://www.zillow.com/research/data/`
- [x] Identify ZORI CSV files
- [x] Map geographic levels (national, metro, zip)

#### Collector Implementation
- [x] Create `src/collectors/zillow_rental.py`
- [x] Implement CSV download and parsing
- [x] Handle multiple geographic granularities
- [x] Register collector (monthly)
- [x] Implement historical backfill (2015-present)

#### Data Model
- [x] Create SQLAlchemy model `ZillowRentalIndex`
  - `period`, `geography_level`, `geography_id`, `geography_name`
  - `zori_value`, `mom_change_pct`, `yoy_change_pct`
- [x] Generate and run Alembic migration

#### Factors
- [x] `RentInflationIndex`: ZORI YoY change (CPI leading indicator)
- [x] `SFRMultifamilySpread`: Single-family vs apartment rent differential

#### Testing
- [x] Unit tests for CSV parser
- [x] Verify monthly data freshness
- [x] Validate index values reasonable

---

## Epic 1: Data Catalog Discovery

**Goal**: Enable users to browse, search, and preview available data sources.

---

### US-001: Browse Available Data Sources

**As a** fundamental analyst
**I want to** browse all available data sources in a searchable catalog
**So that** I can discover new alternative data relevant to my coverage universe

#### Backend Implementation
- [x] Create `DataSource` model with fields:
  - `name`, `description`, `category`, `update_frequency`
  - `latency`, `coverage`, `saturation_level`, `date_range`
- [x] Create FastAPI endpoint `GET /api/v1/catalog/sources`
- [x] Implement filtering by category (travel, real estate, energy, gaming, government, infrastructure)
- [x] Implement filtering by frequency (continuous, hourly, daily, weekly, monthly)
- [x] Implement keyword search in name and description
- [x] Implement sorting by saturation, freshness, coverage

#### Frontend Implementation
- [ ] Build catalog listing page component
- [ ] Build filter sidebar with category/frequency checkboxes
- [ ] Build search input with debounced queries
- [ ] Build sort dropdown
- [ ] Display data availability date range on each card

#### Testing
- [x] API endpoint tests for all filter combinations
- [ ] Frontend component tests
- [ ] E2E test for catalog browse flow

---

### US-002: AI-Powered Data Discovery

**As a** data scientist
**I want to** ask natural language questions like "show me consumer spending signals"
**So that** I can quickly find relevant data without knowing exact source names

#### Backend Implementation
- [x] Create `POST /api/v1/catalog/search/semantic` endpoint
- [x] Integrate LLM for query interpretation
- [x] Implement vector similarity search on source descriptions
- [x] Return ranked sources with relevance explanation
- [x] Implement related source suggestions based on query intent
- [x] Store recent searches per user

#### Frontend Implementation
- [ ] Build natural language search input in catalog header
- [ ] Display results with "Why this matches" explanation
- [ ] Show "Related sources" section
- [ ] Build recent searches dropdown

#### Testing
- [x] Test semantic search accuracy with sample queries
- [ ] Test explanation generation
- [ ] Frontend component tests

---

### US-003: Preview Sample Data

**As a** quant PM
**I want to** preview sample data for any source with interactive date selection
**So that** I can evaluate data quality before integrating

#### Backend Implementation
- [x] Create `GET /api/v1/catalog/sources/{source_id}/preview` endpoint
- [x] Accept query params: `start_date`, `end_date`, `ticker`, `limit`
- [x] Return data quality indicators (completeness, freshness)
- [x] Support export formats: CSV, Parquet, Arrow
- [x] Return row count and basic statistics

#### Frontend Implementation
- [ ] Build interactive date range picker
- [ ] Build sortable, filterable data table
- [ ] Display quality indicators (completeness %, last updated)
- [ ] Build entity/ticker filter
- [ ] Build export buttons (CSV, Parquet, Arrow)
- [ ] Show row count and stats summary

#### Testing
- [x] API tests for date range queries
- [ ] Test export functionality
- [ ] Frontend table interaction tests

---

### US-004: View Source Metadata

**As a** analyst
**I want to** see comprehensive metadata for each data source
**So that** I understand data characteristics before use

#### Backend Implementation
- [x] Create `GET /api/v1/catalog/sources/{source_id}` endpoint
- [x] Return full metadata including:
  - Name, description, collection frequency, typical latency
  - Geographic coverage, entity coverage, date range
  - Saturation level, sample API code snippets
  - List of derived factors

#### Frontend Implementation
- [ ] Build source detail page
- [ ] Display metadata in organized sections
- [ ] Show sample code snippets with copy button
- [ ] List derived factors with links to factor detail

#### Testing
- [x] API tests for metadata completeness
- [ ] Frontend rendering tests

---

## Epic 2: Factor Analysis

**Goal**: Enable users to explore, compare, and blend factors.

---

### US-005: Explore Factor Taxonomy Graph

**As a** data scientist
**I want to** visualize relationships between factors in a graph view
**So that** I can understand factor derivation and correlation structure

#### Backend Implementation
- [x] Create `Factor` model with relationships
- [x] Create `FactorRelationship` model
  - Types: derived-from, correlated-with, causes, leads, component-of
- [x] Create `GET /api/v1/factors/graph` endpoint
- [x] Support filtering by relationship type and domain

#### Frontend Implementation
- [ ] Integrate graph visualization library (D3, Cytoscape, or React Flow)
- [ ] Build interactive graph with zoom, pan, cluster controls
- [ ] Implement node click to expand details panel
- [ ] Build edge type filter
- [ ] Build domain filter (travel, real estate, etc.)
- [ ] Build factor search within graph

#### Testing
- [x] Test graph data structure
- [x] Test filter combinations
- [ ] Frontend interaction tests

---

### US-006: View Factor Documentation

**As a** quant PM
**I want to** see academic-quality documentation for each factor
**So that** I understand economic rationale and expected performance

#### Backend Implementation
- [x] Extend `Factor` model with documentation fields:
  - `formula` (LaTeX), `economic_rationale`, `literature_refs`
  - `historical_metrics` (IC, IR, t-stat, hit rate)
  - `decay_analysis`, `target_entities`, `signal_interpretation`
  - `known_limitations`
- [x] Create `GET /api/v1/factors/{factor_id}` endpoint

#### Frontend Implementation
- [ ] Build factor detail page
- [ ] Render formula with math notation (KaTeX/MathJax)
- [ ] Display economic rationale paragraphs
- [ ] Show literature references with clickable links
- [ ] Build historical metrics table
- [ ] Build decay analysis chart (IC at 1d, 5d, 10d, 21d, 63d horizons)
- [ ] List target entities
- [ ] Document signal interpretation and limitations

#### Testing
- [x] Test LaTeX rendering
- [ ] Test chart data binding
- [ ] Frontend rendering tests

---

### US-007: Compare Factors Side-by-Side

**As a** data scientist
**I want to** compare multiple factors side-by-side
**So that** I can evaluate which factors to include in my model

#### Backend Implementation
- [x] Create `POST /api/v1/factors/compare` endpoint
- [x] Accept list of factor_ids (max 4)
- [x] Compute and return:
  - Side-by-side performance metrics
  - Correlation matrix between selected factors
  - Time-series data for overlaid charts
  - Statistical significance flags

#### Frontend Implementation
- [ ] Build factor selector (multi-select, max 4)
- [ ] Build side-by-side metrics comparison table
- [ ] Build correlation matrix heatmap
- [ ] Build overlaid time-series chart with date sync
- [ ] Highlight statistically significant differences
- [ ] Build "Export as research pack" button

#### Testing
- [x] Test comparison computation
- [ ] Test correlation matrix accuracy
- [ ] Frontend chart synchronization tests

---

### US-008: Blend Factors with Optimization

**As a** quant PM
**I want to** blend multiple factors with optimized weights
**So that** I can create composite signals

#### Backend Implementation
- [x] Create `POST /api/v1/factors/blend` endpoint
- [x] Accept factor_ids and optimization config:
  - Objective: max_ic, max_sharpe, min_correlation, multi_objective
  - Constraints: max_weight, turnover_limits
- [x] Implement optimization algorithms
- [x] Return optimal weights and blended factor metrics
- [x] Create `POST /api/v1/factors/custom` to save blend

#### Frontend Implementation
- [ ] Build factor selection interface
- [ ] Build optimization objective selector
- [ ] Build constraints configuration form
- [ ] Display optimization results (weights, metrics)
- [ ] Build "Save as custom factor" flow

#### Testing
- [x] Test optimization algorithms
- [x] Test constraint handling
- [ ] E2E blend creation flow

---

## Epic 3: Real-Time Monitoring

**Goal**: Enable users to configure alerts and subscribe to real-time updates.

---

### US-009: Configure Threshold Alerts

**As a** fundamental analyst
**I want to** set alerts when factors cross specific thresholds
**So that** I'm notified of significant market signals

#### Backend Implementation
- [x] Create `Alert` model:
  - `factor_id`, `ticker_list`, `threshold_value`
  - `direction` (above, below, crosses)
  - `notification_channel` (email, webhook)
  - `name`, `description`, `enabled`
- [x] Create CRUD endpoints for alerts
- [x] Implement alert evaluation engine
- [x] Implement notification dispatch (email, webhook)
- [x] Implement test alert functionality

#### Frontend Implementation
- [ ] Build alert creation form
- [ ] Factor dropdown selector
- [ ] Ticker input (single or list)
- [ ] Threshold value input
- [ ] Direction selector
- [ ] Notification channel selector
- [ ] Enable/disable toggle
- [ ] Test alert button

#### Testing
- [x] Test alert evaluation logic
- [ ] Test notification dispatch
- [ ] E2E alert creation and trigger flow

---

### US-010: Configure Anomaly Detection Alerts

**As a** quant PM
**I want to** receive alerts when factors show unusual movements
**So that** I can react to significant market events

#### Backend Implementation
- [x] Extend `Alert` model for anomaly type
- [x] Implement statistical anomaly detection:
  - Configurable sensitivity (standard deviations)
  - Baseline period (7d, 30d, 90d rolling)
- [x] Implement ML-based anomaly detection option
- [x] Create endpoint to list recent anomalies

#### Frontend Implementation
- [ ] Build anomaly alert configuration form
- [ ] Sensitivity slider (std devs)
- [ ] Baseline period selector
- [ ] ML option toggle
- [ ] Recent anomalies display

#### Testing
- [x] Test anomaly detection accuracy
- [ ] Test ML model integration

---

### US-011: Configure Event-Based Alerts

**As a** insurance analyst
**I want to** receive alerts for specific events like earthquakes above magnitude 6.0
**So that** I can assess portfolio exposure

#### Backend Implementation
- [x] Extend `Alert` model for event type
- [x] Support event types: earthquake, contract_award, etc.
- [x] Implement event criteria configuration (magnitude > X)
- [x] Implement geographic filters (region, distance from location)
- [x] Include estimated impact in alert payload
- [x] Implement critical event immediate dispatch

#### Frontend Implementation
- [ ] Build event alert configuration form
- [ ] Event type selector
- [ ] Event criteria inputs
- [ ] Geographic filter (map-based or dropdown)
- [ ] Impact estimation toggle

#### Testing
- [x] Test event matching logic
- [ ] Test geographic filtering
- [ ] Test immediate dispatch for critical events

---

### US-012: Subscribe to WebSocket Streams

**As a** quant PM
**I want to** subscribe to real-time factor updates via WebSocket
**So that** I can incorporate signals into my intraday trading system

#### Backend Implementation
- [x] Implement WebSocket server endpoint
- [x] Implement API key authentication for WebSocket
- [x] Support subscription to specific factors and tickers
- [x] Support verbosity levels (simple, delta, full with mean/variance)
- [x] Implement automatic reconnection handling
- [x] Implement heartbeat mechanism
- [ ] Create Python SDK wrapper

#### Frontend Implementation
- [ ] Build WebSocket connection management
- [ ] Build subscription configuration UI
- [ ] Display real-time updates

#### SDK Implementation
- [ ] Create `altdata.stream` module in Python SDK
- [ ] Implement async subscription interface
- [ ] Document usage examples

#### Testing
- [x] Test WebSocket connection stability
- [x] Test subscription filtering
- [ ] Test reconnection logic

---

### US-013: Manage Alert Fatigue

**As a** analyst
**I want to** configure smart suppression for my alerts
**So that** I don't get overwhelmed with notifications

#### Backend Implementation
- [x] Extend alert configuration:
  - Quiet hours (no alerts during specified times)
  - Cooldown period between repeated alerts
  - Daily digest option
- [x] Implement ML-based alert prioritization
- [x] Implement alert bundling
- [x] Create alert history endpoint with read/unread status

#### Frontend Implementation
- [ ] Build quiet hours configuration
- [ ] Build cooldown period input
- [ ] Build digest vs real-time toggle
- [ ] Build alert history view with read/unread

#### Testing
- [x] Test quiet hours logic
- [x] Test cooldown enforcement
- [ ] Test digest generation

---

## Epic 4: Geographic Visualization

**Goal**: Display events and data on interactive maps.

---

### US-014: View Earthquake Event Map

**As a** insurance analyst
**I want to** see earthquake events on a geographic map
**So that** I can assess exposure for insurance companies

#### Backend Implementation
- [x] Create `GET /api/v1/geo/earthquakes` endpoint
- [x] Support filters: magnitude_min, date_range
- [x] Return GeoJSON with event details
- [x] Compute population within radius
- [x] Compute estimated economic impact
- [x] Compute insurance loss estimates by insurer

#### Frontend Implementation
- [ ] Integrate map library (Mapbox, Leaflet, or Google Maps)
- [ ] Display earthquake markers sized by magnitude
- [ ] Build magnitude filter slider
- [ ] Build date range filter
- [ ] Implement marker click for details panel:
  - Magnitude, depth, location, timestamp
  - Population within radius
  - Economic impact estimate
  - Insurance loss by insurer

#### Testing
- [x] Test GeoJSON formatting
- [x] Test impact calculations
- [ ] Frontend map interaction tests

---

### US-015: Configure Regional Earthquake Thresholds

**As a** data admin
**I want to** set different magnitude thresholds by region
**So that** alerts are appropriate for population/asset exposure

#### Backend Implementation
- [x] Create `RegionalThreshold` model
- [x] Support geographic region definition (GeoJSON polygons)
- [x] Allow magnitude threshold per region
- [x] Implement endpoint to preview which events would trigger

#### Frontend Implementation
- [ ] Build region definition interface (draw on map or select preset)
- [ ] Build threshold configuration per region
- [ ] Display default thresholds (lower near population centers)
- [ ] Build preview of recent triggering events

#### Testing
- [x] Test threshold evaluation by region
- [x] Test preview accuracy

---

### US-016: View Power Grid Node Map

**As a** energy analyst
**I want to** see LMP prices visualized on a geographic map
**So that** I can identify price spikes and congestion

#### Backend Implementation
- [x] Create `GET /api/v1/geo/power-grid` endpoint
- [x] Return LMP data by ISO region (PJM, ERCOT, CAISO, ISO-NE, MISO, SPP, NYISO)
- [x] Support historical playback
- [x] Include node-level price history
- [x] Include renewable generation share overlay

#### Frontend Implementation
- [ ] Build map showing ISO regions
- [ ] Implement heat map overlay of LMP prices
- [ ] Build historical playback slider
- [ ] Implement node click for price history chart
- [ ] Build price percentile filter
- [ ] Build renewable share overlay toggle

#### Testing
- [x] Test LMP data accuracy
- [ ] Test playback functionality
- [ ] Frontend map rendering tests

---

## Epic 5: Backtesting & Research

**Goal**: Enable users to validate factor quality through backtesting.

---

### US-017: Run Factor Backtest

**As a** quant PM
**I want to** backtest a factor against my return data
**So that** I can validate signal quality before deployment

#### Backend Implementation
- [x] Create `POST /api/v1/backtest/run` endpoint
- [x] Accept return data upload (CSV: ticker, date, return)
- [x] Accept factor_id and date_range
- [x] Compute: IC, IR, t-stat, hit rate
- [x] Compute decile spread (long-short returns)
- [x] Compute monthly IC time series
- [x] Flag survivorship bias warnings

#### Frontend Implementation
- [ ] Build return data upload interface
- [ ] Build factor and date range selection
- [ ] Display metrics table (IC, IR, t-stat, hit rate)
- [ ] Build decile spread chart
- [ ] Build monthly IC time series chart
- [ ] Display survivorship bias warnings

#### Testing
- [x] Test backtest computation accuracy
- [x] Test file upload handling
- [ ] Validate metrics against known benchmarks

---

### US-018: Analyze Factor Decay

**As a** data scientist
**I want to** analyze how factor signal decays over time
**So that** I can determine optimal holding period

#### Backend Implementation
- [x] Create `GET /api/v1/backtest/decay/{factor_id}` endpoint
- [x] Compute IC at horizons: 1d, 2d, 5d, 10d, 21d, 63d, 126d, 252d
- [x] Estimate signal half-life
- [ ] Support multi-factor comparison

#### Frontend Implementation
- [ ] Build decay curve chart
- [ ] Display half-life estimate
- [ ] Build multi-factor overlay for comparison

#### Testing
- [x] Test decay computation
- [x] Test half-life estimation accuracy

---

### US-019: Analyze Factor Seasonality

**As a** quant PM
**I want to** understand seasonal patterns in factor performance
**So that** I can adjust my strategy timing

#### Backend Implementation
- [x] Create `GET /api/v1/backtest/seasonality/{factor_id}` endpoint
- [x] Compute day-of-week IC breakdown
- [x] Compute monthly IC breakdown
- [x] Identify holiday effects (global developed market calendar)
- [ ] Identify event-based seasonality (earnings season)
- [ ] Support seasonal adjustment of factor values

#### Frontend Implementation
- [ ] Build day-of-week IC chart
- [ ] Build monthly IC chart
- [ ] Highlight holiday effects
- [ ] Display event-based patterns
- [ ] Build seasonal adjustment toggle

#### Testing
- [x] Test seasonality computation
- [ ] Test holiday calendar accuracy

---

### US-020: Export Research Pack

**As a** data scientist
**I want to** export a complete research pack for a factor
**So that** I can share analysis with my team

#### Backend Implementation
- [x] Create `POST /api/v1/backtest/export` endpoint
- [ ] Generate Jupyter notebook with analysis code
- [ ] Include raw factor data (CSV, Parquet, Arrow)
- [ ] Include computed statistics (JSON)
- [ ] Include charts as PNG/SVG
- [ ] Include methodology documentation (PDF/Markdown)
- [ ] Package as downloadable ZIP

#### Frontend Implementation
- [ ] Build export button on factor detail page
- [ ] Show export progress indicator
- [ ] Download ZIP on completion

#### Testing
- [x] Test export endpoint exists
- [ ] Test notebook generation
- [ ] Test all export formats
- [ ] Test ZIP packaging

---

### US-021: Run Factor A/B Experiment

**As a** data scientist
**I want to** run A/B tests on different factor formulations
**So that** I can identify the best performing variant

#### Backend Implementation
- [ ] Create `Experiment` model
- [ ] Create CRUD endpoints for experiments
- [ ] Support control vs treatment factor definition
- [ ] Track parallel performance metrics
- [ ] Implement statistical significance testing (p-value)
- [ ] Support promoting winning variant

#### Frontend Implementation
- [ ] Build experiment creation form
- [ ] Display parallel metrics tracking
- [ ] Show statistical significance results
- [ ] Build "Promote to production" button

#### Testing
- [ ] Test experiment tracking
- [ ] Test significance calculations

---

## Epic 6: API Integration

**Goal**: Provide programmatic access to platform data.

---

### US-022: Authenticate with API Key

**As a** developer
**I want to** authenticate API requests with an API key
**So that** I can access factor data programmatically

#### Backend Implementation
- [x] Create `APIKey` model
- [x] Implement key generation (show once, cannot retrieve)
- [x] Implement Bearer token authentication middleware
- [x] Tie key to account tier with rate limits
- [x] Support key rotation (create new, deprecate old)
- [x] Track usage statistics per key

#### Frontend Implementation
- [ ] Build API key management in user settings
- [ ] Key generation with copy-once display
- [ ] Show active keys with usage stats
- [ ] Key rotation interface
- [ ] Usage dashboard (requests, data volume)

#### Testing
- [x] Test authentication middleware
- [ ] Test rate limiting
- [ ] Test key rotation

---

### US-023: Query Factor History via REST

**As a** quant PM
**I want to** query historical factor values via REST API
**So that** I can integrate data into my backtesting system

#### Backend Implementation
- [x] Create `GET /api/v1/factors/{factor_id}/history` endpoint
- [x] Query params: tickers (comma-separated), start_date, end_date
- [x] Implement cursor-based pagination
- [ ] Support response formats: JSON, CSV, Parquet, Arrow
- [x] Include mean and variance in response
- [x] Include as_of_date and computation_timestamp
- [ ] Return rate limit headers

#### Testing
- [x] Test all query param combinations
- [x] Test pagination
- [ ] Test all response formats

---

### US-024: Query Entity Factors via REST

**As a** analyst
**I want to** get all factors for a specific ticker
**So that** I can see the full signal picture

#### Backend Implementation
- [x] Create `GET /api/v1/factors` endpoint (list all factors)
- [x] Optional factor_ids filter via search
- [x] Optional domain filter
- [x] Return latest values by default
- [x] Include factor metadata in response
- [ ] Support ETF ticker aggregation

#### Testing
- [x] Test factor listing
- [ ] Test ETF aggregation
- [x] Test filtering

---

### US-025: Generate Pine Script Indicator

**As a** retail trader
**I want to** generate a Pine Script indicator from a platform factor
**So that** I can use it in TradingView

#### Backend Implementation
- [ ] Create `POST /api/v1/factors/{factor_id}/pinescript` endpoint
- [ ] Generate Pine Script code for factor
- [ ] Include real-time data feed integration code
- [ ] Generate TradingView setup instructions

#### Frontend Implementation
- [ ] Build "Generate Pine Script" button on factor page
- [ ] Display generated code in modal
- [ ] Copy to clipboard button
- [ ] Show setup instructions

#### Testing
- [x] Test factor decay endpoint exists (prerequisite)
- [ ] Validate generated Pine Script syntax
- [ ] Test code generation for all factor types

---

### US-026: Full TradingView Sync

**As a** quant developer
**I want to** bidirectionally sync between platform and TradingView
**So that** I can use both tools seamlessly

#### Backend Implementation
- [ ] Implement real-time factor push to TradingView
- [ ] Implement TradingView annotation import
- [ ] Synchronize backtesting capabilities
- [ ] Create Pine Script SDK documentation
- [ ] Implement OAuth connection to TradingView

#### Frontend Implementation
- [ ] Build TradingView connection setup
- [ ] Display sync status
- [ ] Build annotation import interface

#### Testing
- [x] Test factor compare endpoint exists
- [ ] Test real-time sync
- [ ] Test annotation import
- [ ] Test OAuth flow

---

## Epic 7: Entity Mapping

**Goal**: Maintain accurate mappings between data entities and tickers.

---

### US-027: Review Pending Entity Mappings

**As a** data admin
**I want to** review algorithmically-generated entity mappings
**So that** I can ensure data quality

#### Backend Implementation
- [ ] Create `EntityMapping` model with confidence scores
- [ ] Create `GET /api/v1/admin/mappings/pending` endpoint
- [ ] Filter for confidence < 0.9
- [ ] Include AI-suggested alternatives with scores
- [ ] Create approve/reject/correct endpoints
- [ ] Support bulk approve for high-confidence
- [ ] Maintain audit trail

#### Frontend Implementation
- [ ] Build mapping review queue
- [ ] Display source entity, suggested ticker, confidence
- [ ] Show AI alternatives
- [ ] Approve/reject/correct buttons
- [ ] Bulk approve interface
- [ ] Audit trail view

#### Testing
- [ ] Test mapping workflow
- [ ] Test audit trail

---

### US-028: Suggest Missing Entity Mapping

**As a** analyst
**I want to** suggest a ticker mapping for an unmapped entity
**So that** the data becomes actionable for me

#### Backend Implementation
- [ ] Create `GET /api/v1/entities/unmapped` endpoint
- [ ] Filter by data source
- [ ] Create `POST /api/v1/mappings/suggest` endpoint
- [ ] Track suggestion status (submitted, reviewing, approved, rejected)
- [ ] Notify user on status change

#### Frontend Implementation
- [ ] Build unmapped entities list
- [ ] Build suggestion submission form
- [ ] Show suggestion status tracking
- [ ] Display notifications on status change

#### Testing
- [ ] Test suggestion workflow
- [ ] Test notifications

---

### US-029: View Entity Mapping Coverage

**As a** data admin
**I want to** see entity mapping coverage statistics
**So that** I can prioritize mapping efforts

#### Backend Implementation
- [ ] Create `GET /api/v1/admin/mappings/coverage` endpoint
- [ ] Compute % mapped by data source
- [ ] Compute $ value/volume of unmapped entities
- [ ] Prioritize high-value unmapped entities
- [ ] Track coverage trend over time
- [ ] Support export of unmapped list

#### Frontend Implementation
- [ ] Build coverage dashboard
- [ ] Display % mapped by source (bar chart)
- [ ] Show unmapped $ value
- [ ] Build prioritized unmapped list
- [ ] Build coverage trend chart
- [ ] Export button

#### Testing
- [ ] Test coverage calculations
- [ ] Test prioritization logic

---

### US-030: Handle Corporate Actions

**As a** data admin
**I want to** be notified of corporate actions affecting mappings
**So that** historical data is properly adjusted

#### Backend Implementation
- [ ] Implement corporate action detection (ticker changes, mergers, spinoffs)
- [ ] Create alert on detected actions
- [ ] Show affected entity mappings
- [ ] Preview historical adjustment impact
- [ ] Implement approve/reject adjustment
- [ ] Maintain audit trail

#### Frontend Implementation
- [ ] Build corporate action alerts
- [ ] Show affected mappings
- [ ] Preview adjustment impact
- [ ] Approve/reject interface
- [ ] Audit trail view

#### Testing
- [ ] Test corporate action detection
- [ ] Test historical adjustment

---

## Epic 8: Disaster & Event Signals

**Goal**: Provide specialized signals for disaster and event-driven analysis.

---

### US-031: View Insurance Loss Estimates

**As a** insurance analyst
**I want to** see modeled loss estimates by insurer after disasters
**So that** I can assess sector impact

#### Backend Implementation
- [ ] Create loss estimation model
- [ ] Compute estimates after earthquake above threshold
- [ ] Break down by major insurers (ALL, TRV, CB, PGR, etc.)
- [ ] Include confidence intervals (mean + variance)
- [ ] Factor in geographic book exposure
- [ ] Factor in reinsurance arrangements
- [ ] Compare to historical similar events

#### Frontend Implementation
- [ ] Build loss estimate panel (triggered by qualifying event)
- [ ] Display breakdown by insurer
- [ ] Show confidence intervals
- [ ] Historical comparison chart

#### Testing
- [ ] Validate loss model accuracy
- [ ] Test historical comparison

---

### US-032: View Box Office Predictions

**As a** entertainment analyst
**I want to** see opening weekend forecasts from Thursday previews
**So that** I can anticipate studio performance

#### Backend Implementation
- [ ] Create box office prediction model
- [ ] Implement ensemble model for weekend forecast
- [ ] Compute confidence intervals
- [ ] Compare to studio guidance/tracking
- [ ] Track historical model accuracy
- [ ] Map predictions to studio tickers

#### Frontend Implementation
- [ ] Build forecast panel after Thursday preview release
- [ ] Display ensemble predictions
- [ ] Show confidence intervals
- [ ] Compare to guidance
- [ ] Show model accuracy history
- [ ] Link to affected tickers

#### Testing
- [ ] Validate prediction model accuracy
- [ ] Test ensemble computation

---

## Epic 9: Data Catalog Management

**Goal**: Enable management and monitoring of data sources.

---

### US-033: Request New Data Source

**As a** analyst
**I want to** request that a new data source be added
**So that** I can get signals I need

#### Backend Implementation
- [ ] Create `DataSourceRequest` model
- [ ] Create CRUD endpoints
- [ ] Track status (submitted, evaluating, approved, rejected, implemented)
- [ ] Notify user on status changes

#### Frontend Implementation
- [ ] Build request submission form (name, URL, description, use case)
- [ ] Priority indicator
- [ ] Status tracking view
- [ ] Notification display

#### Testing
- [ ] Test request workflow
- [ ] Test notifications

---

### US-034: View Source Health Dashboard

**As a** data admin
**I want to** see health status of all data collectors
**So that** I can identify and fix issues

#### Backend Implementation
- [ ] Implement collector health tracking
- [ ] Create `GET /api/v1/admin/collectors/health` endpoint
- [ ] Track up/down status, last success timestamp
- [ ] Track data freshness vs SLA
- [ ] Store error logs
- [ ] Implement manual trigger endpoint

#### Frontend Implementation
- [ ] Build health dashboard
- [ ] Display collector list with status indicators
- [ ] Show last successful collection
- [ ] Show freshness vs SLA
- [ ] Alert on SLA breaches
- [ ] Error log viewer
- [ ] Manual trigger button

#### Testing
- [ ] Test health tracking
- [ ] Test SLA breach detection
- [ ] Test manual trigger

---

### US-035: View Archived Sources

**As a** analyst
**I want to** access historical data from deprecated sources
**So that** I can maintain continuity in my research

#### Backend Implementation
- [ ] Implement source archival workflow
- [ ] Maintain full API access to archived data
- [ ] Store deprecation reason and date
- [ ] Link to alternative sources
- [ ] Ensure factors from archived sources remain computable

#### Frontend Implementation
- [ ] Display archived label in catalog
- [ ] Show deprecation reason and date
- [ ] Suggest alternatives
- [ ] Full data access via UI/API

#### Testing
- [ ] Test archived data access
- [ ] Test factor computation on archived data

---

## Epic 10: User Management & Tiers

**Goal**: Manage user accounts and subscription tiers.

---

### US-036: View Tier Usage

**As a** user
**I want to** see my API usage relative to tier limits
**So that** I know if I need to upgrade

#### Backend Implementation
- [ ] Track API requests per user
- [ ] Track data volume consumed
- [ ] Create `GET /api/v1/user/usage` endpoint
- [ ] Implement 80% and 95% warning thresholds
- [ ] Track historical usage

#### Frontend Implementation
- [ ] Build usage dashboard
- [ ] Display requests used / limit (progress bar)
- [ ] Display data volume consumed
- [ ] List features in current tier
- [ ] Warning banners at 80% and 95%
- [ ] Historical usage chart

#### Testing
- [ ] Test usage tracking accuracy
- [ ] Test warning triggers

---

### US-037: Upgrade Tier

**As a** user
**I want to** upgrade my subscription tier
**So that** I can access more data and features

#### Backend Implementation
- [ ] Implement tier comparison endpoint
- [ ] Implement upgrade endpoint
- [ ] Immediate feature access on upgrade
- [ ] Implement prorated billing calculation

#### Frontend Implementation
- [ ] Build tier comparison page
- [ ] Display clear pricing
- [ ] One-click upgrade button
- [ ] Confirmation with prorated amount
- [ ] Success confirmation with new features

#### Testing
- [ ] Test upgrade flow
- [ ] Test prorated billing
- [ ] Test immediate feature access

---

## Technical Specifications

### Architecture

| Component | Technology |
|-----------|------------|
| Database | PostgreSQL (PIT-enabled) |
| Task Queue | Celery + Redis |
| API | FastAPI |
| Frontend | Professional fintech SaaS (light mode) |
| File Storage | S3-compatible |

### SLAs

| Metric | Target |
|--------|--------|
| Uptime | 99.99% |
| API P50 Latency | < 100ms |
| API P99 Latency | < 500ms |
| Factor Compute | < 1 hour batch |

### Pricing Tiers

| Tier | Rate Limit | Data Access | Features |
|------|------------|-------------|----------|
| Free | 100/day | Phase 1, 30d history | Basic API |
| Pro | 10K/day | All free, full history | Alerts, backtesting, SDK |
| Enterprise | Unlimited | All sources | Full features, SLA, support |

---

## File Structure Reference

```
src/
├── collectors/
│   ├── tsa_checkpoint.py
│   ├── opentable.py
│   ├── usgs_earthquake.py
│   ├── carbon_intensity.py
│   ├── fred_collector.py (building permits)
│   ├── boxoffice.py
│   ├── cloudflare_radar.py
│   └── zillow_rental.py
├── models/
│   ├── data_sources.py
│   ├── factors.py
│   ├── alerts.py
│   ├── entity_mappings.py
│   └── users.py
├── api/
│   ├── catalog.py
│   ├── factors.py
│   ├── alerts.py
│   ├── backtest.py
│   ├── geo.py
│   └── admin.py
├── transformations/
│   └── factors/
│       ├── tsa_factors.py
│       ├── restaurant_factors.py
│       ├── earthquake_factors.py
│       ├── carbon_factors.py
│       ├── building_permit_factors.py
│       ├── boxoffice_factors.py
│       ├── internet_factors.py
│       └── rental_factors.py
└── entity_mapping/
    ├── government_contractor_mapping.py
    ├── game_publisher_mapping.py
    └── studio_ticker_mapping.py
```

---

*Last Updated: Aligned with PRD.md*
